import datetime
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.emergency import EmergencySchedule, EmergencyScheduleHistory
from app.models.order import Order, OrderLine, OrderLineHistory
from app.models.user import User
from app.schemas.statistics import AuditLogOut, ProductStatistics, StatisticsOut, StatisticsSummary
from app.services import emergency_service, permission_service

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


async def _require_statistics_viewer(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    allowed = await permission_service.has_global_permission(db, user, "statistics.view")
    if not allowed:
        allowed = await permission_service.has_global_permission(db, user, "admin.manage")
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")
    return user


@router.get("", response_model=StatisticsOut, dependencies=[Depends(_require_statistics_viewer)])
async def statistics(
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    workshop_folder_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    event_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    order_stmt = select(Order).order_by(Order.execution_date.desc(), Order.uploaded_at.desc())
    if date_from is not None:
        order_stmt = order_stmt.where(Order.execution_date >= date_from)
    if date_to is not None:
        order_stmt = order_stmt.where(Order.execution_date <= date_to)
    if workshop_folder_id is not None:
        order_stmt = order_stmt.where(Order.workshop_folder_id == workshop_folder_id)
    orders = list((await db.execute(order_stmt)).scalars().all())
    order_ids = [order.id for order in orders]
    execution_dates = {order.id: order.execution_date for order in orders}

    lines_by_order: dict[uuid.UUID, list[OrderLine]] = defaultdict(list)
    if order_ids:
        raw_lines = (
            await db.execute(select(OrderLine).where(OrderLine.order_id.in_(order_ids)))
        ).scalars().all()
        for line in raw_lines:
            lines_by_order[line.order_id].append(line)

    effective_lines: list[OrderLine] = []
    for order in orders:
        effective_lines.extend(emergency_service.effective_order_lines(lines_by_order[order.id]))

    product_rows: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "positions": 0,
            "total_quantity": 0,
            "completed": 0,
            "cancelled": 0,
            "emergency_positions": 0,
        }
    )
    for line in effective_lines:
        row = product_rows[line.product_name_raw]
        row["positions"] += 1
        row["total_quantity"] += line.quantity
        row["completed"] += int(line.status == "completed")
        row["cancelled"] += int(line.status == "cancelled")
        row["emergency_positions"] += int(line.emergency_schedule_id is not None)

    schedule_count = 0
    emergency_changes = 0
    if order_ids:
        schedule_count = int(
            await db.scalar(
                select(func.count(EmergencySchedule.id)).where(EmergencySchedule.order_id.in_(order_ids))
            )
            or 0
        )
        emergency_changes = int(
            await db.scalar(
                select(func.count(EmergencyScheduleHistory.id)).where(
                    EmergencyScheduleHistory.order_id.in_(order_ids)
                )
            )
            or 0
        )

    line_log_stmt = select(OrderLineHistory).where(~OrderLineHistory.event_type.like("emergency_%"))
    emergency_log_stmt = select(EmergencyScheduleHistory)
    if order_ids or date_from is not None or date_to is not None or workshop_folder_id is not None:
        line_log_stmt = line_log_stmt.where(OrderLineHistory.order_id.in_(order_ids))
        emergency_log_stmt = emergency_log_stmt.where(EmergencyScheduleHistory.order_id.in_(order_ids))
    if actor_id is not None:
        line_log_stmt = line_log_stmt.where(OrderLineHistory.actor_id == actor_id)
        emergency_log_stmt = emergency_log_stmt.where(EmergencyScheduleHistory.actor_id == actor_id)
    if event_type:
        line_log_stmt = line_log_stmt.where(OrderLineHistory.event_type == event_type)
        emergency_log_stmt = emergency_log_stmt.where(EmergencyScheduleHistory.event_type == event_type)

    line_logs = list((await db.execute(line_log_stmt)).scalars().all())
    emergency_logs = list((await db.execute(emergency_log_stmt)).scalars().all())
    actor_ids = {log.actor_id for log in line_logs + emergency_logs if log.actor_id is not None}
    actor_names = {
        actor.id: actor.full_name
        for actor in (
            await db.execute(select(User).where(User.id.in_(actor_ids)))
            if actor_ids
            else []
        ).scalars().all()
    } if actor_ids else {}

    combined = [
        AuditLogOut(
            id=log.id,
            source="order",
            order_id=log.order_id,
            order_line_id=log.order_line_id,
            product_name_raw=log.product_name_raw,
            execution_date=execution_dates.get(log.order_id) if log.order_id else None,
            actor_id=log.actor_id,
            actor_name=actor_names.get(log.actor_id) if log.actor_id else None,
            event_type=log.event_type,
            old_value=log.old_value,
            new_value=log.new_value,
            note=log.note,
            created_at=log.created_at,
        )
        for log in line_logs
    ] + [
        AuditLogOut(
            id=log.id,
            source="emergency",
            order_id=log.order_id,
            order_line_id=log.order_line_id,
            emergency_schedule_id=log.schedule_id,
            product_name_raw=(log.new_value or log.old_value or {}).get("product_name_raw"),
            execution_date=execution_dates.get(log.order_id) if log.order_id else None,
            actor_id=log.actor_id,
            actor_name=actor_names.get(log.actor_id) if log.actor_id else None,
            event_type=log.event_type,
            old_value=log.old_value,
            new_value=log.new_value,
            note=log.note,
            created_at=log.created_at,
        )
        for log in emergency_logs
    ]
    combined.sort(key=lambda item: item.created_at, reverse=True)
    logs_total = len(combined)

    status_counts = defaultdict(int)
    for line in effective_lines:
        status_counts[line.status] += 1

    return StatisticsOut(
        summary=StatisticsSummary(
            orders=len(orders),
            positions=len(effective_lines),
            pending=status_counts["pending"],
            in_progress=status_counts["in_progress"],
            completed=status_counts["completed"],
            cancelled=status_counts["cancelled"],
            emergency_schedules=schedule_count,
            emergency_changes=emergency_changes,
        ),
        products=[
            ProductStatistics(product_name=name, **values)
            for name, values in sorted(product_rows.items(), key=lambda item: item[0].lower())
        ],
        logs=combined[offset : offset + limit],
        logs_total=logs_total,
    )
