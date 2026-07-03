import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExecutionPlan(Base):
    __tablename__ = "execution_plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started','in_progress','completed')", name="execution_status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_line_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_lines.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    multiplier: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    current_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list["ExecutionPlanStep"]] = relationship(
        back_populates="execution_plan", cascade="all, delete-orphan", order_by="ExecutionPlanStep.order_index"
    )


class ExecutionPlanStep(Base):
    __tablename__ = "execution_plan_steps"
    __table_args__ = (
        CheckConstraint("step_type IN ('ingredient','event')", name="exec_step_type_valid"),
        CheckConstraint("status IN ('pending','done')", name="exec_step_status_valid"),
        UniqueConstraint("execution_plan_id", "order_index", name="uq_exec_step_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("execution_plans.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)

    ingredient_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    measure_type_snapshot: Mapped[str | None] = mapped_column(String(20))
    quantity_canonical_computed: Mapped[int | None] = mapped_column(Integer)

    event_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    event_type_snapshot: Mapped[str | None] = mapped_column(String(30))
    event_params_snapshot: Mapped[dict | None] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    execution_plan: Mapped["ExecutionPlan"] = relationship(back_populates="steps")
