import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_template import EventTemplate
from app.models.folder import Folder
from app.models.ingredient import Ingredient
from app.models.product import Product

ROOT_SEGMENT = ""


def _build_path(parent_path: str | None, folder_id: uuid.UUID) -> str:
    prefix = parent_path or "/"
    return f"{prefix}{folder_id}/"


async def get_folder_or_404(db: AsyncSession, folder_id: uuid.UUID) -> Folder:
    folder = await db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="folder_not_found")
    return folder


async def get_breadcrumbs(db: AsyncSession, folder: Folder) -> list[Folder]:
    ids = [uuid.UUID(p) for p in folder.materialized_path.split("/") if p]
    if not ids:
        return []
    result = await db.execute(select(Folder).where(Folder.id.in_(ids)))
    by_id = {f.id: f for f in result.scalars().all()}
    return [by_id[i] for i in ids if i in by_id]


async def create_folder(
    db: AsyncSession, *, name: str, parent_id: uuid.UUID | None, created_by: uuid.UUID
) -> Folder:
    parent: Folder | None = None
    if parent_id is not None:
        parent = await get_folder_or_404(db, parent_id)

    folder = Folder(
        name=name,
        parent_id=parent_id,
        depth=(parent.depth + 1) if parent else 0,
        materialized_path="",
        created_by=created_by,
    )
    db.add(folder)
    await db.flush()  # obtain folder.id
    folder.materialized_path = _build_path(parent.materialized_path if parent else None, folder.id)
    await db.commit()
    await db.refresh(folder)
    return folder


async def rename_folder(db: AsyncSession, folder: Folder, new_name: str) -> Folder:
    folder.name = new_name
    await db.commit()
    await db.refresh(folder)
    return folder


async def _is_descendant(db: AsyncSession, candidate_id: uuid.UUID, ancestor_id: uuid.UUID) -> bool:
    candidate = await get_folder_or_404(db, candidate_id)
    ancestor_ids = {uuid.UUID(p) for p in candidate.materialized_path.split("/") if p}
    return ancestor_id in ancestor_ids


async def move_folder(db: AsyncSession, folder: Folder, new_parent_id: uuid.UUID | None) -> Folder:
    if new_parent_id is not None:
        if new_parent_id == folder.id or await _is_descendant(db, new_parent_id, folder.id):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="cannot_move_into_own_subtree")
        new_parent = await get_folder_or_404(db, new_parent_id)
    else:
        new_parent = None

    old_path_prefix = folder.materialized_path
    old_depth = folder.depth

    folder.parent_id = new_parent_id
    new_own_path = _build_path(new_parent.materialized_path if new_parent else None, folder.id)
    depth_delta = ((new_parent.depth + 1) if new_parent else 0) - old_depth

    folder.materialized_path = new_own_path
    folder.depth += depth_delta

    # bulk-update descendants: replace the old prefix with the new one, adjust depth
    result = await db.execute(
        select(Folder).where(Folder.materialized_path.like(f"{old_path_prefix}%"), Folder.id != folder.id)
    )
    for descendant in result.scalars().all():
        suffix = descendant.materialized_path[len(old_path_prefix):]
        descendant.materialized_path = f"{new_own_path}{suffix}"
        descendant.depth += depth_delta

    await db.commit()
    await db.refresh(folder)
    return folder


async def delete_folder(db: AsyncSession, folder: Folder) -> None:
    child_folders = await db.execute(select(Folder.id).where(Folder.parent_id == folder.id))
    if child_folders.first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="folder_not_empty_has_subfolders")

    for model in (Ingredient, EventTemplate, Product):
        existing = await db.execute(select(model.id).where(model.folder_id == folder.id))
        if existing.first() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="folder_not_empty_has_configs")

    await db.delete(folder)
    await db.commit()


async def get_folder_content(db: AsyncSession, folder: Folder) -> dict:
    subfolders = (await db.execute(select(Folder).where(Folder.parent_id == folder.id))).scalars().all()
    ingredients = (await db.execute(select(Ingredient).where(Ingredient.folder_id == folder.id))).scalars().all()
    events = (await db.execute(select(EventTemplate).where(EventTemplate.folder_id == folder.id))).scalars().all()
    products = (await db.execute(select(Product).where(Product.folder_id == folder.id))).scalars().all()
    return {
        "subfolders": subfolders,
        "ingredients": ingredients,
        "events": events,
        "products": products,
    }
