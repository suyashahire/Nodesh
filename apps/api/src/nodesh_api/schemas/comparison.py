"""Multi-document comparison API schemas."""

from uuid import UUID

from pydantic import BaseModel


class SharedConceptOverview(BaseModel):
    id: UUID
    name: str
    document_count: int
    total_occurrences: int
    document_ids: list[UUID]
    document_names: list[str]


class DocumentConceptOverview(BaseModel):
    document_id: UUID
    filename: str
    total_concepts: int
    unique_concept_count: int
    unique_concepts: list[str]


class DocumentPairOverlap(BaseModel):
    doc_a_id: UUID
    doc_a_name: str
    doc_b_id: UUID
    doc_b_name: str
    shared_concept_count: int
    jaccard_similarity: float
    shared_concepts: list[str]


class WorkspaceDocumentComparison(BaseModel):
    workspace_id: UUID
    total_documents: int
    documents: list[DocumentConceptOverview]
    shared_concepts: list[SharedConceptOverview]
    pairwise_overlap: list[DocumentPairOverlap]
