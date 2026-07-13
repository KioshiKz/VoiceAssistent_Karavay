import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.folder import Folder
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductDetailOut, ProductOut, ProductUpdate
from app.schemas.recipe_step import RecipeStepCreate, RecipeStepOut, RecipeStepReorder, RecipeStepUpdate
from app.services import folder_service, order_access_service, permission_service, recipe_service

router = APIRouter(tags=["products"])


@router.get("/api/folders/{folder_id}/products", response_model=list[ProductOut])
async def list_products(
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.view", folder_param="folder_id")),
):
    result = await db.execute(select(Product).where(Product.folder_id == folder_id))
    return list(result.scalars().all())


@router.get("/api/workshops/{workshop_id}/products", response_model=list[ProductOut])
async def list_workshop_products(
    workshop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workshop = await order_access_service.get_workshop_or_404(db, workshop_id)
    await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")
    return await order_access_service.active_products_in_workshop(db, workshop)


@router.post("/api/folders/{folder_id}/products", response_model=ProductOut, status_code=201)
async def create_product(
    folder_id: uuid.UUID,
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.edit", folder_param="folder_id")),
):
    product = Product(folder_id=folder_id, **payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def _require_product_edit(db: AsyncSession, user: User, product: Product) -> None:
    folder = await folder_service.get_folder_or_404(db, product.folder_id)
    if not await permission_service.has_folder_permission(db, user, "folder.edit", folder):
        raise HTTPException(403, detail="permission_denied")


async def _require_product_view(db: AsyncSession, user: User, product: Product) -> None:
    folder = await folder_service.get_folder_or_404(db, product.folder_id)
    if not await permission_service.has_folder_permission(db, user, "folder.view", folder):
        raise HTTPException(403, detail="permission_denied")


@router.get("/api/products/search", response_model=list[ProductOut])
async def search_products(
    q: str = "",
    workshop_folder_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Used by the manual order-line matcher; registered before /{product_id}
    so the literal 'search' segment isn't swallowed by the dynamic route."""
    from sqlalchemy import func

    stmt = select(Product).join(Folder, Folder.id == Product.folder_id).where(Product.is_active.is_(True))
    if workshop_folder_id is not None:
        workshop = await order_access_service.get_workshop_or_404(db, workshop_folder_id)
        await order_access_service.require_workshop_permission(db, user, workshop, "folder.view")
        stmt = stmt.where(Folder.materialized_path.like(f"{workshop.materialized_path}%"))
    elif not await permission_service.is_system_user(db, user):
        visible_ids = await order_access_service.visible_workshop_ids(db, user)
        if not visible_ids:
            return []
        roots = list(
            (await db.execute(select(Folder).where(Folder.id.in_(visible_ids)))).scalars().all()
        )
        stmt = stmt.where(
            or_(*[Folder.materialized_path.like(f"{root.materialized_path}%") for root in roots])
        )
    if q:
        stmt = stmt.where(func.lower(Product.name).like(f"%{q.lower()}%"))
    result = await db.execute(stmt.order_by(Product.name).limit(20))
    return list(result.scalars().all())


@router.get("/api/products/{product_id}", response_model=ProductDetailOut)
async def get_product(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_view(db, user, product)
    steps = await recipe_service.load_steps(db, product_id)
    return ProductDetailOut(
        id=product.id,
        folder_id=product.folder_id,
        name=product.name,
        base_quantity=product.base_quantity,
        is_active=product.is_active,
        steps=[RecipeStepOut(**recipe_service.step_to_dict(s)) for s in steps],
    )


@router.patch("/api/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_edit(db, user, product)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/api/products/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_edit(db, user, product)
    await db.delete(product)
    await db.commit()


@router.get("/api/products/{product_id}/steps", response_model=list[RecipeStepOut])
async def list_steps(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_view(db, user, product)
    steps = await recipe_service.load_steps(db, product_id)
    return [RecipeStepOut(**recipe_service.step_to_dict(s)) for s in steps]


@router.post("/api/products/{product_id}/steps", response_model=RecipeStepOut, status_code=201)
async def create_step(
    product_id: uuid.UUID,
    payload: RecipeStepCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_edit(db, user, product)
    step = await recipe_service.create_step(db, product_id, payload)
    return RecipeStepOut(**recipe_service.step_to_dict(step))


@router.patch("/api/products/{product_id}/steps/reorder", response_model=list[RecipeStepOut])
async def reorder_steps(
    product_id: uuid.UUID,
    payload: RecipeStepReorder,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_edit(db, user, product)
    steps = await recipe_service.reorder_steps(db, product_id, payload.step_ids)
    return [RecipeStepOut(**recipe_service.step_to_dict(s)) for s in steps]


@router.patch("/api/products/{product_id}/steps/{step_id}", response_model=RecipeStepOut)
async def update_step(
    product_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: RecipeStepUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.recipe_step import RecipeStep

    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_edit(db, user, product)
    step = await db.get(RecipeStep, step_id)
    if step is None or step.product_id != product_id:
        raise HTTPException(404, detail="step_not_found")
    step = await recipe_service.update_step(db, step, payload)
    return RecipeStepOut(**recipe_service.step_to_dict(step))


@router.delete("/api/products/{product_id}/steps/{step_id}", status_code=204)
async def delete_step(
    product_id: uuid.UUID,
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models.recipe_step import RecipeStep

    product = await recipe_service.get_product_or_404(db, product_id)
    await _require_product_edit(db, user, product)
    step = await db.get(RecipeStep, step_id)
    if step is None or step.product_id != product_id:
        raise HTTPException(404, detail="step_not_found")
    await recipe_service.delete_step(db, step)
