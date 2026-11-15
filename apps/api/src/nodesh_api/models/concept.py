"""Persisted workspace concepts and their source-document links."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from nodesh_api.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Concept(Base):
    """A normalized keyword or phrase aggregated within one workspace."""

    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("workspace_id", "normalized_name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    total_occurrences: Mapped[int] = mapped_column(Integer, default=0)
    tfidf_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DocumentConcept(Base):
    """A concept observation extracted from one source document."""

    __tablename__ = "document_concepts"

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    concept_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    occurrence_count: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    tfidf_score: Mapped[float] = mapped_column(Float, default=0.0)
