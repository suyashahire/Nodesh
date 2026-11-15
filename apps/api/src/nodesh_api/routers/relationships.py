"""Workspace relationship extraction HTTP contract."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nodesh_api.database import get_session
from nodesh_api.models.relationship import ConceptRelationship
from nodesh_api.schemas.relationship import (
    RelationshipEvidenceRead,
    RelationshipExtractionResult,
    RelationshipRead,
)
from nodesh_api.services.relationships import (
    extract_relationship_snippet,
    extract_workspace_relationships,
    list_relationship_evidence,
    list_workspace_relationships,
)
from nodesh_api.services.workspaces import resume_workspace

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/relationships", tags=["relationships"]
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


@router.post("/extract", response_model=RelationshipExtractionResult)
def extract_relationships(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> RelationshipExtractionResult:
    """Rebuild evidence-backed co-occurrence relationships for a workspace."""
    require_workspace(session, workspace_id)
    documents_analyzed, relationships = extract_workspace_relationships(session, workspace_id)
    return RelationshipExtractionResult(
        documents_analyzed=documents_analyzed,
        relationships=[serialize_relationship(relationship) for relationship in relationships],
    )


@router.get("", response_model=list[RelationshipRead])
def get_relationships(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> list[RelationshipRead]:
    """List resolved concept relationships in a workspace."""
    require_workspace(session, workspace_id)
    return [
        serialize_relationship(relationship)
        for relationship in list_workspace_relationships(session, workspace_id)
    ]


@router.get("/{relationship_id}/evidence", response_model=list[RelationshipEvidenceRead])
def get_evidence(
    workspace_id: UUID, relationship_id: UUID, session: Session = Depends(get_session)
) -> list[RelationshipEvidenceRead]:
    """Show the source documents that support one resolved relationship."""
    require_workspace(session, workspace_id)
    relationship = session.get(ConceptRelationship, relationship_id)
    evidence = list_relationship_evidence(session, workspace_id, relationship_id)
    if evidence is None or relationship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    return [
        RelationshipEvidenceRead(
            document_id=document.id,
            original_filename=document.original_filename,
            source_occurrences=item.source_occurrences,
            target_occurrences=item.target_occurrences,
            snippet=extract_relationship_snippet(
                document.extracted_text,
                relationship.source_concept.name,
                relationship.target_concept.name,
            ),
        )
        for item, document in evidence
    ]
