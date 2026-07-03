import uuid

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    password: str | None = None


class UserListOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    role_names: list[str]


class UserRolesSet(BaseModel):
    role_ids: list[uuid.UUID]
