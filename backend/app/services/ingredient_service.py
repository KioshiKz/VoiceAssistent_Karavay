import uuid

from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_template import EventTemplate
from app.models.folder import Folder
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe_step import RecipeStep


async def visible_ingredients(db: AsyncSession, target_folder: Folder) -> list[Ingredient]:
    """Ingredients created in target_folder or any of its ancestors (inheritance rule):
    visible iff the ingredient's folder path is a prefix of the target folder's path."""
    result = await db.execute(
        select(Ingredient)
        .join(Folder, Folder.id == Ingredient.folder_id)
        .where(
            literal(target_folder.materialized_path).like(Folder.materialized_path + "%"),
            Ingredient.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def visible_event_templates(db: AsyncSession, target_folder: Folder) -> list[EventTemplate]:
    result = await db.execute(
        select(EventTemplate)
        .join(Folder, Folder.id == EventTemplate.folder_id)
        .where(
            literal(target_folder.materialized_path).like(Folder.materialized_path + "%"),
            EventTemplate.is_active.is_(True),
        )
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
