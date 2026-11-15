"""Unified analysis API schema."""

from pydantic import BaseModel

from nodesh_api.schemas.concept import ConceptRead
from nodesh_api.schemas.graph import KnowledgeGraph
from nodesh_api.schemas.relationship import RelationshipRead


class AnalysisResult(BaseModel):
    documents_analyzed: int
    concepts: list[ConceptRead]
    relationships: list[RelationshipRead]
    graph: KnowledgeGraph
