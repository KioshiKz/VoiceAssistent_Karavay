import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Integer

from app.db.base import Base


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        CheckConstraint(
            "measure_type IN ('weight','volume','time','temperature')", name="measure_type_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folder_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    measure_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    allowed_container_weights_g: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
