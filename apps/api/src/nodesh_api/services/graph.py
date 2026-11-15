"""Build the workspace knowledge graph from persisted concepts and relationships."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept
from nodesh_api.models.relationship import ConceptRelationship
from nodesh_api.schemas.graph import GraphEdge, GraphNode, KnowledgeGraph


def build_workspace_graph(session: Session, workspace_id: UUID) -> KnowledgeGraph:
    concepts = list(
        session.scalars(
            select(Concept)
            .where(Concept.workspace_id == workspace_id)
            .order_by(Concept.total_occurrences.desc(), Concept.name)
        )
    )
    relationships = list(
        session.scalars(
            select(ConceptRelationship)
            .where(ConceptRelationship.workspace_id == workspace_id)
            .order_by(ConceptRelationship.strength.desc(), ConceptRelationship.id)
        )
    )
    return KnowledgeGraph(
        nodes=[
            GraphNode(
                id=concept.id,
                label=concept.name,
                document_count=concept.document_count,
                total_occurrences=concept.total_occurrences,
                tfidf_score=concept.tfidf_score,
            )
            for concept in concepts
        ],
        edges=[
            GraphEdge(
                id=relationship.id,
                source=relationship.source_concept_id,
                target=relationship.target_concept_id,
                relationship_type=relationship.relationship_type,
                document_count=relationship.document_count,
                strength=relationship.strength,
                pmi=relationship.pmi,
                npmi=relationship.npmi,
            )
            for relationship in relationships
        ],
    )
