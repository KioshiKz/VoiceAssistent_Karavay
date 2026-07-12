import datetime
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.folder import Folder
from app.models.order import Order, OrderLine, OrderLineHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    CurrentOrderOut,
    OrderLineCancel,
    OrderLineHistoryOut,
    OrderLineMatch,
    OrderLineOut,
    OrderLineUpdate,
    OrderUploadOut,
)
from app.services import folder_service, permission_service
from app.services.order_import_service import parse_order_file

router = APIRouter(prefix="/api", tags=["orders"])


async def _match_product(db: AsyncSession, name_raw: str) -> Product | None:
    normalized = name_raw.strip().lower()
    result = await db.execute(
        select(Product).where(func.lower(func.trim(Product.name)) == normalized, Product.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def _can_view_order_queue(db: AsyncSession, user: User) -> bool:
    return (
        await permission_service.has_tab_permission(db, user, "tab.view", "current_order")
        or await permission_service.has_tab_permission(db, user, "tab.view", "execution_queue")
        or await permission_service.has_global_permission(db, user, "order.execute")
    )


async def _visible_workshop_ids(db: AsyncSession, user: User) -> set[uuid.UUID] | None:
    if await permission_service.is_system_user(db, user):
        return None

    result = await db.execute(select(Folder).order_by(Folder.materialized_path))
    visible: set[uuid.UUID] = set()
    for folder in result.scalars().all():
        if await permission_service.has_folder_permission(db, user, "folder.view", folder):
            visible.add(folder.id)
    return visible


async def _role_visibility_ahead(db: AsyncSession, user: User) -> int | None:
    if await permission_service.is_system_user(db, user):
        return None
    if not user.user_roles:
        return 0

    values: list[int | None] = []
    for user_role in user.user_roles:
        if user_role.role is not None:
            values.append(user_role.role.order_visibility_ahead)
    if not values:
        return 0
    if any(value is None for value in values):
        return None
    return max(value for value in values if value is not None)


def _apply_visibility_limit(lines: list[OrderLine], visibility_limit: int | None) -> list[OrderLine]:
    if visibility_limit is None:
        return lines
    if visibility_limit <= 0:
        return []

    visible: list[OrderLine] = []
    active_count = 0
    for line in lines:
        if line.status == "cancelled":
            continue
        if line.status == "completed":
            visible.append(line)
            continue
        if active_count < visibility_limit:
            visible.append(line)
            active_count += 1
    return visible


async def _user_names(db: AsyncSession, user_ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = [user_id for user_id in user_ids if user_id is not None]
    if not ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(ids)))
    return {user.id: user.full_name for user in result.scalars().all()}


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
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        note=note,
    )


def _serialize_line(line: OrderLine) -> dict:
    return {
        "quantity": line.quantity,
        "due_time": line.due_time.isoformat(),
        "matched_product_id": str(line.matched_product_id) if line.matched_product_id else None,
        "match_status": line.match_status,
        "status": line.status,
    }


async def _line_to_out(
    db: AsyncSession,
    line: OrderLine,
    names: dict[uuid.UUID, str] | None = None,
) -> OrderLineOut:
    order = line.__dict__.get("order")
    if order is None:
        order = await db.get(Order, line.order_id, options=[selectinload(Order.workshop_folder)])
    workshop = order.__dict__.get("workshop_folder") if order is not None else None
    if order is not None and workshop is None and order.workshop_folder_id is not None:
        workshop = await db.get(Folder, order.workshop_folder_id)
    if names is None:
        names = await _user_names(db, {line.cancelled_by, line.last_advanced_by})

    return OrderLineOut(
        id=line.id,
        order_id=line.order_id,
        product_name_raw=line.product_name_raw,
        quantity=line.quantity,
        due_time=line.due_time,
        match_status=line.match_status,
        matched_product_id=line.matched_product_id,
        status=line.status,
        cancellation_reason=line.cancellation_reason,
        cancelled_by=line.cancelled_by,
        cancelled_by_name=names.get(line.cancelled_by) if line.cancelled_by else None,
        cancelled_at=line.cancelled_at,
        last_advanced_by=line.last_advanced_by,
        last_advanced_by_name=names.get(line.last_advanced_by) if line.last_advanced_by else None,
        last_advanced_at=line.last_advanced_at,
        workshop_folder_id=order.workshop_folder_id if order is not None else None,
        workshop_folder_name=workshop.name if workshop is not None else None,
    )


@router.post(
    "/orders/upload",
    response_model=OrderUploadOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="upload_order"))],
)
async def upload_order(
    file: UploadFile = File(...),
    execution_date: datetime.date = Form(...),
    workshop_folder_id: uuid.UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if workshop_folder_id is not None:
        workshop = await folder_service.get_folder_or_404(db, workshop_folder_id)
        if not await permission_service.has_folder_permission(db, user, "folder.edit", workshop):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")

    file_bytes = await file.read()
    parsed_lines = parse_order_file(file_bytes)

    order = Order(
        uploaded_by=user.id,
        workshop_folder_id=workshop_folder_id,
        source_filename=file.filename or "order.xlsx",
        execution_date=execution_date,
    )
    db.add(order)
    await db.flush()

    matched_count = 0
    lines_out: list[OrderLine] = []
    for parsed in parsed_lines:
        product = await _match_product(db, parsed.product_name_raw)
        line = OrderLine(
            order_id=order.id,
            row_group_index=parsed.row_group_index,
            product_name_raw=parsed.product_name_raw,
            quantity=parsed.quantity,
            due_time=parsed.due_time,
            matched_product_id=product.id if product else None,
            match_status="matched" if product else "unmatched",
            status="pending",
        )
        if product:
            matched_count += 1
        db.add(line)
        lines_out.append(line)

    await db.commit()
    for line in lines_out:
        await db.refresh(line)

    names: dict[uuid.UUID, str] = {}
    return OrderUploadOut(
        order_id=order.id,
        total_lines=len(lines_out),
        matched=matched_count,
        unmatched=len(lines_out) - matched_count,
        lines=[await _line_to_out(db, line, names) for line in lines_out],
    )


@router.get("/orders/current", response_model=CurrentOrderOut)
async def current_order(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not await _can_view_order_queue(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")

    visible_workshops = await _visible_workshop_ids(db, user)
    orders_stmt = select(Order).options(selectinload(Order.workshop_folder)).order_by(
        Order.execution_date.desc(), Order.uploaded_at.desc()
    )
    if visible_workshops is not None:
        if visible_workshops:
            orders_stmt = orders_stmt.where(
                (Order.workshop_folder_id.is_(None)) | (Order.workshop_folder_id.in_(visible_workshops))
            )
        else:
            orders_stmt = orders_stmt.where(Order.workshop_folder_id.is_(None))

    orders = list((await db.execute(orders_stmt)).scalars().all())
    if not orders:
        raise HTTPException(404, detail="no_orders_uploaded_yet")

    latest_date = orders[0].execution_date
    latest_order_ids = [order.id for order in orders if order.execution_date == latest_date]
    lines_result = await db.execute(
        select(OrderLine)
        .where(OrderLine.order_id.in_(latest_order_ids))
        .options(selectinload(OrderLine.order).selectinload(Order.workshop_folder))
        .order_by(OrderLine.due_time, OrderLine.created_at)
    )
    lines = list(lines_result.scalars().all())

    visibility_limit = await _role_visibility_ahead(db, user)
    lines = _apply_visibility_limit(lines, visibility_limit)

    names = await _user_names(db, {line.cancelled_by for line in lines} | {line.last_advanced_by for line in lines})
    return CurrentOrderOut(
        order_id=latest_order_ids[0],
        execution_date=latest_date,
        lines=[await _line_to_out(db, line, names) for line in lines],
    )


@router.patch(
    "/order-lines/{line_id}/match",
    response_model=OrderLineOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="current_order"))],
)
async def match_order_line(
    line_id: uuid.UUID,
    payload: OrderLineMatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line = await db.get(OrderLine, line_id)
    if line is None:
        raise HTTPException(404, detail="order_line_not_found")
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(404, detail="product_not_found")

    old_value = _serialize_line(line)
    line.matched_product_id = product.id
    line.match_status = "matched"
    db.add(_history(line, user.id, "match", old_value=old_value, new_value=_serialize_line(line)))
    await db.commit()
    await db.refresh(line)
    return await _line_to_out(db, line)


@router.patch(
    "/order-lines/{line_id}",
    response_model=OrderLineOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="current_order"))],
)
async def update_order_line(
    line_id: uuid.UUID,
    payload: OrderLineUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line = await db.get(OrderLine, line_id)
    if line is None:
        raise HTTPException(404, detail="order_line_not_found")
    if line.status == "cancelled":
        raise HTTPException(409, detail="order_line_cancelled")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await _line_to_out(db, line)

    old_value = _serialize_line(line)
    if "quantity" in updates:
        line.quantity = updates["quantity"]
    if "due_time" in updates:
        line.due_time = updates["due_time"]
    if "matched_product_id" in updates:
        product_id = updates["matched_product_id"]
        if product_id is None:
            line.matched_product_id = None
            line.match_status = "unmatched"
        else:
            product = await db.get(Product, product_id)
            if product is None:
                raise HTTPException(404, detail="product_not_found")
            line.matched_product_id = product.id
            line.match_status = "matched"

    db.add(_history(line, user.id, "edit", old_value=old_value, new_value=_serialize_line(line)))
    await db.commit()
    await db.refresh(line)
    return await _line_to_out(db, line)


@router.post(
    "/order-lines/{line_id}/cancel",
    response_model=OrderLineOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="current_order"))],
)
async def cancel_order_line(
    line_id: uuid.UUID,
    payload: OrderLineCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line = await db.get(OrderLine, line_id)
    if line is None:
        raise HTTPException(404, detail="order_line_not_found")
    if line.status == "cancelled":
        return await _line_to_out(db, line)

    old_value = _serialize_line(line)
    line.status = "cancelled"
    line.cancellation_reason = payload.reason.strip()
    line.cancelled_by = user.id
    line.cancelled_at = datetime.datetime.now(datetime.timezone.utc)
    db.add(
        _history(
            line,
            user.id,
            "cancel",
            old_value=old_value,
            new_value=_serialize_line(line),
            note=line.cancellation_reason,
        )
    )
    await db.commit()
    await db.refresh(line)
    return await _line_to_out(db, line)


@router.get(
    "/order-lines/{line_id}/history",
    response_model=list[OrderLineHistoryOut],
    dependencies=[Depends(require_permission("tab.view", tab_key="current_order"))],
)
async def order_line_history(line_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    line = await db.get(OrderLine, line_id)
    if line is None:
        raise HTTPException(404, detail="order_line_not_found")

    result = await db.execute(
        select(OrderLineHistory)
        .where(OrderLineHistory.order_line_id == line_id)
        .order_by(OrderLineHistory.created_at.desc())
    )
    items = list(result.scalars().all())
    names = await _user_names(db, {item.actor_id for item in items})
    return [
        OrderLineHistoryOut(
            id=item.id,
            order_line_id=item.order_line_id,
            actor_id=item.actor_id,
            actor_name=names.get(item.actor_id) if item.actor_id else None,
            event_type=item.event_type,
            old_value=item.old_value,
            new_value=item.new_value,
            note=item.note,
            created_at=item.created_at,
        )
        for item in items
    ]
