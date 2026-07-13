import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.execution import ExecutionPlan
from app.models.user import User
from app.schemas.execution import ExecutionPlanOut, ExecutionPlanStepOut
from app.services import execution_service, order_access_service, permission_service
from app.services.unit_conversion import format_compound

router = APIRouter(prefix="/api", tags=["execution"])


def _plan_to_out(plan: ExecutionPlan, can_view_full_recipe: bool) -> ExecutionPlanOut:
    steps_out = []
    sorted_steps = sorted(plan.steps, key=lambda s: s.order_index)
    total_steps = len(sorted_steps)
    if can_view_full_recipe or plan.status == "completed":
        visible_steps = sorted_steps
    else:
        visible_count = min(plan.current_step_index + 1, total_steps)
        visible_steps = sorted_steps[:visible_count]

    for s in visible_steps:
        quantity_display = None
        if s.step_type in {"ingredient", "ingredient_event"} and s.quantity_canonical_computed is not None:
            quantity_display = format_compound(s.quantity_canonical_computed, s.measure_type_snapshot)
        steps_out.append(
            ExecutionPlanStepOut(
                order_index=s.order_index,
                step_type=s.step_type,
                ingredient_name_snapshot=s.ingredient_name_snapshot,
                measure_type_snapshot=s.measure_type_snapshot,
                quantity_canonical_computed=s.quantity_canonical_computed,
                quantity_display=quantity_display,
                event_name_snapshot=s.event_name_snapshot,
                event_type_snapshot=s.event_type_snapshot,
                event_params_snapshot=s.event_params_snapshot,
                status=s.status,
                completed_at=s.completed_at,
            )
        )
    return ExecutionPlanOut(
        id=plan.id,
        order_line_id=plan.order_line_id,
        product_id=plan.product_id,
        multiplier=float(plan.multiplier),
        status=plan.status,
        current_step_index=plan.current_step_index,
        total_steps=total_steps,
        can_view_full_recipe=can_view_full_recipe,
        steps=steps_out,
    )


@router.get(
    "/order-lines/{order_line_id}/execution-plan",
    response_model=ExecutionPlanOut,
)
async def get_execution_plan(
    order_line_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("order.execute")),
):
    await order_access_service.require_line_permission(db, user, order_line_id, "folder.view")
    plan = await execution_service.get_or_create_execution_plan(db, order_line_id)
    can_view_full_recipe = await permission_service.has_global_permission(db, user, "recipe.full_view")
    return _plan_to_out(plan, can_view_full_recipe)


@router.post(
    "/execution-plans/{plan_id}/advance",
    response_model=ExecutionPlanOut,
)
async def advance(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("order.execute")),
):
    existing = await db.get(ExecutionPlan, plan_id)
    if existing is None:
        raise HTTPException(404, detail="execution_plan_not_found")
    await order_access_service.require_line_permission(db, user, existing.order_line_id, "folder.view")
    plan = await execution_service.advance_step(db, plan_id, user.id)
    can_view_full_recipe = await permission_service.has_global_permission(db, user, "recipe.full_view")
    return _plan_to_out(plan, can_view_full_recipe)


@router.post(
    "/execution-plans/{plan_id}/rewind",
    response_model=ExecutionPlanOut,
)
async def rewind(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("order.execute")),
):
    existing = await db.get(ExecutionPlan, plan_id)
    if existing is None:
        raise HTTPException(404, detail="execution_plan_not_found")
    await order_access_service.require_line_permission(db, user, existing.order_line_id, "folder.view")
    plan = await execution_service.rewind_step(db, plan_id, user.id)
    can_view_full_recipe = await permission_service.has_global_permission(db, user, "recipe.full_view")
    return _plan_to_out(plan, can_view_full_recipe)
