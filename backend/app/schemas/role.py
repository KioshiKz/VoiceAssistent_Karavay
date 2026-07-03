import uuid

from pydantic import BaseModel


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_system: bool

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
