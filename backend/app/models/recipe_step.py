import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    __table_args__ = (
        CheckConstraint(
            "(step_type = 'ingredient' AND ingredient_id IS NOT NULL AND event_template_id IS NULL "
            "AND quantity_canonical IS NOT NULL) OR "
            "(step_type = 'event' AND event_template_id IS NOT NULL AND ingredient_id IS NULL)",
            name="step_shape",
        ),
        UniqueConstraint("product_id", "order_index", name="uq_recipe_step_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)

    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT")
    )
    quantity_canonical: Mapped[int | None] = mapped_column(Integer)

    event_template_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("event_templates.id", ondelete="RESTRICT")
    )
    event_params: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="steps")
    ingredient: Mapped["Ingredient | None"] = relationship()
    event_template: Mapped["EventTemplate | None"] = relationship()
