import uuid

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.weight_check import WeightCheckSettings


class EventTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    event_type: str = Field(pattern="^(timer|weight_check|phrase_confirmation)$")
    is_active: bool = True
    default_params: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_weight_defaults(self):
        if self.event_type == "weight_check":
            self.default_params = WeightCheckSettings.model_validate(self.default_params or {}).model_dump()
        return self


class EventTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    event_type: str | None = Field(default=None, pattern="^(timer|weight_check|phrase_confirmation)$")
    is_active: bool | None = None
    default_params: dict[str, Any] | None = None


class EventTemplateOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    name: str
    description: str | None
    event_type: str
    is_active: bool
    default_params: dict[str, Any] | None = None

    model_config = {"from_attributes": True}
