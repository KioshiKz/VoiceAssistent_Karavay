import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event_template import EventTemplate
from app.models.folder import Folder
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.recipe_step import RecipeStep
from app.schemas.recipe_step import RecipeStepCreate
from app.schemas.weight_check import merge_weight_params
from app.services.ingredient_service import recipe_resource_path_is_visible
from app.services.unit_conversion import format_compound, quantize_quantity
from app.services.scale_service import weight_parameters


async def get_product_or_404(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, detail="product_not_found")
    return product


async def lock_product_recipe(db: AsyncSession, product_id: uuid.UUID) -> None:
    result = await db.execute(select(Product.id).where(Product.id == product_id).with_for_update())
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, detail="product_not_found")


async def next_step_index(db: AsyncSession, product_id: uuid.UUID) -> int:
    await lock_product_recipe(db, product_id)
    result = await db.execute(select(func.max(RecipeStep.order_index)).where(RecipeStep.product_id == product_id))
    last = result.scalar_one()
    return 0 if last is None else last + 1


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
    if step.step_type in {"ingredient", "ingredient_event"} and step.ingredient is not None and step.quantity_canonical is not None:
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


async def _require_recipe_resource_visible(
    db: AsyncSession,
    target_folder: Folder,
    resource_folder_id: uuid.UUID,
) -> None:
    resource_folder = await db.get(Folder, resource_folder_id)
    if resource_folder is None or not recipe_resource_path_is_visible(
        target_folder.materialized_path,
        resource_folder.materialized_path,
    ):
        raise HTTPException(422, detail="recipe_resource_outside_product_scope")


async def create_step(
    db: AsyncSession,
    product_id: uuid.UUID,
    payload: RecipeStepCreate,
    *,
    target_folder: Folder | None = None,
) -> RecipeStep:
    event_params = payload.event_params
    if payload.step_type in {"ingredient", "ingredient_event"}:
        ingredient = await db.get(Ingredient, payload.ingredient_id)
        if ingredient is None:
            raise HTTPException(404, detail="ingredient_not_found")
        if target_folder is not None:
            await _require_recipe_resource_visible(db, target_folder, ingredient.folder_id)
    if payload.step_type in {"event", "ingredient_event"}:
        event_template = await db.get(EventTemplate, payload.event_template_id)
        if event_template is None:
            raise HTTPException(404, detail="event_template_not_found")
        if target_folder is not None:
            await _require_recipe_resource_visible(db, target_folder, event_template.folder_id)
        if event_template.event_type == "weight_check":
            event_params = merge_weight_params(getattr(event_template, "default_params", None), event_params)
            linked_weight = payload.step_type == "ingredient_event" and ingredient.measure_type == "weight"
            use_ingredient = event_params.get("use_ingredient_weight", linked_weight)
            if not isinstance(use_ingredient, bool) or (use_ingredient and not linked_weight):
                raise HTTPException(422, detail="Вес связанного ингредиента доступен только для ингредиентов с мерой «Вес».")
            event_params["use_ingredient_weight"] = use_ingredient
            if use_ingredient:
                event_params["target_weight_g"] = float(quantize_quantity(payload.quantity_canonical))
            weight_parameters(event_params)

    step = RecipeStep(
        product_id=product_id,
        order_index=await next_step_index(db, product_id),
        step_type=payload.step_type,
        ingredient_id=payload.ingredient_id,
        quantity_canonical=quantize_quantity(payload.quantity_canonical) if payload.quantity_canonical is not None else None,
        event_template_id=payload.event_template_id,
        event_params=event_params,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step, attribute_names=["ingredient", "event_template"])
    return step


async def update_step(db: AsyncSession, step: RecipeStep, payload) -> RecipeStep:
    changes = payload.model_dump(exclude_unset=True)
    if step.event_template_id and ({"event_params", "quantity_canonical"} & payload.model_fields_set):
        event_template = await db.get(EventTemplate, step.event_template_id)
        if event_template and event_template.event_type == "weight_check":
            params = changes.get("event_params", step.event_params)
            if params is None:
                weight_parameters(None)
            params = dict(params)
            ingredient = await db.get(Ingredient, step.ingredient_id) if getattr(step, "ingredient_id", None) else None
            linked_weight = getattr(step, "step_type", None) == "ingredient_event" and ingredient is not None and ingredient.measure_type == "weight"
            use_ingredient = params.get("use_ingredient_weight", linked_weight)
            if not isinstance(use_ingredient, bool) or (use_ingredient and not linked_weight):
                raise HTTPException(422, detail="Вес связанного ингредиента доступен только для ингредиентов с мерой «Вес».")
            params["use_ingredient_weight"] = use_ingredient
            if use_ingredient:
                quantity = changes.get("quantity_canonical", step.quantity_canonical)
                if quantity is None:
                    raise HTTPException(422, detail="Укажите положительный вес связанного ингредиента.")
                params["target_weight_g"] = float(quantize_quantity(quantity))
            weight_parameters(params)
            changes["event_params"] = params
    for key, value in changes.items():
        if key == "quantity_canonical" and value is not None:
            value = quantize_quantity(value)
        setattr(step, key, value)
    await db.commit()
    await db.refresh(step, attribute_names=["ingredient", "event_template"])
    return step


async def delete_step(db: AsyncSession, step: RecipeStep) -> None:
    await lock_product_recipe(db, step.product_id)
    await db.delete(step)
    await db.commit()


async def reorder_steps(db: AsyncSession, product_id: uuid.UUID, step_ids: list[uuid.UUID]) -> list[RecipeStep]:
    await lock_product_recipe(db, product_id)
    steps = await load_steps(db, product_id)
    steps_by_id = {s.id: s for s in steps}
    if set(steps_by_id) != set(step_ids):
        raise HTTPException(409, detail="step_ids_do_not_match_product_steps")

    # two-phase: push to a temporary offset first to avoid unique(product_id, order_index) clashes
    offset = max((step.order_index for step in steps), default=0) + len(step_ids) + 1
    for step in steps:
        step.order_index += offset
    await db.flush()

    for position, step_id in enumerate(step_ids):
        steps_by_id[step_id].order_index = position

    await db.commit()
    return await load_steps(db, product_id)
