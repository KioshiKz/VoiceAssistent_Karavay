import uuid

from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class FolderRename(BaseModel):
    name: str


class FolderMove(BaseModel):
    parent_id: uuid.UUID | None = None


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class BreadcrumbOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class FolderPermissionsOut(BaseModel):
    view: bool
    create: bool
    edit: bool


class IngredientBrief(BaseModel):
    id: uuid.UUID
    name: str
    measure_type: str
    is_active: bool

    model_config = {"from_attributes": True}


class ProductBrief(BaseModel):
    id: uuid.UUID
    name: str
    base_quantity: int
    is_active: bool

    model_config = {"from_attributes": True}


class EventBrief(BaseModel):
    id: uuid.UUID
    name: str
    event_type: str
    is_active: bool

    model_config = {"from_attributes": True}


class FolderContentOut(BaseModel):
    folder: FolderOut
    breadcrumbs: list[BreadcrumbOut]
    permissions: FolderPermissionsOut
    subfolders: list[FolderOut]
    ingredients: list[IngredientBrief]
    products: list[ProductBrief]
    events: list[EventBrief]
