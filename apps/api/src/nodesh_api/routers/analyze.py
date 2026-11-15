"""Workspace unified analysis HTTP contract."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from nodesh_api.database import get_session
from nodesh_api.models.relationship import ConceptRelationship
from nodesh_api.schemas.analyze import AnalysisResult
from nodesh_api.schemas.relationship import RelationshipRead
from nodesh_api.services.concepts import analyze_workspace
from nodesh_api.services.graph import build_workspace_graph
from nodesh_api.services.relationships import extract_workspace_relationships
from nodesh_api.services.workspaces import resume_workspace

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/analyze", tags=["analyze"]
)


def require_workspace(session: Session, workspace_id: UUID) -> None:
    if resume_workspace(session, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


def serialize_relationship(relationship: ConceptRelationship) -> RelationshipRead:
    return RelationshipRead(
        id=relationship.id,
        source_concept_id=relationship.source_concept_id,
        source_name=relationship.source_concept.name,
        target_concept_id=relationship.target_concept_id,
        target_name=relationship.target_concept.name,
        relationship_type=relationship.relationship_type,
        document_count=relationship.document_count,
        strength=relationship.strength,
        created_at=relationship.created_at,
        updated_at=relationship.updated_at,
    )


@router.post("", response_model=AnalysisResult)
def analyze_workspace_pipeline(
    workspace_id: UUID,
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> AnalysisResult:
    """Run the complete analysis pipeline in one request: concepts, relationships, and graph."""
    require_workspace(session, workspace_id)
    documents_analyzed, concepts = analyze_workspace(session, workspace_id, limit=limit)
    _, relationships = extract_workspace_relationships(session, workspace_id)
    graph = build_workspace_graph(session, workspace_id)
    return AnalysisResult(
        documents_analyzed=documents_analyzed,
        concepts=concepts,
        relationships=[serialize_relationship(rel) for rel in relationships],
        graph=graph,
    )
