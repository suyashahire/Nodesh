"""Workspace topic and concept HTTP contract."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from nodesh_api.database import get_session
from nodesh_api.schemas.concept import (
    ConceptDossier,
    ConceptExtractionResult,
    ConceptMergeRequest,
    ConceptMergeResult,
    ConceptMergeSuggestion,
    ConceptRead,
)
from nodesh_api.services.concept_merge import find_merge_suggestions, merge_concepts
from nodesh_api.services.concepts import analyze_workspace, list_workspace_concepts
from nodesh_api.services.textrank import build_concept_dossier
from nodesh_api.services.workspaces import resume_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/concepts", tags=["concepts"])


def require_workspace(session: Session, workspace_id: UUID) -> None:
    if resume_workspace(session, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


@router.post("/extract", response_model=ConceptExtractionResult)
def extract_workspace_concepts(
    workspace_id: UUID,
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> ConceptExtractionResult:
    """Rebuild deterministic concept links and workspace topics from documents."""
    require_workspace(session, workspace_id)
    documents_analyzed, concepts = analyze_workspace(session, workspace_id, limit=limit)
    return ConceptExtractionResult(documents_analyzed=documents_analyzed, concepts=concepts)


@router.get("", response_model=list[ConceptRead])
def get_workspace_concepts(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> list[ConceptRead]:
    """List a workspace's currently extracted topics and concepts."""
    require_workspace(session, workspace_id)
    return list_workspace_concepts(session, workspace_id)


@router.get("/merge-suggestions", response_model=list[ConceptMergeSuggestion])
def get_concept_merge_suggestions(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> list[ConceptMergeSuggestion]:
    """Return deterministic merge suggestions for near-duplicate concepts/aliases."""
    require_workspace(session, workspace_id)
    return find_merge_suggestions(session, workspace_id)


@router.post("/merge", response_model=ConceptMergeResult)
def merge_workspace_concepts(
    workspace_id: UUID,
    request: ConceptMergeRequest,
    session: Session = Depends(get_session),
) -> ConceptMergeResult:
    """Manually merge source concept into target concept with user confirmation."""
    require_workspace(session, workspace_id)
    try:
        return merge_concepts(
            session,
            workspace_id,
            source_concept_id=request.source_concept_id,
            target_concept_id=request.target_concept_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@router.get("/{concept_id}/dossier", response_model=ConceptDossier)
def get_concept_dossier(
    workspace_id: UUID,
    concept_id: UUID,
    session: Session = Depends(get_session),
) -> ConceptDossier:
    """Generate an extractive 2-sentence summary dossier using classical TextRank."""
    require_workspace(session, workspace_id)
    try:
        return build_concept_dossier(session, workspace_id, concept_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
