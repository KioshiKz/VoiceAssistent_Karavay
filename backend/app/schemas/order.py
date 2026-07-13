import datetime
import uuid

from pydantic import BaseModel, Field


class OrderLineOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    product_name_raw: str
    quantity: int
    due_time: datetime.time
    match_status: str
    matched_product_id: uuid.UUID | None
    status: str
    cancellation_reason: str | None
    cancelled_by: uuid.UUID | None
    cancelled_by_name: str | None = None
    cancelled_at: datetime.datetime | None
    last_advanced_by: uuid.UUID | None
    last_advanced_by_name: str | None = None
    last_advanced_at: datetime.datetime | None
    workshop_folder_id: uuid.UUID | None = None
    workshop_folder_name: str | None = None

    model_config = {"from_attributes": True}


class OrderUploadOut(BaseModel):
    order_id: uuid.UUID
    total_lines: int
    matched: int
    unmatched: int
    lines: list[OrderLineOut]


class OrderLineMatch(BaseModel):
    product_id: uuid.UUID


class OrderLineUpdate(BaseModel):
    product_name_raw: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int | None = Field(default=None, ge=1)
    due_time: datetime.time | None = None
    matched_product_id: uuid.UUID | None = None


class OrderLineCreate(BaseModel):
    order_id: uuid.UUID
    product_name_raw: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=1)
    due_time: datetime.time
    matched_product_id: uuid.UUID | None = None


class OrderLineCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class OrderLineHistoryOut(BaseModel):
    id: uuid.UUID
    order_line_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    actor_name: str | None = None
    event_type: str
    old_value: dict | None
    new_value: dict | None
    note: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class OrderLineHistoryEntryOut(OrderLineHistoryOut):
    order_id: uuid.UUID | None
    product_name_raw: str | None
    execution_date: datetime.date | None


class CurrentOrderOut(BaseModel):
    order_id: uuid.UUID
    execution_date: datetime.date
    lines: list[OrderLineOut]


class OrderSummaryOut(BaseModel):
    id: uuid.UUID
    execution_date: datetime.date
    source_filename: str
    uploaded_at: datetime.datetime
    uploaded_by_name: str | None
    workshop_folder_id: uuid.UUID | None
    workshop_folder_name: str | None
    total_lines: int
    active_lines: int
