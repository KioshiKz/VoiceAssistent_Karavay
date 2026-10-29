import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.emergency import EmergencySchedule, EmergencyScheduleHistory
from app.models.execution import ExecutionPlan
from app.models.order import Order, OrderLine, OrderLineHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.emergency import (
    EmergencyAddItem,
    EmergencyItemOut,
    EmergencyItemUpdate,
    EmergencyRemoveItem,
    EmergencyReplaceItem,
    EmergencyScheduleCreate,
    EmergencyScheduleOut,
    EmergencySourceLineOut,
)
from app.services import emergency_service, order_access_service, permission_service
from app.services.quantity_service import normalize_quantity

router = APIRouter(prefix="/api", tags=["emergency schedules"])


async def _require_emergency_manager(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    allowed = await permission_service.has_global_permission(db, user, "emergency.manage")
    if not allowed:
        allowed = await permission_service.has_global_permission(db, user, "admin.manage")
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")
    return user


async def _unit(db: AsyncSession, line: OrderLine) -> str | None:
    if line.matched_product_id is None:
        return None
    product = await db.get(Product, line.matched_product_id)
    return product.yield_unit if product is not None else None


def _touch(schedule: EmergencySchedule) -> None:
    schedule.updated_at = datetime.datetime.now(datetime.timezone.utc)


def _line_snapshot(line: OrderLine) -> dict:
    return {
        "id": str(line.id),
        "product_name_raw": line.product_name_raw,
        "quantity": line.quantity,
        "due_time": line.due_time.isoformat(),
        "matched_product_id": str(line.matched_product_id) if line.matched_product_id else None,
        "match_status": line.match_status,
        "status": line.status,
        "emergency_action": line.emergency_action,
        "emergency_source_line_id": str(line.emergency_source_line_id) if line.emergency_source_line_id else None,
        "emergency_active": line.emergency_active,
    }


def _audit(
    schedule: EmergencySchedule,
    actor_id: uuid.UUID,
    event_type: str,
    *,
    line: OrderLine | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    note: str | None = None,
) -> EmergencyScheduleHistory:
    return EmergencyScheduleHistory(
        schedule_id=schedule.id,
        order_id=schedule.order_id,
        order_line_id=line.id if line else None,
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        note=note,
    )


def _line_history(
    line: OrderLine,
    actor_id: uuid.UUID,
    event_type: str,
    old_value: dict | None,
    new_value: dict | None,
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


async def _schedule_or_404(db: AsyncSession, schedule_id: uuid.UUID) -> EmergencySchedule:
    schedule = await db.get(EmergencySchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="emergency_schedule_not_found")
    return schedule


async def _schedule_for_order_or_404(db: AsyncSession, order_id: uuid.UUID) -> EmergencySchedule:
    schedule = (
        await db.execute(select(EmergencySchedule).where(EmergencySchedule.order_id == order_id))
    ).scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="emergency_schedule_not_found")
    return schedule


async def _raw_lines(db: AsyncSession, order_id: uuid.UUID) -> list[OrderLine]:
    result = await db.execute(
        select(OrderLine)
        .where(OrderLine.order_id == order_id)
        .order_by(OrderLine.due_time, OrderLine.created_at)
    )
    return list(result.scalars().all())


async def _schedule_out(db: AsyncSession, schedule: EmergencySchedule) -> EmergencyScheduleOut:
    lines = await _raw_lines(db, schedule.order_id)
    source_lines = [line for line in lines if line.emergency_schedule_id is None]
    items = [
        line
        for line in lines
        if line.emergency_schedule_id == schedule.id and line.emergency_active
    ]
    overlays = {line.emergency_source_line_id: line for line in items if line.emergency_source_line_id}
    creator = await db.get(User, schedule.created_by) if schedule.created_by else None
    return EmergencyScheduleOut(
        id=schedule.id,
        order_id=schedule.order_id,
        reason=schedule.reason,
        created_by=schedule.created_by,
        created_by_name=creator.full_name if creator else None,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        source_lines=[
            EmergencySourceLineOut(
                id=line.id,
                product_name_raw=line.product_name_raw,
                quantity=line.quantity,
                unit=await _unit(db, line),
                due_time=line.due_time,
                matched_product_id=line.matched_product_id,
                match_status=line.match_status,
                status=line.status,
                overlaid_by_item_id=overlays[line.id].id if line.id in overlays else None,
                overlay_action=overlays[line.id].emergency_action if line.id in overlays else None,
            )
            for line in source_lines
        ],
        items=[
            EmergencyItemOut(
                id=line.id,
                action=line.emergency_action or "add",
                source_line_id=line.emergency_source_line_id,
                product_name_raw=line.product_name_raw,
                quantity=line.quantity,
                unit=await _unit(db, line),
                due_time=line.due_time,
                matched_product_id=line.matched_product_id,
                match_status=line.match_status,
                status=line.status,
                active=line.emergency_active,
            )
            for line in items
        ],
    )


async def _require_schedule_access(
    db: AsyncSession,
    user: User,
    schedule: EmergencySchedule,
) -> Order:
    order = await order_access_service.get_order_or_404(db, schedule.order_id)
    await order_access_service.require_order_permission(db, user, order, "folder.view")
    return order


async def _source_line(db: AsyncSession, schedule: EmergencySchedule, line_id: uuid.UUID) -> OrderLine:
    line = (
        await db.execute(
            select(OrderLine)
            .where(OrderLine.id == line_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if (
        line is None
        or line.order_id != schedule.order_id
        or line.emergency_schedule_id is not None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="source_order_line_not_found")
    if line.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="emergency_source_line_already_started")
    return line


async def _ensure_item_editable(db: AsyncSession, line: OrderLine) -> None:
    plan_id = (
        await db.execute(select(ExecutionPlan.id).where(ExecutionPlan.order_line_id == line.id).limit(1))
    ).scalar_one_or_none()
    if plan_id is not None or line.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="emergency_item_already_started")


async def _find_source_overlay(
    db: AsyncSession,
    schedule: EmergencySchedule,
    source_line_id: uuid.UUID,
) -> OrderLine | None:
    return (
        await db.execute(
            select(OrderLine).where(
                OrderLine.emergency_schedule_id == schedule.id,
                OrderLine.emergency_source_line_id == source_line_id,
            )
        )
    ).scalar_one_or_none()


async def _next_row_index(db: AsyncSession, order_id: uuid.UUID) -> int:
    current = await db.scalar(select(func.max(OrderLine.row_group_index)).where(OrderLine.order_id == order_id))
    return int(current or 0) + 1


@router.get("/orders/{order_id}/emergency-schedule", response_model=EmergencyScheduleOut)
async def get_emergency_schedule(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await order_access_service.get_order_or_404(db, order_id)
    await order_access_service.require_order_permission(db, user, order, "folder.view")
    return await _schedule_out(db, await _schedule_for_order_or_404(db, order_id))


@router.post(
    "/orders/{order_id}/emergency-schedule",
    response_model=EmergencyScheduleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_emergency_manager)],
)
async def create_emergency_schedule(
    order_id: uuid.UUID,
    payload: EmergencyScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await order_access_service.get_order_or_404(db, order_id)
    await order_access_service.require_order_permission(db, user, order, "folder.view")
    if order.force_completed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_already_completed")
    existing = (
        await db.execute(select(EmergencySchedule).where(EmergencySchedule.order_id == order.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="emergency_schedule_already_exists")
    effective = emergency_service.effective_order_lines(await _raw_lines(db, order.id))
    if effective and all(line.status in {"completed", "cancelled"} for line in effective):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_already_completed")

    schedule = EmergencySchedule(order_id=order.id, reason=payload.reason.strip(), created_by=user.id)
    db.add(schedule)
    await db.flush()
    db.add(
        _audit(
            schedule,
            user.id,
            "emergency_schedule_started",
            new_value={"reason": schedule.reason},
        )
    )
    await db.commit()
    await db.refresh(schedule)
    return await _schedule_out(db, schedule)


@router.post(
    "/emergency-schedules/{schedule_id}/items/add",
    response_model=EmergencyScheduleOut,
    dependencies=[Depends(_require_emergency_manager)],
)
async def add_emergency_item(
    schedule_id: uuid.UUID,
    payload: EmergencyAddItem,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id)
    order = await _require_schedule_access(db, user, schedule)
    if order.force_completed_at is not None or order.workshop_folder_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_already_completed")
    workshop = await order_access_service.get_workshop_or_404(db, order.workshop_folder_id)
    product = await order_access_service.get_active_workshop_product_or_404(db, payload.product_id, workshop)
    line = OrderLine(
        order_id=order.id,
        row_group_index=await _next_row_index(db, order.id),
        product_name_raw=product.name,
        quantity=normalize_quantity(payload.quantity, product.yield_unit),
        due_time=payload.due_time,
        matched_product_id=product.id,
        match_status="matched",
        status="pending",
        emergency_schedule_id=schedule.id,
        emergency_action="add",
        emergency_active=True,
    )
    db.add(line)
    await db.flush()
    snapshot = _line_snapshot(line)
    db.add(_line_history(line, user.id, "emergency_item_added", None, snapshot))
    db.add(_audit(schedule, user.id, "emergency_item_added", line=line, new_value=snapshot))
    _touch(schedule)
    await db.commit()
    await db.refresh(schedule)
    return await _schedule_out(db, schedule)


@router.post(
    "/emergency-schedules/{schedule_id}/items/replace",
    response_model=EmergencyScheduleOut,
    dependencies=[Depends(_require_emergency_manager)],
)
async def replace_emergency_item(
    schedule_id: uuid.UUID,
    payload: EmergencyReplaceItem,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id)
    await _require_schedule_access(db, user, schedule)
    source = await _source_line(db, schedule, payload.source_line_id)
    quantity = normalize_quantity(payload.quantity, await _unit(db, source))
    line = await _find_source_overlay(db, schedule, source.id)
    if line is None:
        line = OrderLine(
            order_id=source.order_id,
            row_group_index=await _next_row_index(db, source.order_id),
            product_name_raw=source.product_name_raw,
            quantity=quantity,
            due_time=payload.due_time or source.due_time,
            matched_product_id=source.matched_product_id,
            match_status=source.match_status,
            status="pending",
            emergency_schedule_id=schedule.id,
            emergency_source_line_id=source.id,
            emergency_action="replace",
            emergency_active=True,
        )
        db.add(line)
        await db.flush()
        old = None
    else:
        await _ensure_item_editable(db, line)
        old = _line_snapshot(line)
        line.quantity = quantity
        line.due_time = payload.due_time or source.due_time
        line.emergency_action = "replace"
        line.emergency_active = True
        line.status = "pending"
    snapshot = _line_snapshot(line)
    db.add(_line_history(line, user.id, "emergency_quantity_replaced", old, snapshot))
    db.add(_audit(schedule, user.id, "emergency_quantity_replaced", line=line, old_value=old, new_value=snapshot))
    _touch(schedule)
    await db.commit()
    await db.refresh(schedule)
    return await _schedule_out(db, schedule)


@router.post(
    "/emergency-schedules/{schedule_id}/items/remove",
    response_model=EmergencyScheduleOut,
    dependencies=[Depends(_require_emergency_manager)],
)
async def remove_source_item(
    schedule_id: uuid.UUID,
    payload: EmergencyRemoveItem,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id)
    await _require_schedule_access(db, user, schedule)
    source = await _source_line(db, schedule, payload.source_line_id)
    line = await _find_source_overlay(db, schedule, source.id)
    if line is None:
        line = OrderLine(
            order_id=source.order_id,
            row_group_index=await _next_row_index(db, source.order_id),
            product_name_raw=source.product_name_raw,
            quantity=source.quantity,
            due_time=source.due_time,
            matched_product_id=source.matched_product_id,
            match_status=source.match_status,
            status="pending",
            emergency_schedule_id=schedule.id,
            emergency_source_line_id=source.id,
            emergency_action="remove",
            emergency_active=True,
        )
        db.add(line)
        await db.flush()
        old = None
    else:
        await _ensure_item_editable(db, line)
        old = _line_snapshot(line)
        line.emergency_action = "remove"
        line.emergency_active = True
        line.status = "pending"
    snapshot = _line_snapshot(line)
    db.add(_line_history(line, user.id, "emergency_item_removed", old, snapshot, payload.note))
    db.add(
        _audit(
            schedule,
            user.id,
            "emergency_item_removed",
            line=line,
            old_value=old,
            new_value=snapshot,
            note=payload.note,
        )
    )
    _touch(schedule)
    await db.commit()
    await db.refresh(schedule)
    return await _schedule_out(db, schedule)


@router.patch(
    "/emergency-schedules/{schedule_id}/items/{line_id}",
    response_model=EmergencyScheduleOut,
    dependencies=[Depends(_require_emergency_manager)],
)
async def update_emergency_item(
    schedule_id: uuid.UUID,
    line_id: uuid.UUID,
    payload: EmergencyItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id)
    await _require_schedule_access(db, user, schedule)
    line = (
        await db.execute(
            select(OrderLine)
            .where(OrderLine.id == line_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if line is None or line.emergency_schedule_id != schedule.id or not line.emergency_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="emergency_item_not_found")
    if line.emergency_action not in {"add", "replace"}:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="emergency_remove_marker_not_editable")
    await _ensure_item_editable(db, line)
    old = _line_snapshot(line)
    changes = payload.model_dump(exclude_unset=True)
    if "quantity" in changes:
        changes["quantity"] = normalize_quantity(changes["quantity"], await _unit(db, line))
    for key, value in changes.items():
        setattr(line, key, value)
    snapshot = _line_snapshot(line)
    db.add(_line_history(line, user.id, "emergency_item_updated", old, snapshot))
    db.add(_audit(schedule, user.id, "emergency_item_updated", line=line, old_value=old, new_value=snapshot))
    _touch(schedule)
    await db.commit()
    await db.refresh(schedule)
    return await _schedule_out(db, schedule)


@router.delete(
    "/emergency-schedules/{schedule_id}/items/{line_id}",
    response_model=EmergencyScheduleOut,
    dependencies=[Depends(_require_emergency_manager)],
)
async def restore_emergency_item(
    schedule_id: uuid.UUID,
    line_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id)
    await _require_schedule_access(db, user, schedule)
    line = (
        await db.execute(
            select(OrderLine)
            .where(OrderLine.id == line_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if line is None or line.emergency_schedule_id != schedule.id or not line.emergency_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="emergency_item_not_found")
    await _ensure_item_editable(db, line)
    old = _line_snapshot(line)
    line.emergency_active = False
    snapshot = _line_snapshot(line)
    db.add(_line_history(line, user.id, "emergency_item_restored", old, snapshot))
    db.add(_audit(schedule, user.id, "emergency_item_restored", line=line, old_value=old, new_value=snapshot))
    _touch(schedule)
    await db.commit()
    await db.refresh(schedule)
    return await _schedule_out(db, schedule)
