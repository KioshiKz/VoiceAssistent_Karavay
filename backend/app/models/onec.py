from datetime import datetime
import uuid

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OneCRecord(Base):
    """Source snapshots, separate from production recipes and execution history."""
    __tablename__ = "onec_records"
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity: Mapped[str] = mapped_column(String(100), primary_key=True)
    ref: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OneCLink(Base):
    """Which application object was created from which 1C reference.

    `source_hash` is the 1C data last applied and `local_hash` the resulting
    recipe, so a re-import can tell 1C changes from manual edits."""
    __tablename__ = "onec_links"
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity: Mapped[str] = mapped_column(String(32), primary_key=True)
    ref: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    local_hash: Mapped[str | None] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
