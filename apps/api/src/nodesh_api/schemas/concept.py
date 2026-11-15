"""Concept API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from nodesh_api.schemas.graph import KnowledgeGraph


class ConceptRead(BaseModel):
    id: UUID
    name: str
    document_count: int
    total_occurrences: int
    tfidf_score: float = 0.0
    source_documents: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConceptExtractionResult(BaseModel):
    documents_analyzed: int
    concepts: list[ConceptRead]


class ConceptMergeSuggestion(BaseModel):
    source_concept_id: UUID
    source_name: str
    target_concept_id: UUID
    target_name: str
    similarity: float
    reason: str


class ConceptMergeRequest(BaseModel):
    source_concept_id: UUID
    target_concept_id: UUID


class ConceptMergeResult(BaseModel):
    merged_into_concept_id: UUID
    merged_concept_name: str
    source_occurrences_merged: int
    new_total_occurrences: int
    graph: KnowledgeGraph


class ConceptDossier(BaseModel):
    concept_id: UUID
    concept_name: str
    summary: str
    key_sentences: list[str]
    source_documents: list[str]
