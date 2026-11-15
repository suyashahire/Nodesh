"""Anonymous workspace persistence model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from nodesh_api.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    """An anonymous, browser-resumable Nodesh workspace."""

    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
