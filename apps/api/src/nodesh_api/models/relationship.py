"""Resolved concept relationships and their document evidence."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from nodesh_api.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConceptRelationship(Base):
    """A canonical, undirected relationship between two workspace concepts."""

    __tablename__ = "concept_relationships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_concept_id", "target_concept_id", "relationship_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    source_concept_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("concepts.id", ondelete="CASCADE"),
    )
    target_concept_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("concepts.id", ondelete="CASCADE"),
    )
    relationship_type: Mapped[str] = mapped_column(String(32), default="co_occurs_with")
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    strength: Mapped[float] = mapped_column(Float, default=0)
    pmi: Mapped[float] = mapped_column(Float, default=0.0)
    npmi: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source_concept = relationship("Concept", foreign_keys=[source_concept_id])
    target_concept = relationship("Concept", foreign_keys=[target_concept_id])


class RelationshipEvidence(Base):
    """The observation of one relationship in one source document."""

    __tablename__ = "relationship_evidence"

    relationship_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("concept_relationships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_occurrences: Mapped[int] = mapped_column(Integer)
    target_occurrences: Mapped[int] = mapped_column(Integer)
