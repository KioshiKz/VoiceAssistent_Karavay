import uuid
from typing import Any, Literal

from pydantic import BaseModel, model_validator


class RecipeStepCreate(BaseModel):
    step_type: Literal["ingredient", "event", "ingredient_event"]
    order_index: int

    ingredient_id: uuid.UUID | None = None
    quantity_canonical: float | None = None

    event_template_id: uuid.UUID | None = None
    event_params: dict[str, Any] | None = None

    @model_validator(mode="after")
    def check_shape(self):
        if self.step_type == "ingredient":
            if self.ingredient_id is None or self.quantity_canonical is None:
                raise ValueError("ingredient_id and quantity_canonical are required for ingredient steps")
        elif self.step_type == "event":
            if self.event_template_id is None:
                raise ValueError("event_template_id is required for event steps")
        else:
            if self.ingredient_id is None or self.quantity_canonical is None or self.event_template_id is None:
                raise ValueError(
                    "ingredient_id, quantity_canonical and event_template_id are required for linked steps"
                )
        return self


class RecipeStepReorder(BaseModel):
    step_ids: list[uuid.UUID]


class RecipeStepUpdate(BaseModel):
    """Partial update: only quantity/params change; step_type and target
    ingredient/event_template are immutable after creation (delete+recreate instead)."""

    quantity_canonical: float | None = None
    event_params: dict[str, Any] | None = None


class IngredientRefOut(BaseModel):
    id: uuid.UUID
    name: str
    measure_type: str

    model_config = {"from_attributes": True}


class EventTemplateRefOut(BaseModel):
    id: uuid.UUID
    name: str
    event_type: str

    model_config = {"from_attributes": True}


class RecipeStepOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    order_index: int
    step_type: str
    ingredient: IngredientRefOut | None = None
    quantity_canonical: float | None = None
    quantity_display: str | None = None
    event_template: EventTemplateRefOut | None = None
    event_params: dict[str, Any] | None = None
