"""Workspace API response schema."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkspaceRead(BaseModel):
    id: UUID
    created_at: datetime
    last_active_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceStats(BaseModel):
    document_count: int
    concept_count: int
    relationship_count: int
    total_characters: int
