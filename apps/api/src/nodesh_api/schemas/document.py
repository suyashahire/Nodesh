"""Document API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    id: UUID
    workspace_id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    extraction_status: str
    extracted_characters: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(DocumentRead):
    extracted_text: str
