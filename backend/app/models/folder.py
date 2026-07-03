import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uq_folder_parent_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    materialized_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    children: Mapped[list["Folder"]] = relationship(
        back_populates="parent", cascade="save-update", remote_side="Folder.parent_id"
    )
    parent: Mapped["Folder | None"] = relationship(back_populates="children", remote_side=[id])
