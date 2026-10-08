import datetime
import uuid

from pydantic import BaseModel


class StatisticsSummary(BaseModel):
    orders: int
    positions: int
    pending: int
    in_progress: int
    completed: int
    cancelled: int
    emergency_schedules: int
    emergency_changes: int


class ProductStatistics(BaseModel):
    product_name: str
    positions: int
    total_quantity: int
    completed: int
    cancelled: int
    emergency_positions: int


class AuditLogOut(BaseModel):
    id: uuid.UUID
    source: str
    order_id: uuid.UUID | None
    order_line_id: uuid.UUID | None
    emergency_schedule_id: uuid.UUID | None = None
    product_name_raw: str | None
    execution_date: datetime.date | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    event_type: str
    old_value: dict | None
    new_value: dict | None
    note: str | None
    created_at: datetime.datetime


class StatisticsOut(BaseModel):
    summary: StatisticsSummary
    products: list[ProductStatistics]
    logs: list[AuditLogOut]
    logs_total: int
