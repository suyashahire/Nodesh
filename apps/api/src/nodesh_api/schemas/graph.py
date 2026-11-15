"""Knowledge graph read-model schemas."""

from uuid import UUID

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: UUID
    label: str
    document_count: int
    total_occurrences: int
    tfidf_score: float = 0.0


class GraphEdge(BaseModel):
    id: UUID
    source: UUID
    target: UUID
    relationship_type: str
    document_count: int
    strength: float
    pmi: float = 0.0
    npmi: float = 0.0


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
