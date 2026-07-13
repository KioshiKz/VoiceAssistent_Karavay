import datetime
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.execution import ExecutionPlan, ExecutionPlanStep
from app.models.folder import Folder
from app.models.order import CurrentOrderSelection, Order, OrderLine, OrderLineHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    CurrentOrderOut,
    CurrentOrderSelectionIn,
    OrderCreate,
    OrderDetailOut,
    OrderLineCancel,
    OrderLineCreate,
    OrderLineHistoryEntryOut,
    OrderLineHistoryOut,
    OrderLineMatch,
    OrderLineOut,
    OrderLineUpdate,
    OrderSummaryOut,
    OrderUploadOut,
)
from app.services import order_access_service, permission_service
from app.services.order_import_service import parse_order_file

router = APIRouter(prefix="/api", tags=["orders"])


async def _match_product(
    db: AsyncSession,
    name_raw: str,
    workshop: Folder,
) -> Product | None:
    """Match only inside a workshop subtree.

    Duplicate normalized names are intentionally left unmatched so an operator
    can resolve the line explicitly instead of silently choosing the wrong SKU.
    """
    normalized = name_raw.strip().lower()
    result = await db.execute(
        select(Product)
        .join(Folder, Folder.id == Product.folder_id)
        .where(
            func.lower(func.trim(Product.name)) == normalized,
            Product.is_active.is_(True),
            Folder.materialized_path.like(f"{workshop.materialized_path}%"),
        )
        .order_by(Product.created_at, Product.id)
        .limit(2)
    )
    products = list(result.scalars().all())
    return products[0] if len(products) == 1 else None


async def _can_view_order_queue(db: AsyncSession, user: User) -> bool:
    return (
        await permission_service.has_tab_permission(db, user, "tab.view", "current_order")
        or await permission_service.has_tab_permission(db, user, "tab.view", "execution_queue")
        or await permission_service.has_tab_permission(db, user, "tab.view", "orders_list")
        or await permission_service.has_global_permission(db, user, "order.execute")
    )


async def _require_order_edit_permission(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if not (
        await permission_service.has_tab_permission(db, user, "tab.edit", "current_order")
        or await permission_service.has_tab_permission(db, user, "tab.edit", "orders_list")
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")
    return user


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
        order_id=line.order_id,
        product_name_raw=line.product_name_raw,
        actor_id=actor_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
        note=note,
    )


def _serialize_line(line: OrderLine) -> dict:
    return {
        "product_name_raw": line.product_name_raw,
        "quantity": line.quantity,
        "due_time": line.due_time.isoformat(),
        "matched_product_id": str(line.matched_product_id) if line.matched_product_id else None,
        "match_status": line.match_status,
        "status": line.status,
    }


def _order_status(statuses: list[str], force_completed_at: datetime.datetime | None = None) -> str:
    if force_completed_at is not None:
        return "completed"
    if not statuses:
        return "pending"
    active = [line_status for line_status in statuses if line_status != "cancelled"]
    if not active:
        return "completed"
    if all(line_status == "completed" for line_status in active):
        return "completed"
    if any(line_status in {"in_progress", "completed"} for line_status in active):
        return "in_progress"
    return "pending"


async def _lock_order(db: AsyncSession, order_id: uuid.UUID) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order_not_found")
    return order


async def _lock_order_line(db: AsyncSession, order_id: uuid.UUID, line_id: uuid.UUID) -> tuple[Order, OrderLine]:
    order = await _lock_order(db, order_id)
    result = await db.execute(
        select(OrderLine)
        .where(OrderLine.id == line_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    line = result.scalar_one_or_none()
    if line is None or line.order_id != order.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order_line_not_found")
    return order, line


def _ensure_order_not_force_completed(order: Order) -> None:
    if order.force_completed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_force_completed")


async def _ensure_order_not_naturally_completed(db: AsyncSession, order: Order) -> None:
    """Keep an archived order immutable unless it was force-completed.

    Callers hold the order row lock, which serializes line mutations with
    execution and force-completion operations.
    """
    if order.force_completed_at is not None:
        return
    statuses = list(
        (
            await db.execute(
                select(OrderLine.status).where(OrderLine.order_id == order.id)
            )
        ).scalars().all()
    )
    if _order_status(statuses) == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_already_completed")


async def _line_has_execution_plan(db: AsyncSession, line_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(ExecutionPlan.id).where(ExecutionPlan.order_line_id == line_id).limit(1)
    )
    return result.first() is not None


def _current_step_name(plan: ExecutionPlan | None) -> str | None:
    if plan is None or plan.status == "completed":
        return None
    sorted_steps = sorted(plan.steps, key=lambda item: item.order_index)
    if plan.current_step_index < 0 or plan.current_step_index >= len(sorted_steps):
        return None
    step = sorted_steps[plan.current_step_index]
    names = [name for name in (step.ingredient_name_snapshot, step.event_name_snapshot) if name]
    return " / ".join(names) if names else None


async def _plans_by_line(
    db: AsyncSession,
    line_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ExecutionPlan]:
    if not line_ids:
        return {}
    result = await db.execute(
        select(ExecutionPlan)
        .where(ExecutionPlan.order_line_id.in_(line_ids))
        .options(selectinload(ExecutionPlan.steps))
    )
    return {plan.order_line_id: plan for plan in result.scalars().all()}


async def _line_to_out(
    db: AsyncSession,
    line: OrderLine,
    names: dict[uuid.UUID, str] | None = None,
    plan: ExecutionPlan | None = None,
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
        execution_plan_status=plan.status if plan is not None else None,
        current_step_index=plan.current_step_index if plan is not None else None,
        total_steps=len(plan.steps) if plan is not None else 0,
        current_step_name=_current_step_name(plan),
    )


async def _load_order_lines(db: AsyncSession, order_id: uuid.UUID) -> list[OrderLine]:
    result = await db.execute(
        select(OrderLine)
        .where(OrderLine.order_id == order_id)
        .options(selectinload(OrderLine.order).selectinload(Order.workshop_folder))
        .order_by(OrderLine.due_time, OrderLine.created_at)
    )
    return list(result.scalars().all())


async def _order_detail(db: AsyncSession, order: Order) -> OrderDetailOut:
    lines = await _load_order_lines(db, order.id)
    plans = await _plans_by_line(db, [line.id for line in lines])
    names = await _user_names(
        db,
        {order.uploaded_by}
        | {order.force_completed_by}
        | {line.cancelled_by for line in lines}
        | {line.last_advanced_by for line in lines},
    )
    workshop = order.__dict__.get("workshop_folder")
    if workshop is None and order.workshop_folder_id is not None:
        workshop = await db.get(Folder, order.workshop_folder_id)

    return OrderDetailOut(
        order_id=order.id,
        execution_date=order.execution_date,
        source_filename=order.source_filename,
        uploaded_at=order.uploaded_at,
        uploaded_by_name=names.get(order.uploaded_by) if order.uploaded_by else None,
        workshop_folder_id=order.workshop_folder_id,
        workshop_folder_name=workshop.name if workshop is not None else None,
        force_completed_at=order.force_completed_at,
        force_completed_by=order.force_completed_by,
        force_completed_by_name=names.get(order.force_completed_by) if order.force_completed_by else None,
        status=_order_status([line.status for line in lines], order.force_completed_at),
        lines=[await _line_to_out(db, line, names, plans.get(line.id)) for line in lines],
    )


async def _orders_visible_to_user_stmt(db: AsyncSession, user: User):
    root_ids_stmt = select(Folder.id).where(Folder.parent_id.is_(None))
    visible_workshops = await order_access_service.visible_workshop_ids(db, user)
    stmt = select(Order).options(selectinload(Order.workshop_folder))
    if visible_workshops is None:
        return stmt.where(
            (Order.workshop_folder_id.is_(None)) | (Order.workshop_folder_id.in_(root_ids_stmt))
        )
    if not visible_workshops:
        return stmt.where(Order.id.is_(None))
    return stmt.where(Order.workshop_folder_id.in_(visible_workshops))


def _active_order_conditions():
    has_any_line = select(OrderLine.id).where(OrderLine.order_id == Order.id).exists()
    has_unfinished_line = (
        select(OrderLine.id)
        .where(
            OrderLine.order_id == Order.id,
            OrderLine.status.in_(("pending", "in_progress")),
        )
        .exists()
    )
    return (
        Order.force_completed_at.is_(None),
        or_(~has_any_line, has_unfinished_line),
    )


async def _order_summaries(db: AsyncSession, orders: list[Order]) -> list[OrderSummaryOut]:
    order_ids = [order.id for order in orders]
    statuses_by_order: dict[uuid.UUID, list[str]] = defaultdict(list)
    if order_ids:
        rows = await db.execute(
            select(OrderLine.order_id, OrderLine.status).where(OrderLine.order_id.in_(order_ids))
        )
        for order_id, line_status in rows.all():
            statuses_by_order[order_id].append(line_status)

    names = await _user_names(db, {order.uploaded_by for order in orders})
    return [
        OrderSummaryOut(
            id=order.id,
            execution_date=order.execution_date,
            source_filename=order.source_filename,
            uploaded_at=order.uploaded_at,
            uploaded_by_name=names.get(order.uploaded_by) if order.uploaded_by else None,
            workshop_folder_id=order.workshop_folder_id,
            workshop_folder_name=order.workshop_folder.name if order.workshop_folder else None,
            total_lines=len(statuses_by_order.get(order.id, [])),
            active_lines=sum(
                line_status != "cancelled"
                for line_status in statuses_by_order.get(order.id, [])
            ),
            status=_order_status(
                statuses_by_order.get(order.id, []),
                order.force_completed_at,
            ),
        )
        for order in orders
    ]


async def _resolve_current_order(
    db: AsyncSession,
    user: User,
    execution_date: datetime.date,
    workshop: Folder | None,
) -> CurrentOrderOut:
    if workshop is not None:
        stmt = select(Order).where(Order.workshop_folder_id == workshop.id)
    else:
        stmt = await _orders_visible_to_user_stmt(db, user)
    stmt = stmt.where(
        Order.execution_date == execution_date,
        *_active_order_conditions(),
    ).options(selectinload(Order.workshop_folder))

    selection: CurrentOrderSelection | None = None
    order: Order | None = None
    if workshop is not None:
        selection = (
            await db.execute(
                select(CurrentOrderSelection).where(
                    CurrentOrderSelection.workshop_folder_id == workshop.id,
                    CurrentOrderSelection.execution_date == execution_date,
                )
            )
        ).scalar_one_or_none()
        if selection is not None:
            order = (
                await db.execute(stmt.where(Order.id == selection.order_id).limit(1))
            ).scalar_one_or_none()
    else:
        manual_row = (
            await db.execute(
                stmt.join(
                    CurrentOrderSelection,
                    and_(
                        CurrentOrderSelection.order_id == Order.id,
                        CurrentOrderSelection.workshop_folder_id == Order.workshop_folder_id,
                        CurrentOrderSelection.execution_date == Order.execution_date,
                    ),
                )
                .add_columns(CurrentOrderSelection)
                .order_by(
                    CurrentOrderSelection.selected_at.desc(),
                    Order.uploaded_at.asc(),
                    Order.id.asc(),
                )
                .limit(1)
            )
        ).one_or_none()
        if manual_row is not None:
            order, selection = manual_row

    selection_mode = "manual" if order is not None and selection is not None else "automatic"
    if order is None:
        selection = None
        order = (
            await db.execute(
                stmt.order_by(Order.uploaded_at.asc(), Order.id.asc()).limit(1)
            )
        ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_current_order_for_date")

    lines = await _load_order_lines(db, order.id)
    visibility_limit = await _role_visibility_ahead(db, user)
    lines = _apply_visibility_limit(lines, visibility_limit)
    selected_by = selection.selected_by if selection is not None else None
    names = await _user_names(
        db,
        {selected_by}
        | {line.cancelled_by for line in lines}
        | {line.last_advanced_by for line in lines},
    )
    plans = await _plans_by_line(db, [line.id for line in lines])
    selected_workshop = order.workshop_folder
    return CurrentOrderOut(
        order_id=order.id,
        execution_date=order.execution_date,
        workshop_folder_id=order.workshop_folder_id,
        workshop_folder_name=selected_workshop.name if selected_workshop is not None else None,
        selection_mode=selection_mode,
        selected_at=selection.selected_at if selection is not None else None,
        selected_by_name=names.get(selected_by) if selected_by is not None else None,
        lines=[await _line_to_out(db, line, names, plans.get(line.id)) for line in lines],
    )


@router.post(
    "/orders/upload",
    response_model=OrderUploadOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="orders_list"))],
)
async def upload_order(
    file: UploadFile = File(...),
    execution_date: datetime.date = Form(...),
    workshop_folder_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workshop = await order_access_service.get_workshop_or_404(db, workshop_folder_id)
    await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")

    file_bytes = await file.read()
    parsed_lines = parse_order_file(file_bytes)

    order = Order(
        uploaded_by=user.id,
        workshop_folder_id=workshop.id,
        source_filename=file.filename or "order.xlsx",
        execution_date=execution_date,
    )
    db.add(order)
    await db.flush()

    matched_count = 0
    lines_out: list[OrderLine] = []
    for parsed in parsed_lines:
        product = await _match_product(db, parsed.product_name_raw, workshop)
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
        await db.flush()
        db.add(_history(line, user.id, "import", new_value=_serialize_line(line), note=order.source_filename))
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


@router.post(
    "/orders",
    response_model=OrderDetailOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tab.edit", tab_key="orders_list"))],
)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workshop = await order_access_service.get_workshop_or_404(db, payload.workshop_folder_id)
    await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")

    order = Order(
        uploaded_by=user.id,
        workshop_folder_id=workshop.id,
        source_filename=None,
        execution_date=payload.execution_date,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    order.workshop_folder = workshop
    return await _order_detail(db, order)


@router.get("/orders/current", response_model=CurrentOrderOut)
async def current_order(
    workshop_folder_id: uuid.UUID | None = None,
    execution_date: datetime.date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not await _can_view_order_queue(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")

    requested_date = execution_date or datetime.date.today()
    workshop: Folder | None = None
    if workshop_folder_id is not None:
        workshop = await order_access_service.get_workshop_or_404(db, workshop_folder_id)
        await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")
    return await _resolve_current_order(
        db,
        user,
        requested_date,
        workshop,
    )


@router.get("/orders/current/candidates", response_model=list[OrderSummaryOut])
async def current_order_candidates(
    workshop_folder_id: uuid.UUID,
    execution_date: datetime.date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not await _can_view_order_queue(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")

    workshop = await order_access_service.get_workshop_or_404(db, workshop_folder_id)
    await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")
    requested_date = execution_date or datetime.date.today()
    result = await db.execute(
        select(Order)
        .where(
            Order.workshop_folder_id == workshop.id,
            Order.execution_date == requested_date,
            *_active_order_conditions(),
        )
        .options(selectinload(Order.workshop_folder))
        .order_by(Order.uploaded_at.asc(), Order.id.asc())
    )
    return await _order_summaries(db, list(result.scalars().all()))


@router.put(
    "/orders/current/selection",
    response_model=CurrentOrderOut,
    dependencies=[Depends(require_permission("orders.select_current"))],
)
async def set_current_order_selection(
    payload: CurrentOrderSelectionIn,
    workshop_folder_id: uuid.UUID,
    execution_date: datetime.date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not await _can_view_order_queue(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")

    workshop = await order_access_service.get_workshop_or_404(db, workshop_folder_id)
    await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")

    if payload.order_id is None:
        await db.execute(
            delete(CurrentOrderSelection).where(
                CurrentOrderSelection.workshop_folder_id == workshop.id,
                CurrentOrderSelection.execution_date == execution_date,
            )
        )
    else:
        order = await order_access_service.get_order_or_404(db, payload.order_id)
        await order_access_service.require_order_permission(db, user, order, "folder.view")
        if order.workshop_folder_id != workshop.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="order_workshop_mismatch")
        if order.execution_date != execution_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="order_execution_date_mismatch")

        active_order_id = (
            await db.execute(
                select(Order.id).where(
                    Order.id == order.id,
                    *_active_order_conditions(),
                )
            )
        ).scalar_one_or_none()
        if active_order_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="order_not_active")

        insert_stmt = pg_insert(CurrentOrderSelection).values(
            workshop_folder_id=workshop.id,
            execution_date=execution_date,
            order_id=order.id,
            selected_by=user.id,
        )
        await db.execute(
            insert_stmt.on_conflict_do_update(
                index_elements=[
                    CurrentOrderSelection.workshop_folder_id,
                    CurrentOrderSelection.execution_date,
                ],
                set_={
                    "order_id": order.id,
                    "selected_by": user.id,
                    "selected_at": func.now(),
                },
            )
        )

    await db.commit()
    return await _resolve_current_order(db, user, execution_date, workshop)


@router.get(
    "/orders",
    response_model=list[OrderSummaryOut],
    dependencies=[Depends(require_permission("tab.view", tab_key="orders_list"))],
)
async def list_orders(
    workshop_folder_id: uuid.UUID | None = None,
    history: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if history and not await permission_service.has_global_permission(db, user, "order.history.view"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")
    if workshop_folder_id is not None:
        workshop = await order_access_service.get_workshop_or_404(db, workshop_folder_id)
        await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")
        orders_stmt = select(Order).where(Order.workshop_folder_id == workshop.id)
    else:
        orders_stmt = await _orders_visible_to_user_stmt(db, user)

    orders_stmt = orders_stmt.options(selectinload(Order.workshop_folder)).order_by(
        Order.execution_date.desc(), Order.uploaded_at.desc()
    )
    orders = list((await db.execute(orders_stmt)).scalars().all())
    summaries = await _order_summaries(db, orders)
    return [summary for summary in summaries if history == (summary.status == "completed")]


@router.get(
    "/orders/{order_id}",
    response_model=OrderDetailOut,
    dependencies=[Depends(require_permission("tab.view", tab_key="orders_list"))],
)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await db.get(Order, order_id, options=[selectinload(Order.workshop_folder)])
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order_not_found")
    await order_access_service.require_order_permission(db, user, order, "folder.view")
    detail = await _order_detail(db, order)
    if detail.status == "completed" and not await permission_service.has_global_permission(
        db, user, "order.history.view"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")
    return detail


@router.post(
    "/orders/{order_id}/force-complete",
    response_model=OrderDetailOut,
    dependencies=[Depends(require_permission("order.force_complete"))],
)
async def force_complete_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order_result = await db.execute(select(Order).where(Order.id == order_id).with_for_update())
    order = order_result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order_not_found")
    await order_access_service.require_order_permission(db, user, order, "folder.view")
    if order.force_completed_at is not None:
        return await _order_detail(db, order)

    lines_result = await db.execute(
        select(OrderLine).where(OrderLine.order_id == order.id).with_for_update()
    )
    lines = list(lines_result.scalars().all())
    if _order_status([line.status for line in lines]) == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_already_completed")
    line_ids = [line.id for line in lines]
    plans: list[ExecutionPlan] = []
    if line_ids:
        plans = list(
            (
                await db.execute(
                    select(ExecutionPlan)
                    .where(ExecutionPlan.order_line_id.in_(line_ids))
                    .with_for_update()
                )
            ).scalars().all()
        )
    plan_by_line = {plan.order_line_id: plan for plan in plans}

    steps_by_plan: dict[uuid.UUID, list[ExecutionPlanStep]] = defaultdict(list)
    if plans:
        steps_result = await db.execute(
            select(ExecutionPlanStep)
            .where(ExecutionPlanStep.execution_plan_id.in_([plan.id for plan in plans]))
            .order_by(ExecutionPlanStep.order_index)
            .with_for_update()
        )
        for step in steps_result.scalars().all():
            steps_by_plan[step.execution_plan_id].append(step)

    now = datetime.datetime.now(datetime.timezone.utc)
    order.force_completed_at = now
    order.force_completed_by = user.id
    changed_line_count = 0
    for line in lines:
        if line.status in {"cancelled", "completed"}:
            continue
        changed_line_count += 1
        plan = plan_by_line.get(line.id)
        plan_steps = steps_by_plan.get(plan.id, []) if plan is not None else []
        old_value = _serialize_line(line)
        if plan is not None:
            old_value["execution_plan_status"] = plan.status
            old_value["current_step_index"] = plan.current_step_index

        line.status = "completed"
        line.last_advanced_by = user.id
        line.last_advanced_at = now
        if plan is not None:
            for step in plan_steps:
                step.status = "done"
                if step.completed_at is None:
                    step.completed_at = now
            plan.current_step_index = len(plan_steps)
            plan.status = "completed"

        new_value = _serialize_line(line)
        if plan is not None:
            new_value["execution_plan_status"] = plan.status
            new_value["current_step_index"] = plan.current_step_index
        db.add(
            _history(
                line,
                user.id,
                "force_complete",
                old_value=old_value,
                new_value=new_value,
                note="Принудительное завершение заявки",
            )
        )

    if changed_line_count == 0:
        db.add(
            OrderLineHistory(
                order_line_id=None,
                order_id=order.id,
                product_name_raw=None,
                actor_id=user.id,
                event_type="force_complete",
                note="Принудительное завершение пустой заявки",
            )
        )

    await db.commit()
    refreshed = await db.get(Order, order.id, options=[selectinload(Order.workshop_folder)])
    return await _order_detail(db, refreshed)


@router.post(
    "/order-lines",
    response_model=OrderLineOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("order.line.create"))],
)
async def create_order_line(
    payload: OrderLineCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await order_access_service.get_order_or_404(db, payload.order_id)
    workshop = await order_access_service.require_order_permission(db, user, order, "folder.view")
    if workshop is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="legacy_order_has_no_workshop")
    order = await _lock_order(db, order.id)
    _ensure_order_not_force_completed(order)
    await _ensure_order_not_naturally_completed(db, order)

    if payload.matched_product_id is not None:
        product = await order_access_service.get_active_workshop_product_or_404(
            db, payload.matched_product_id, workshop
        )
    else:
        product = await _match_product(db, payload.product_name_raw, workshop)
        if product is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="product_not_available_for_workshop")

    next_group_index = (
        await db.execute(select(func.coalesce(func.max(OrderLine.row_group_index), -1)).where(OrderLine.order_id == order.id))
    ).scalar_one() + 1

    line = OrderLine(
        order_id=order.id,
        row_group_index=next_group_index,
        product_name_raw=product.name,
        quantity=payload.quantity,
        due_time=payload.due_time,
        matched_product_id=product.id,
        match_status="matched",
        status="pending",
    )
    db.add(line)
    await db.flush()
    db.add(_history(line, user.id, "create", new_value=_serialize_line(line)))
    await db.commit()
    await db.refresh(line)
    return await _line_to_out(db, line)


@router.delete(
    "/order-lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("order.line.delete"))],
)
async def delete_order_line(
    line_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line, order, _ = await order_access_service.require_line_permission(db, user, line_id, "folder.view")
    order, line = await _lock_order_line(db, order.id, line.id)
    _ensure_order_not_force_completed(order)
    await _ensure_order_not_naturally_completed(db, order)
    db.add(_history(line, user.id, "delete", old_value=_serialize_line(line)))
    await db.flush()
    await db.delete(line)
    await db.commit()


@router.patch(
    "/order-lines/{line_id}/match",
    response_model=OrderLineOut,
    dependencies=[Depends(_require_order_edit_permission)],
)
async def match_order_line(
    line_id: uuid.UUID,
    payload: OrderLineMatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line, order, workshop = await order_access_service.require_line_permission(db, user, line_id, "folder.view")
    order, line = await _lock_order_line(db, order.id, line.id)
    _ensure_order_not_force_completed(order)
    if line.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_line_cancelled")
    if line.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_line_completed")
    if workshop is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="legacy_order_has_no_workshop")
    if await _line_has_execution_plan(db, line.id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="execution_plan_already_created")
    product = await order_access_service.get_active_workshop_product_or_404(db, payload.product_id, workshop)

    old_value = _serialize_line(line)
    line.product_name_raw = product.name
    line.matched_product_id = product.id
    line.match_status = "matched"
    db.add(_history(line, user.id, "match", old_value=old_value, new_value=_serialize_line(line)))
    await db.commit()
    await db.refresh(line)
    return await _line_to_out(db, line)


@router.patch(
    "/order-lines/{line_id}",
    response_model=OrderLineOut,
    dependencies=[Depends(_require_order_edit_permission)],
)
async def update_order_line(
    line_id: uuid.UUID,
    payload: OrderLineUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line, order, workshop = await order_access_service.require_line_permission(db, user, line_id, "folder.view")
    order, line = await _lock_order_line(db, order.id, line.id)
    _ensure_order_not_force_completed(order)
    if line.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_line_cancelled")
    if line.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_line_completed")
    if workshop is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="legacy_order_has_no_workshop")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await _line_to_out(db, line)

    old_value = _serialize_line(line)
    plan_sensitive_fields = {"product_name_raw", "matched_product_id", "quantity"}
    if plan_sensitive_fields.intersection(updates) and await _line_has_execution_plan(db, line.id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="execution_plan_already_created")
    selected_product: Product | None = None
    if "matched_product_id" in updates and updates["matched_product_id"] is not None:
        selected_product = await order_access_service.get_active_workshop_product_or_404(
            db, updates["matched_product_id"], workshop
        )
    elif "product_name_raw" in updates:
        normalized_new_name = updates["product_name_raw"].strip().lower()
        normalized_current_name = line.product_name_raw.strip().lower()
        if normalized_new_name == normalized_current_name and line.matched_product_id is not None:
            selected_product = await order_access_service.get_active_workshop_product_or_404(
                db, line.matched_product_id, workshop
            )
        else:
            selected_product = await _match_product(db, updates["product_name_raw"], workshop)
            if selected_product is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="product_not_available_for_workshop")

    if selected_product is not None:
        line.product_name_raw = selected_product.name
        line.matched_product_id = selected_product.id
        line.match_status = "matched"
    elif "matched_product_id" in updates and updates["matched_product_id"] is None:
        line.matched_product_id = None
        line.match_status = "unmatched"
    if "quantity" in updates:
        line.quantity = updates["quantity"]
    if "due_time" in updates:
        line.due_time = updates["due_time"]

    db.add(_history(line, user.id, "edit", old_value=old_value, new_value=_serialize_line(line)))
    await db.commit()
    await db.refresh(line)
    return await _line_to_out(db, line)


@router.post(
    "/order-lines/{line_id}/cancel",
    response_model=OrderLineOut,
    dependencies=[Depends(_require_order_edit_permission)],
)
async def cancel_order_line(
    line_id: uuid.UUID,
    payload: OrderLineCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    line, order, _ = await order_access_service.require_line_permission(db, user, line_id, "folder.view")
    order, line = await _lock_order_line(db, order.id, line.id)
    _ensure_order_not_force_completed(order)
    if line.status == "cancelled":
        return await _line_to_out(db, line)
    if line.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="order_line_completed")

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
    dependencies=[Depends(require_permission("order.history.view"))],
)
async def order_line_history(
    line_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await order_access_service.require_line_permission(db, user, line_id, "folder.view")
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


@router.get(
    "/order-line-history",
    response_model=list[OrderLineHistoryEntryOut],
    dependencies=[Depends(require_permission("order.history.view"))],
)
async def list_order_line_history(
    actor_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)

    stmt = select(OrderLineHistory)
    if order_id is not None:
        order = await order_access_service.get_order_or_404(db, order_id)
        await order_access_service.require_order_permission(db, user, order, "folder.view")
        stmt = stmt.where(OrderLineHistory.order_id == order_id)
    else:
        visible_workshops = await order_access_service.visible_workshop_ids(db, user)
        if visible_workshops is not None:
            if not visible_workshops:
                stmt = stmt.where(OrderLineHistory.id.is_(None))
            else:
                stmt = stmt.join(Order, Order.id == OrderLineHistory.order_id).where(
                    Order.workshop_folder_id.in_(visible_workshops)
                )
    if actor_id is not None:
        stmt = stmt.where(OrderLineHistory.actor_id == actor_id)
    if event_type is not None:
        stmt = stmt.where(OrderLineHistory.event_type == event_type)
    stmt = stmt.order_by(OrderLineHistory.created_at.desc()).limit(limit).offset(offset)

    items = list((await db.execute(stmt)).scalars().all())
    names = await _user_names(db, {item.actor_id for item in items})
    order_ids = {item.order_id for item in items if item.order_id is not None}
    exec_dates: dict[uuid.UUID, datetime.date] = {}
    if order_ids:
        dates_result = await db.execute(select(Order.id, Order.execution_date).where(Order.id.in_(order_ids)))
        exec_dates = {row[0]: row[1] for row in dates_result.all()}

    return [
        OrderLineHistoryEntryOut(
            id=item.id,
            order_line_id=item.order_line_id,
            actor_id=item.actor_id,
            actor_name=names.get(item.actor_id) if item.actor_id else None,
            event_type=item.event_type,
            old_value=item.old_value,
            new_value=item.new_value,
            note=item.note,
            created_at=item.created_at,
            order_id=item.order_id,
            product_name_raw=item.product_name_raw,
            execution_date=exec_dates.get(item.order_id) if item.order_id else None,
        )
        for item in items
    ]
