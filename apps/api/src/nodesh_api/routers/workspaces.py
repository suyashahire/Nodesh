"""Anonymous workspace HTTP contract."""

from uuid import UUID

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from nodesh_api.database import get_session
from nodesh_api.schemas.workspace import WorkspaceRead, WorkspaceStats
from nodesh_api.services.workspaces import (
    create_workspace,
    delete_workspace,
    get_workspace_stats,
    resume_workspace,
)
from nodesh_api.storage import delete_workspace_storage, get_uploads_directory

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_anonymous_workspace(session: Session = Depends(get_session)) -> WorkspaceRead:
    """Create an anonymous workspace for a new browser session."""
    return create_workspace(session)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> WorkspaceRead:
    """Resume an existing workspace and record its most recent activity."""
    workspace = resume_workspace(session, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workspace(
    workspace_id: UUID,
    session: Session = Depends(get_session),
    uploads_directory: Path = Depends(get_uploads_directory),
) -> Response:
    """Permanently delete a workspace, its graph data, and its stored source files."""
    if not delete_workspace(session, workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    delete_workspace_storage(uploads_directory, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/stats", response_model=WorkspaceStats)
def get_stats(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> WorkspaceStats:
    """Return counts and aggregate character statistics for a workspace."""
    workspace = resume_workspace(session, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )
    return get_workspace_stats(session, workspace_id)
