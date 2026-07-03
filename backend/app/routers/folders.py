import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.folder import Folder
from app.models.user import User
from app.schemas.folder import (
    FolderContentOut,
    FolderCreate,
    FolderMove,
    FolderOut,
    FolderPermissionsOut,
    FolderRename,
)
from app.services import folder_service, permission_service

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("/tree", response_model=list[FolderOut])
async def folder_tree(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Folder).order_by(Folder.materialized_path))
    folders = result.scalars().all()
    visible = []
    for f in folders:
        if await permission_service.has_folder_permission(db, user, "folder.view", f):
            visible.append(f)
    return visible


@router.get("/{folder_id}/content", response_model=FolderContentOut)
async def folder_content(
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.view", folder_param="folder_id")),
):
    folder = await folder_service.get_folder_or_404(db, folder_id)
    breadcrumbs = await folder_service.get_breadcrumbs(db, folder)
    content = await folder_service.get_folder_content(db, folder)
    can_create = await permission_service.has_folder_permission(db, user, "folder.create", folder)
    can_edit = await permission_service.has_folder_permission(db, user, "folder.edit", folder)
    return FolderContentOut(
        folder=folder,
        breadcrumbs=breadcrumbs,
        permissions=FolderPermissionsOut(view=True, create=can_create, edit=can_edit),
        subfolders=content["subfolders"],
        ingredients=content["ingredients"],
        products=content["products"],
        events=content["events"],
    )


@router.post("", response_model=FolderOut, status_code=201)
async def create_folder(
    payload: FolderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.parent_id is not None:
        parent = await folder_service.get_folder_or_404(db, payload.parent_id)
        if not await permission_service.has_folder_permission(db, user, "folder.create", parent):
            raise HTTPException(403, detail="permission_denied")
    else:
        # root-level folders have no parent to scope a folder.create check against
        if not await permission_service.has_global_permission(db, user, "admin.manage"):
            raise HTTPException(403, detail="permission_denied")

    folder = await folder_service.create_folder(
        db, name=payload.name, parent_id=payload.parent_id, created_by=user.id
    )
    return folder


@router.patch("/{folder_id}/rename", response_model=FolderOut)
async def rename_folder(
    folder_id: uuid.UUID,
    payload: FolderRename,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.edit", folder_param="folder_id")),
):
    folder = await folder_service.get_folder_or_404(db, folder_id)
    return await folder_service.rename_folder(db, folder, payload.name)


@router.patch("/{folder_id}/move", response_model=FolderOut)
async def move_folder(
    folder_id: uuid.UUID,
    payload: FolderMove,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.edit", folder_param="folder_id")),
):
    folder = await folder_service.get_folder_or_404(db, folder_id)
    if payload.parent_id is not None:
        target = await folder_service.get_folder_or_404(db, payload.parent_id)
        if not await permission_service.has_folder_permission(db, user, "folder.edit", target):
            raise HTTPException(403, detail="permission_denied")
    return await folder_service.move_folder(db, folder, payload.parent_id)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.edit", folder_param="folder_id")),
):
    folder = await folder_service.get_folder_or_404(db, folder_id)
    await folder_service.delete_folder(db, folder)
