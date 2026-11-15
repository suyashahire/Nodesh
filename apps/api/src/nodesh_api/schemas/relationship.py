"""Relationship API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RelationshipRead(BaseModel):
    id: UUID
    source_concept_id: UUID
    source_name: str
    target_concept_id: UUID
    target_name: str
    relationship_type: str
    document_count: int
    strength: float
    pmi: float = 0.0
    npmi: float = 0.0
    created_at: datetime
    updated_at: datetime


class RelationshipEvidenceRead(BaseModel):
    document_id: UUID
    original_filename: str
    source_occurrences: int
    target_occurrences: int
    snippet: str = ""


class RelationshipExtractionResult(BaseModel):
    documents_analyzed: int
    relationships: list[RelationshipRead]
