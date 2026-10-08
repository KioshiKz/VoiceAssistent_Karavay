import uuid

from sqlalchemy import literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_template import EventTemplate
from app.models.folder import Folder
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe_step import RecipeStep


def recipe_scope_path(folder_path: str) -> str | None:
    """Return the first branch below a workshop for sibling recipe resources.

    A folder path is `/workshop/category/.../`. Products anywhere inside the
    category can use ingredients and events from every folder in that same
    category, including nested sibling folders. The workshop root itself is
    deliberately not a sibling scope: its direct resources remain available
    through the legacy ancestor rule without leaking resources between the
    workshop's categories.
    """
    parts = [part for part in folder_path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"/{parts[0]}/{parts[1]}/"


def recipe_resource_path_is_visible(target_path: str, resource_path: str) -> bool:
    """Pure counterpart of the SQL visibility rule, used by tests and guards."""
    if target_path.startswith(resource_path):
        return True
    scope_path = recipe_scope_path(target_path)
    return scope_path is not None and resource_path.startswith(scope_path)


def _recipe_resource_filter(target_folder: Folder):
    inherited = literal(target_folder.materialized_path).like(Folder.materialized_path + "%")
    scope_path = recipe_scope_path(target_folder.materialized_path)
    if scope_path is None:
        return inherited
    return or_(inherited, Folder.materialized_path.like(f"{scope_path}%"))


async def visible_ingredients(db: AsyncSession, target_folder: Folder) -> list[Ingredient]:
    """Return active ingredients inherited from ancestors or kept in the same recipe branch."""
    result = await db.execute(
        select(Ingredient)
        .join(Folder, Folder.id == Ingredient.folder_id)
        .where(
            _recipe_resource_filter(target_folder),
            Ingredient.is_active.is_(True),
        )
        .order_by(Folder.materialized_path, Ingredient.name)
    )
    return list(result.scalars().all())


async def visible_event_templates(db: AsyncSession, target_folder: Folder) -> list[EventTemplate]:
    result = await db.execute(
        select(EventTemplate)
        .join(Folder, Folder.id == EventTemplate.folder_id)
        .where(
            _recipe_resource_filter(target_folder),
            EventTemplate.is_active.is_(True),
        )
        .order_by(Folder.materialized_path, EventTemplate.name)
    )
    return list(result.scalars().all())


async def used_in_products(db: AsyncSession, ingredient_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Product.id, Product.name, Folder.materialized_path, Folder.name)
        .join(RecipeStep, RecipeStep.product_id == Product.id)
        .join(Folder, Folder.id == Product.folder_id)
        .where(RecipeStep.ingredient_id == ingredient_id)
        .order_by(Folder.materialized_path, Product.name)
    )
    rows = result.all()
    return [
        {"product_id": pid, "product_name": pname, "folder_path": fpath}
        for pid, pname, fpath, _fname in rows
    ]
