import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventTemplate(Base):
    __tablename__ = "event_templates"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('timer','weight_check','phrase_confirmation')", name="event_type_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folder_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
