import datetime
import uuid

from pydantic import BaseModel


class OrderLineOut(BaseModel):
    id: uuid.UUID
    product_name_raw: str
    quantity: int
    due_time: datetime.time
    match_status: str
    matched_product_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class OrderUploadOut(BaseModel):
    order_id: uuid.UUID
    total_lines: int
    matched: int
    unmatched: int
    lines: list[OrderLineOut]


class OrderLineMatch(BaseModel):
    product_id: uuid.UUID


class CurrentOrderOut(BaseModel):
    order_id: uuid.UUID
    execution_date: datetime.date
    lines: list[OrderLineOut]
