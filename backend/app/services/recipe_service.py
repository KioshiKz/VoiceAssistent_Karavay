import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event_template import EventTemplate
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe_step import RecipeStep
from app.schemas.recipe_step import RecipeStepCreate
from app.services.unit_conversion import format_compound


async def get_product_or_404(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, detail="product_not_found")
    return product


async def load_steps(db: AsyncSession, product_id: uuid.UUID) -> list[RecipeStep]:
    result = await db.execute(
        select(RecipeStep)
        .where(RecipeStep.product_id == product_id)
        .options(selectinload(RecipeStep.ingredient), selectinload(RecipeStep.event_template))
        .order_by(RecipeStep.order_index)
    )
    return list(result.scalars().all())


def step_to_dict(step: RecipeStep) -> dict:
    quantity_display = None
    if step.step_type == "ingredient" and step.ingredient is not None and step.quantity_canonical is not None:
        quantity_display = format_compound(step.quantity_canonical, step.ingredient.measure_type)
    return {
        "id": step.id,
        "product_id": step.product_id,
        "order_index": step.order_index,
        "step_type": step.step_type,
        "ingredient": step.ingredient,
        "quantity_canonical": step.quantity_canonical,
        "quantity_display": quantity_display,
        "event_template": step.event_template,
        "event_params": step.event_params,
    }


async def create_step(db: AsyncSession, product_id: uuid.UUID, payload: RecipeStepCreate) -> RecipeStep:
    if payload.step_type == "ingredient":
        ingredient = await db.get(Ingredient, payload.ingredient_id)
        if ingredient is None:
            raise HTTPException(404, detail="ingredient_not_found")
    else:
        event_template = await db.get(EventTemplate, payload.event_template_id)
        if event_template is None:
            raise HTTPException(404, detail="event_template_not_found")

    step = RecipeStep(
        product_id=product_id,
        order_index=payload.order_index,
        step_type=payload.step_type,
        ingredient_id=payload.ingredient_id,
        quantity_canonical=payload.quantity_canonical,
        event_template_id=payload.event_template_id,
        event_params=payload.event_params,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step, attribute_names=["ingredient", "event_template"])
    return step


async def update_step(db: AsyncSession, step: RecipeStep, payload) -> RecipeStep:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(step, key, value)
    await db.commit()
    await db.refresh(step, attribute_names=["ingredient", "event_template"])
    return step


async def delete_step(db: AsyncSession, step: RecipeStep) -> None:
    await db.delete(step)
    await db.commit()


async def reorder_steps(db: AsyncSession, product_id: uuid.UUID, step_ids: list[uuid.UUID]) -> list[RecipeStep]:
    steps = await load_steps(db, product_id)
    steps_by_id = {s.id: s for s in steps}
    if set(steps_by_id) != set(step_ids):
        raise HTTPException(409, detail="step_ids_do_not_match_product_steps")

    # two-phase: push to a temporary offset first to avoid unique(product_id, order_index) clashes
    offset = len(step_ids) + 1000
    for step in steps:
        step.order_index += offset
    await db.flush()

    for position, step_id in enumerate(step_ids):
        steps_by_id[step_id].order_index = position

    await db.commit()
    return await load_steps(db, product_id)
