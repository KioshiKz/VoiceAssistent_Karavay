import datetime
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.order import Order, OrderLine
from app.models.product import Product
from app.models.user import User
from app.schemas.order import CurrentOrderOut, OrderLineMatch, OrderLineOut, OrderUploadOut
from app.services.order_import_service import parse_order_file

router = APIRouter(prefix="/api", tags=["orders"])


async def _match_product(db: AsyncSession, name_raw: str) -> Product | None:
    normalized = name_raw.strip().lower()
    result = await db.execute(
        select(Product).where(func.lower(func.trim(Product.name)) == normalized, Product.is_active.is_(True))
    )
    return result.scalar_one_or_none()


@router.post(
    "/orders/upload",
    response_model=OrderUploadOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="upload_order"))],
)
async def upload_order(
    file: UploadFile = File(...),
    execution_date: datetime.date = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_bytes = await file.read()
    parsed_lines = parse_order_file(file_bytes)

    order = Order(uploaded_by=user.id, source_filename=file.filename or "order.xlsx", execution_date=execution_date)
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
        )
        if product:
            matched_count += 1
        db.add(line)
        lines_out.append(line)

    await db.commit()
    for line in lines_out:
        await db.refresh(line)

    return OrderUploadOut(
        order_id=order.id,
        total_lines=len(lines_out),
        matched=matched_count,
        unmatched=len(lines_out) - matched_count,
        lines=[OrderLineOut.model_validate(l) for l in lines_out],
    )


@router.get(
    "/orders/current",
    response_model=CurrentOrderOut,
    dependencies=[Depends(require_permission("tab.view", tab_key="current_order"))],
)
async def current_order(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).order_by(Order.uploaded_at.desc()).limit(1))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(404, detail="no_orders_uploaded_yet")

    lines_result = await db.execute(
        select(OrderLine).where(OrderLine.order_id == order.id).order_by(OrderLine.due_time)
    )
    lines = lines_result.scalars().all()
    return CurrentOrderOut(
        order_id=order.id,
        execution_date=order.execution_date,
        lines=[OrderLineOut.model_validate(l) for l in lines],
    )


@router.patch(
    "/order-lines/{line_id}/match",
    response_model=OrderLineOut,
    dependencies=[Depends(require_permission("tab.edit", tab_key="current_order"))],
)
async def match_order_line(line_id: uuid.UUID, payload: OrderLineMatch, db: AsyncSession = Depends(get_db)):
    line = await db.get(OrderLine, line_id)
    if line is None:
        raise HTTPException(404, detail="order_line_not_found")
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(404, detail="product_not_found")

    line.matched_product_id = product.id
    line.match_status = "matched"
    await db.commit()
    await db.refresh(line)
    return OrderLineOut.model_validate(line)
