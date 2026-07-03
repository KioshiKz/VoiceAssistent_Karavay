import uuid

from pydantic import BaseModel

from app.schemas.recipe_step import RecipeStepOut


class ProductCreate(BaseModel):
    name: str
    base_quantity: int
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    base_quantity: int | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    name: str
    base_quantity: int
    is_active: bool

    model_config = {"from_attributes": True}


class ProductDetailOut(ProductOut):
    steps: list[RecipeStepOut]
