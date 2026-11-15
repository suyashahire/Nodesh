"""Workspace knowledge graph read-model HTTP contract."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nodesh_api.database import get_session
from nodesh_api.schemas.graph import KnowledgeGraph
from nodesh_api.services.graph import build_workspace_graph
from nodesh_api.services.workspaces import resume_workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/graph", tags=["graph"])


@router.get("", response_model=KnowledgeGraph)
def get_knowledge_graph(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> KnowledgeGraph:
    """Return the workspace's resolved concepts as nodes and relationships as edges."""
    if resume_workspace(session, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return build_workspace_graph(session, workspace_id)
