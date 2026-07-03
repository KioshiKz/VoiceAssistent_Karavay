import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AppTab(Base):
    __tablename__ = "app_tabs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PermissionDef(Base):
    __tablename__ = "permission_defs"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (CheckConstraint("scope_type IN ('tab','folder','global')", name="scope_type_valid"),)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        CheckConstraint(
            "(tab_id IS NOT NULL AND folder_id IS NULL) OR "
            "(tab_id IS NULL AND folder_id IS NOT NULL) OR "
            "(tab_id IS NULL AND folder_id IS NULL)",
            name="scope_matches_type",
        ),
        UniqueConstraint("role_id", "permission_code", "tab_id", "folder_id", name="uq_role_perm_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_code: Mapped[str] = mapped_column(String(50), ForeignKey("permission_defs.code"), nullable=False)
    tab_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_tabs.id", ondelete="CASCADE")
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE")
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
