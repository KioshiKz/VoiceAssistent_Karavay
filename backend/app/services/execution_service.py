import datetime
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import ExecutionPlan, ExecutionPlanStep
from app.models.order import Order, OrderLine, OrderLineHistory
from app.models.product import Product
from app.models.recipe_step import RecipeStep
from app.services.unit_conversion import quantize_quantity
from app.services.scale_service import scale_service


def execution_event_params(event_type: str | None, values: dict | None, multiplier: Decimal,
                           ingredient_weight: Decimal | None = None) -> dict | None:
    if event_type != "weight_check":
        return values
    params = dict(values or {})
    if params.get("weight_target_basis") == "batch":
        return params
    if ingredient_weight is not None and params.get("use_ingredient_weight", True):
        target = ingredient_weight
        params["use_ingredient_weight"] = True
    else:
        base = Decimal(str(params.get("target_weight_g", 0)))
        params["target_weight_base_g"] = float(base)
        target = quantize_quantity(base * multiplier)
    params["target_weight_g"] = float(target)
    params["weight_target_basis"] = "batch"
    return params


def normalize_plan_weight_targets(plan: ExecutionPlan) -> bool:
    changed = False
    target_changed = False
    for step in plan.steps:
        if step.status == "done" or step.event_type_snapshot != "weight_check":
            continue
        linked_weight = step.quantity_canonical_computed if getattr(step, "step_type", None) == "ingredient_event" and getattr(step, "measure_type_snapshot", None) == "weight" else None
        params = execution_event_params(step.event_type_snapshot, step.event_params_snapshot,
                                       Decimal(str(getattr(plan, "multiplier", 1))), linked_weight)
        if params != step.event_params_snapshot:
            target_changed = target_changed or params.get("target_weight_g") != (step.event_params_snapshot or {}).get("target_weight_g")
            step.event_params_snapshot = params
            changed = True
    if target_changed:
        scale_service.reset_plan(str(plan.id))
    return changed


async def get_or_create_execution_plan(db: AsyncSession, order_line_id: uuid.UUID) -> ExecutionPlan:
    line_ref = await db.get(OrderLine, order_line_id)
    if line_ref is None:
        raise HTTPException(404, detail="order_line_not_found")
    if line_ref.emergency_schedule_id is not None and (
        not line_ref.emergency_active or line_ref.emergency_action == "remove"
    ):
        raise HTTPException(409, detail="emergency_order_line_not_executable")
    if line_ref.emergency_schedule_id is None:
        overlay_id = await db.scalar(
            select(OrderLine.id)
            .where(
                OrderLine.emergency_source_line_id == line_ref.id,
                OrderLine.emergency_active.is_(True),
                OrderLine.emergency_action.in_(("replace", "remove")),
            )
            .limit(1)
        )
        if overlay_id is not None:
            raise HTTPException(409, detail="order_line_replaced_by_emergency_schedule")

    result = await db.execute(
        select(ExecutionPlan)
        .where(ExecutionPlan.order_line_id == order_line_id)
        .options(selectinload(ExecutionPlan.steps))
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if normalize_plan_weight_targets(existing):
            await db.commit()
        return existing

    order_result = await db.execute(
        select(Order)
        .where(Order.id == line_ref.order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        raise HTTPException(404, detail="order_not_found")
    if order.force_completed_at is not None:
        raise HTTPException(409, detail="order_force_completed")
    line_result = await db.execute(
        select(OrderLine)
        .where(OrderLine.id == order_line_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    order_line = line_result.scalar_one_or_none()
    if order_line is None:
        raise HTTPException(404, detail="order_line_not_found")

    # A concurrent get-or-create waits on the line lock, then observes the plan
    # produced by the first transaction instead of violating the unique key.
    existing_result = await db.execute(
        select(ExecutionPlan)
        .where(ExecutionPlan.order_line_id == order_line_id)
        .options(selectinload(ExecutionPlan.steps))
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if normalize_plan_weight_targets(existing):
            await db.commit()
        return existing
    if order_line.status == "cancelled":
        raise HTTPException(409, detail="order_line_cancelled")
    if order_line.status == "completed":
        raise HTTPException(409, detail="order_line_already_completed")
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
        if step.step_type in {"ingredient", "ingredient_event"}:
            computed = quantize_quantity(Decimal(step.quantity_canonical) * multiplier)
            plan_step = ExecutionPlanStep(
                execution_plan_id=plan.id,
                order_index=step.order_index,
                step_type=step.step_type,
                ingredient_name_snapshot=step.ingredient.name,
                measure_type_snapshot=step.ingredient.measure_type,
                quantity_canonical_computed=computed,
            )
            if step.step_type == "ingredient_event":
                plan_step.event_name_snapshot = step.event_template.name
                plan_step.event_type_snapshot = step.event_template.event_type
                plan_step.event_params_snapshot = execution_event_params(
                    step.event_template.event_type, step.event_params, multiplier,
                    computed if step.ingredient.measure_type == "weight" else None)
            db.add(plan_step)
        else:
            db.add(
                ExecutionPlanStep(
                    execution_plan_id=plan.id,
                    order_index=step.order_index,
                    step_type="event",
                    event_name_snapshot=step.event_template.name,
                    event_type_snapshot=step.event_template.event_type,
                    event_params_snapshot=execution_event_params(step.event_template.event_type, step.event_params, multiplier),
                )
            )

    await db.commit()

    result = await db.execute(
        select(ExecutionPlan).where(ExecutionPlan.id == plan.id).options(selectinload(ExecutionPlan.steps))
    )
    return result.scalar_one()


def _history(
    line: OrderLine,
    actor_id: uuid.UUID | None,
    event_type: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    note: str | None = None,
) -> OrderLineHistory:
    return OrderLineHistory(
        order_line_id=line.id,
        order_id=line.order_id,
        product_name_raw=line.product_name_raw,
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        note=note,
    )


async def _lock_plan_context(
    db: AsyncSession,
    plan_id: uuid.UUID,
) -> tuple[ExecutionPlan, OrderLine, Order]:
    plan_ref = await db.get(ExecutionPlan, plan_id)
    if plan_ref is None:
        raise HTTPException(404, detail="execution_plan_not_found")
    line_ref = await db.get(OrderLine, plan_ref.order_line_id)
    if line_ref is None:
        raise HTTPException(404, detail="order_line_not_found")

    # Keep the same lock order as force-complete: order -> line -> plan -> steps.
    order_result = await db.execute(
        select(Order)
        .where(Order.id == line_ref.order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        raise HTTPException(404, detail="order_not_found")
    line_result = await db.execute(
        select(OrderLine)
        .where(OrderLine.id == line_ref.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    order_line = line_result.scalar_one_or_none()
    if order_line is None:
        raise HTTPException(404, detail="order_line_not_found")

    plan_result = await db.execute(
        select(ExecutionPlan)
        .where(ExecutionPlan.id == plan_id)
        .options(selectinload(ExecutionPlan.steps))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(404, detail="execution_plan_not_found")
    await db.execute(
        select(ExecutionPlanStep.id)
        .where(ExecutionPlanStep.execution_plan_id == plan.id)
        .with_for_update()
    )
    return plan, order_line, order


async def advance_step(db: AsyncSession, plan_id: uuid.UUID, actor_id: uuid.UUID | None) -> ExecutionPlan:
    plan, order_line, order = await _lock_plan_context(db, plan_id)
    if order.force_completed_at is not None:
        raise HTTPException(409, detail="order_force_completed")
    if plan.status == "completed":
        raise HTTPException(409, detail="execution_plan_already_completed")
    if order_line.status == "cancelled":
        raise HTTPException(409, detail="order_line_cancelled")

    normalize_plan_weight_targets(plan)
    sorted_steps = sorted(plan.steps, key=lambda step: step.order_index)
    current_step = (
        sorted_steps[plan.current_step_index]
        if 0 <= plan.current_step_index < len(sorted_steps)
        else None
    )
    weight_verification = None
    if current_step is not None and current_step.event_type_snapshot == "weight_check":
        weight_verification = scale_service.require_ready(
            str(plan.id), plan.current_step_index, current_step.event_params_snapshot
        )
    if current_step is not None:
        current_step.status = "done"
        current_step.completed_at = datetime.datetime.now(datetime.timezone.utc)

    plan.current_step_index += 1
    plan.status = "completed" if plan.current_step_index >= len(sorted_steps) else "in_progress"
    order_line.status = "completed" if plan.status == "completed" else "in_progress"
    order_line.last_advanced_by = actor_id
    order_line.last_advanced_at = datetime.datetime.now(datetime.timezone.utc)
    db.add(
        _history(
            order_line,
            actor_id,
            "advance",
            old_value={"current_step_index": plan.current_step_index - 1},
            new_value={
                "current_step_index": plan.current_step_index, "status": order_line.status,
                **({"weight_verification": weight_verification} if weight_verification else {}),
            },
        )
    )

    await db.commit()
    scale_service.reset_plan(str(plan.id))
    await db.refresh(plan)
    return plan


async def rewind_step(db: AsyncSession, plan_id: uuid.UUID, actor_id: uuid.UUID | None) -> ExecutionPlan:
    plan, order_line, order = await _lock_plan_context(db, plan_id)
    if order.force_completed_at is not None:
        raise HTTPException(409, detail="order_force_completed")
    if plan.status == "completed":
        raise HTTPException(409, detail="execution_plan_already_completed")
    if order_line.status == "completed":
        raise HTTPException(409, detail="order_line_completed")
    if plan.current_step_index <= 0:
        raise HTTPException(409, detail="execution_plan_at_first_step")
    if order_line.status == "cancelled":
        raise HTTPException(409, detail="order_line_cancelled")
    forced = await db.execute(
        select(OrderLineHistory.id)
        .where(
            OrderLineHistory.order_line_id == order_line.id,
            OrderLineHistory.event_type == "force_complete",
        )
        .limit(1)
    )
    if forced.first() is not None:
        raise HTTPException(409, detail="order_line_force_completed")

    previous_index = plan.current_step_index
    plan.current_step_index -= 1
    sorted_steps = sorted(plan.steps, key=lambda item: item.order_index)
    step = (
        sorted_steps[plan.current_step_index]
        if 0 <= plan.current_step_index < len(sorted_steps)
        else None
    )
    if step is not None:
        step.status = "pending"
        step.completed_at = None

    plan.status = "in_progress" if plan.steps else "completed"
    order_line.status = "in_progress"
    order_line.last_advanced_by = actor_id
    order_line.last_advanced_at = datetime.datetime.now(datetime.timezone.utc)
    db.add(
        _history(
            order_line,
            actor_id,
            "rewind",
            old_value={"current_step_index": previous_index},
            new_value={"current_step_index": plan.current_step_index, "status": order_line.status},
        )
    )

    await db.commit()
    scale_service.reset_plan(str(plan.id))
    await db.refresh(plan)
    return plan
