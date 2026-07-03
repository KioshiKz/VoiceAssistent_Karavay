import uuid

from pydantic import BaseModel, Field


class IngredientCreate(BaseModel):
    name: str
    measure_type: str = Field(pattern="^(weight|volume|time|temperature)$")
    description: str | None = None
    allowed_container_weights_g: list[int] | None = None
    is_active: bool = True


class IngredientUpdate(BaseModel):
    name: str | None = None
    measure_type: str | None = Field(default=None, pattern="^(weight|volume|time|temperature)$")
    description: str | None = None
    allowed_container_weights_g: list[int] | None = None
    is_active: bool | None = None


class IngredientOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    name: str
    measure_type: str
    description: str | None
    allowed_container_weights_g: list[int] | None
    is_active: bool

    model_config = {"from_attributes": True}


class UsedInProductOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    folder_path: str
