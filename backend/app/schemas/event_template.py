import uuid

from pydantic import BaseModel, Field


class EventTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    event_type: str = Field(pattern="^(timer|weight_check|phrase_confirmation)$")
    is_active: bool = True


class EventTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    event_type: str | None = Field(default=None, pattern="^(timer|weight_check|phrase_confirmation)$")
    is_active: bool | None = None


class EventTemplateOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    name: str
    description: str | None
    event_type: str
    is_active: bool

    model_config = {"from_attributes": True}
