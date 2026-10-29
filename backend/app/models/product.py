import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("base_quantity > 0", name="base_quantity_positive"),
        CheckConstraint("yield_unit IN ('pcs','kg')", name="yield_unit_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folder_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Recipe output in `yield_unit`: whole pieces, or kilograms (may be fractional).
    base_quantity: Mapped[float] = mapped_column(Numeric(12, 3, asdecimal=False), nullable=False)
    yield_unit: Mapped[str] = mapped_column(String(8), nullable=False, default="pcs", server_default="pcs")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list["RecipeStep"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="RecipeStep.order_index"
    )
