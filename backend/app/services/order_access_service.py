import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.order import Order, OrderLine
from app.models.product import Product
from app.models.user import User
from app.services import permission_service


async def get_workshop_or_404(db: AsyncSession, workshop_id: uuid.UUID) -> Folder:
    workshop = await db.get(Folder, workshop_id)
    if workshop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="workshop_not_found")
    if workshop.parent_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="folder_is_not_workshop")
    return workshop


async def require_workshop_permission(
    db: AsyncSession,
    user: User,
    workshop: Folder,
    code: str,
) -> None:
    if not await permission_service.has_folder_permission(db, user, code, workshop):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")


async def require_workshop_permissions(
    db: AsyncSession,
    user: User,
    workshop: Folder,
    *codes: str,
) -> None:
    for code in codes:
        await require_workshop_permission(db, user, workshop, code)


async def get_order_or_404(db: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order_not_found")
    return order


async def require_order_permission(
    db: AsyncSession,
    user: User,
    order: Order,
    code: str,
) -> Folder | None:
    if order.workshop_folder_id is None:
        if await permission_service.is_system_user(db, user):
            return None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")

    workshop = await get_workshop_or_404(db, order.workshop_folder_id)
    await require_workshop_permission(db, user, workshop, code)
    return workshop


async def require_order_permissions(
    db: AsyncSession,
    user: User,
    order: Order,
    *codes: str,
) -> Folder | None:
    workshop: Folder | None = None
    for code in codes:
        workshop = await require_order_permission(db, user, order, code)
    return workshop


async def get_line_and_order(db: AsyncSession, line_id: uuid.UUID) -> tuple[OrderLine, Order]:
    line = await db.get(OrderLine, line_id)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="order_line_not_found")
    order = await get_order_or_404(db, line.order_id)
    return line, order


async def require_line_permission(
    db: AsyncSession,
    user: User,
    line_id: uuid.UUID,
    code: str,
) -> tuple[OrderLine, Order, Folder | None]:
    line, order = await get_line_and_order(db, line_id)
    workshop = await require_order_permission(db, user, order, code)
    return line, order, workshop


async def visible_workshop_ids(db: AsyncSession, user: User) -> set[uuid.UUID] | None:
    if await permission_service.is_system_user(db, user):
        return None

    result = await db.execute(select(Folder).where(Folder.parent_id.is_(None)).order_by(Folder.materialized_path))
    visible: set[uuid.UUID] = set()
    for workshop in result.scalars().all():
        if await permission_service.has_folder_permission(db, user, "folder.view", workshop):
            visible.add(workshop.id)
    return visible


def product_is_in_workshop(product_folder: Folder, workshop: Folder) -> bool:
    return product_folder.materialized_path.startswith(workshop.materialized_path)


async def get_active_workshop_product_or_404(
    db: AsyncSession,
    product_id: uuid.UUID,
    workshop: Folder,
) -> Product:
    product = await db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product_not_found")
    product_folder = await db.get(Folder, product.folder_id)
    if product_folder is None or not product_is_in_workshop(product_folder, workshop):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="product_not_available_for_workshop")
    return product


async def active_products_in_workshop(db: AsyncSession, workshop: Folder) -> list[Product]:
    result = await db.execute(
        select(Product)
        .join(Folder, Folder.id == Product.folder_id)
        .where(
            Product.is_active.is_(True),
            Folder.materialized_path.like(f"{workshop.materialized_path}%"),
        )
        .order_by(Product.name, Product.created_at)
    )
    return list(result.scalars().all())
