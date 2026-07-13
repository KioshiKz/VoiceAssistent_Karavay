import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "workshop_folder_id",
            "execution_date",
            name="uq_orders_id_workshop_execution_date",
        ),
        Index("ix_orders_workshop_date_uploaded", "workshop_folder_id", "execution_date", "uploaded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    workshop_folder_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("folders.id"))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    execution_date: Mapped[date] = mapped_column(Date, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    force_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    force_completed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    workshop_folder: Mapped["Folder | None"] = relationship()


class CurrentOrderSelection(Base):
    __tablename__ = "current_order_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "workshop_folder_id", "execution_date"],
            ["orders.id", "orders.workshop_folder_id", "orders.execution_date"],
            name="fk_current_order_selections_order_context",
            ondelete="CASCADE",
        ),
        Index("ix_current_order_selections_order_id", "order_id"),
    )

    workshop_folder_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        primary_key=True,
    )
    execution_date: Mapped[date] = mapped_column(Date, primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    selected_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("match_status IN ('matched','unmatched')", name="match_status_valid"),
        CheckConstraint("status IN ('pending','in_progress','completed','cancelled')", name="order_line_status_valid"),
        Index("ix_order_lines_order_id_status", "order_id", "status"),
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_advanced_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    last_advanced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="lines")
    history: Mapped[list["OrderLineHistory"]] = relationship(
        back_populates="order_line", order_by="OrderLineHistory.created_at", passive_deletes=True
    )


class OrderLineHistory(Base):
    """order_line_id survives line deletion (ON DELETE SET NULL) so audit trail
    isn't lost when a manually-created line is removed; order_id/product_name_raw
    are snapshotted here for the same reason."""

    __tablename__ = "order_line_history"
    __table_args__ = (Index("ix_order_line_history_order_date", "order_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_line_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_lines.id", ondelete="SET NULL")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    product_name_raw: Mapped[str | None] = mapped_column(String(255))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB)
    new_value: Mapped[dict | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order_line: Mapped["OrderLine | None"] = relationship(back_populates="history")
