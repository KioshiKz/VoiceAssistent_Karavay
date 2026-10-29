import datetime
import uuid

from pydantic import BaseModel, Field


class EmergencyScheduleCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class EmergencyAddItem(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)
    due_time: datetime.time


class EmergencyReplaceItem(BaseModel):
    source_line_id: uuid.UUID
    quantity: float = Field(gt=0)
    due_time: datetime.time | None = None


class EmergencyRemoveItem(BaseModel):
    source_line_id: uuid.UUID
    note: str | None = Field(default=None, max_length=1000)


class EmergencyItemUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    due_time: datetime.time | None = None


class EmergencySourceLineOut(BaseModel):
    id: uuid.UUID
    product_name_raw: str
    quantity: float
    unit: str | None = None
    due_time: datetime.time
    matched_product_id: uuid.UUID | None
    match_status: str
    status: str
    overlaid_by_item_id: uuid.UUID | None = None
    overlay_action: str | None = None


class EmergencyItemOut(BaseModel):
    id: uuid.UUID
    action: str
    source_line_id: uuid.UUID | None
    product_name_raw: str
    quantity: float
    unit: str | None = None
    due_time: datetime.time
    matched_product_id: uuid.UUID | None
    match_status: str
    status: str
    active: bool


class EmergencyScheduleOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    reason: str
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    source_lines: list[EmergencySourceLineOut]
    items: list[EmergencyItemOut]
