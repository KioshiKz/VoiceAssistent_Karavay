import uuid

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    order_visibility_ahead: int | None = Field(default=None, ge=1)


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    order_visibility_ahead: int | None = Field(default=None, ge=1)


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool
    order_visibility_ahead: int | None

    model_config = {"from_attributes": True}


class PermissionDefOut(BaseModel):
    code: str
    label: str
    scope_type: str

    model_config = {"from_attributes": True}


class AppTabOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    order_index: int

    model_config = {"from_attributes": True}


class RolePermissionEntry(BaseModel):
    permission_code: str
    tab_id: uuid.UUID | None = None
    folder_id: uuid.UUID | None = None
    granted: bool = True


class RolePermissionsReplace(BaseModel):
    entries: list[RolePermissionEntry]


class RolePermissionOut(RolePermissionEntry):
    id: uuid.UUID
