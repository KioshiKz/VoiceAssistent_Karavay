import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.execution import ExecutionPlan
from app.models.user import User
from app.schemas.execution import ExecutionPlanOut, ExecutionPlanStepOut
from app.services import execution_service
from app.services.unit_conversion import format_compound

router = APIRouter(prefix="/api", tags=["execution"])


def _plan_to_out(plan: ExecutionPlan) -> ExecutionPlanOut:
    steps_out = []
    for s in sorted(plan.steps, key=lambda s: s.order_index):
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
    plan = await execution_service.get_or_create_execution_plan(db, order_line_id)
    return _plan_to_out(plan)


@router.post(
    "/execution-plans/{plan_id}/advance",
    response_model=ExecutionPlanOut,
)
async def advance(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("order.execute")),
):
    plan = await execution_service.advance_step(db, plan_id, user.id)
    return _plan_to_out(plan)


@router.post(
    "/execution-plans/{plan_id}/rewind",
    response_model=ExecutionPlanOut,
)
async def rewind(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("order.execute")),
):
    plan = await execution_service.rewind_step(db, plan_id, user.id)
    return _plan_to_out(plan)
