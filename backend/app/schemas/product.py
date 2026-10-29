import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.recipe_step import RecipeStepOut


YieldUnit = Literal["pcs", "kg"]


class ProductCreate(BaseModel):
    name: str
    base_quantity: float
    yield_unit: YieldUnit = "pcs"
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    base_quantity: float | None = None
    yield_unit: YieldUnit | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    name: str
    base_quantity: float
    yield_unit: YieldUnit = "pcs"
    is_active: bool

    model_config = {"from_attributes": True}


class ProductDetailOut(ProductOut):
    steps: list[RecipeStepOut]
