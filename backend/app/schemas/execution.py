import datetime
import uuid
from typing import Any

from pydantic import BaseModel


class ExecutionPlanStepOut(BaseModel):
    order_index: int
    step_type: str
    ingredient_name_snapshot: str | None
    measure_type_snapshot: str | None
    quantity_canonical_computed: int | None
    quantity_display: str | None = None
    event_name_snapshot: str | None
    event_type_snapshot: str | None
    event_params_snapshot: dict[str, Any] | None
    status: str
    completed_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class ExecutionPlanOut(BaseModel):
    id: uuid.UUID
    order_line_id: uuid.UUID
    product_id: uuid.UUID
    multiplier: float
    status: str
    current_step_index: int
    steps: list[ExecutionPlanStepOut]

    model_config = {"from_attributes": True}
