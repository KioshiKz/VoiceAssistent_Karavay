import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.ingredient import Ingredient
from app.models.user import User
from app.schemas.ingredient import IngredientCreate, IngredientOut, IngredientUpdate, UsedInProductOut
from app.services import folder_service, ingredient_service

router = APIRouter(tags=["ingredients"])


@router.get("/api/folders/{folder_id}/ingredients", response_model=list[IngredientOut])
async def list_ingredients(
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.view", folder_param="folder_id")),
):
    folder = await folder_service.get_folder_or_404(db, folder_id)
    return await ingredient_service.visible_ingredients(db, folder)


@router.post("/api/folders/{folder_id}/ingredients", response_model=IngredientOut, status_code=201)
async def create_ingredient(
    folder_id: uuid.UUID,
    payload: IngredientCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("folder.edit", folder_param="folder_id")),
):
    ingredient = Ingredient(folder_id=folder_id, **payload.model_dump())
    db.add(ingredient)
    await db.commit()
    await db.refresh(ingredient)
    return ingredient


async def _get_ingredient_or_404(db: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await db.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(404, detail="ingredient_not_found")
    return ingredient


@router.get("/api/ingredients/{ingredient_id}", response_model=IngredientOut)
async def get_ingredient(ingredient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_ingredient_or_404(db, ingredient_id)


@router.patch("/api/ingredients/{ingredient_id}", response_model=IngredientOut)
async def update_ingredient(
    ingredient_id: uuid.UUID,
    payload: IngredientUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ingredient = await _get_ingredient_or_404(db, ingredient_id)
    from app.services import permission_service

    folder = await folder_service.get_folder_or_404(db, ingredient.folder_id)
    if not await permission_service.has_folder_permission(db, user, "folder.edit", folder):
        raise HTTPException(403, detail="permission_denied")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ingredient, key, value)
    await db.commit()
    await db.refresh(ingredient)
    return ingredient


@router.delete("/api/ingredients/{ingredient_id}", status_code=204)
async def delete_ingredient(
    ingredient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services import permission_service
    from app.models.recipe_step import RecipeStep
    from sqlalchemy import select

    ingredient = await _get_ingredient_or_404(db, ingredient_id)
    folder = await folder_service.get_folder_or_404(db, ingredient.folder_id)
    if not await permission_service.has_folder_permission(db, user, "folder.edit", folder):
        raise HTTPException(403, detail="permission_denied")

    referenced = await db.execute(select(RecipeStep.id).where(RecipeStep.ingredient_id == ingredient_id))
    if referenced.first() is not None:
        raise HTTPException(409, detail="ingredient_referenced_by_recipe_steps")

    await db.delete(ingredient)
    await db.commit()


@router.get("/api/ingredients/{ingredient_id}/used-in", response_model=list[UsedInProductOut])
async def used_in(ingredient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await ingredient_service.used_in_products(db, ingredient_id)
