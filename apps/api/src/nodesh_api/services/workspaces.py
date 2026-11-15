"""Workspace domain service."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept
from nodesh_api.models.document import Document
from nodesh_api.models.relationship import ConceptRelationship
from nodesh_api.models.workspace import Workspace
from nodesh_api.schemas.workspace import WorkspaceStats


def create_workspace(session: Session) -> Workspace:
    workspace = Workspace()
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def resume_workspace(session: Session, workspace_id: UUID) -> Workspace | None:
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        return None

    workspace.last_active_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(workspace)
    return workspace


def delete_workspace(session: Session, workspace_id: UUID) -> bool:
    """Permanently remove one anonymous workspace and its database records."""
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        return False
    session.delete(workspace)
    session.commit()
    return True


def get_workspace_stats(session: Session, workspace_id: UUID) -> WorkspaceStats:
    """Compute workspace statistics using COUNT queries."""
    document_count = session.scalar(
        select(func.count()).select_from(Document).where(Document.workspace_id == workspace_id)
    ) or 0
    concept_count = session.scalar(
        select(func.count()).select_from(Concept).where(Concept.workspace_id == workspace_id)
    ) or 0
    relationship_count = session.scalar(
        select(func.count())
        .select_from(ConceptRelationship)
        .where(ConceptRelationship.workspace_id == workspace_id)
    ) or 0
    total_characters = session.scalar(
        select(func.coalesce(func.sum(Document.extracted_characters), 0))
        .where(Document.workspace_id == workspace_id)
    ) or 0
    return WorkspaceStats(
        document_count=document_count,
        concept_count=concept_count,
        relationship_count=relationship_count,
        total_characters=total_characters,
    )
