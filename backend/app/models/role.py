import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(1000))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")
