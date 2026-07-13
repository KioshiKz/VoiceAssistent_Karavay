import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    voice_assistant_enabled: bool

    model_config = {"from_attributes": True}


class VoiceSettingsUpdate(BaseModel):
    voice_assistant_enabled: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class TabPermission(BaseModel):
    view: bool = False
    edit: bool = False


class MePermissions(BaseModel):
    tabs: dict[str, TabPermission]
    global_: dict[str, bool] = Field(alias="global")
    system_role: bool

    model_config = {"populate_by_name": True}
