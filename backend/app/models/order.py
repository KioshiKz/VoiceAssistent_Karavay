import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    execution_date: Mapped[date] = mapped_column(Date, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("match_status IN ('matched','unmatched')", name="match_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    row_group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    due_time: Mapped[time] = mapped_column(Time, nullable=False)
    matched_product_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id")
    )
    match_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="lines")
