import datetime
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import ExecutionPlan, ExecutionPlanStep
from app.models.order import OrderLine
from app.models.product import Product
from app.models.recipe_step import RecipeStep
from app.services.unit_conversion import round_half_up


async def get_or_create_execution_plan(db: AsyncSession, order_line_id: uuid.UUID) -> ExecutionPlan:
    result = await db.execute(
        select(ExecutionPlan)
        .where(ExecutionPlan.order_line_id == order_line_id)
        .options(selectinload(ExecutionPlan.steps))
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    order_line = await db.get(OrderLine, order_line_id)
    if order_line is None:
        raise HTTPException(404, detail="order_line_not_found")
    if order_line.matched_product_id is None:
        raise HTTPException(409, detail="order_line_not_matched_to_a_product")

    product = await db.get(Product, order_line.matched_product_id)
    if product is None:
        raise HTTPException(404, detail="product_not_found")

    steps_result = await db.execute(
        select(RecipeStep)
        .where(RecipeStep.product_id == product.id)
        .options(selectinload(RecipeStep.ingredient), selectinload(RecipeStep.event_template))
        .order_by(RecipeStep.order_index)
    )
    steps = steps_result.scalars().all()

    multiplier = Decimal(order_line.quantity) / Decimal(product.base_quantity)

    plan = ExecutionPlan(order_line_id=order_line.id, product_id=product.id, multiplier=multiplier)
    db.add(plan)
    await db.flush()

    for step in steps:
        if step.step_type == "ingredient":
            computed = round_half_up(float(step.quantity_canonical) * float(multiplier))
            db.add(
                ExecutionPlanStep(
                    execution_plan_id=plan.id,
                    order_index=step.order_index,
                    step_type="ingredient",
                    ingredient_name_snapshot=step.ingredient.name,
                    measure_type_snapshot=step.ingredient.measure_type,
                    quantity_canonical_computed=computed,
                )
            )
        else:
            db.add(
                ExecutionPlanStep(
                    execution_plan_id=plan.id,
                    order_index=step.order_index,
                    step_type="event",
                    event_name_snapshot=step.event_template.name,
                    event_type_snapshot=step.event_template.event_type,
                    event_params_snapshot=step.event_params,
                )
            )

    await db.commit()

    result = await db.execute(
        select(ExecutionPlan).where(ExecutionPlan.id == plan.id).options(selectinload(ExecutionPlan.steps))
    )
    return result.scalar_one()


async def advance_step(db: AsyncSession, plan_id: uuid.UUID) -> ExecutionPlan:
    result = await db.execute(
        select(ExecutionPlan).where(ExecutionPlan.id == plan_id).options(selectinload(ExecutionPlan.steps))
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(404, detail="execution_plan_not_found")
    if plan.status == "completed":
        raise HTTPException(409, detail="execution_plan_already_completed")

    steps_by_index = {s.order_index: s for s in plan.steps}
    current_step = steps_by_index.get(plan.current_step_index)
    if current_step is not None:
        current_step.status = "done"
        current_step.completed_at = datetime.datetime.now(datetime.timezone.utc)

    plan.current_step_index += 1
    plan.status = "completed" if plan.current_step_index >= len(plan.steps) else "in_progress"

    await db.commit()
    await db.refresh(plan)
    return plan
