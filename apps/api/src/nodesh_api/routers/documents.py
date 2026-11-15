"""Workspace-scoped document ingestion HTTP contract."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nodesh_api.config import get_settings
from nodesh_api.database import get_session
from nodesh_api.models.document import Document
from nodesh_api.schemas.comparison import WorkspaceDocumentComparison
from nodesh_api.schemas.document import DocumentDetail, DocumentRead
from nodesh_api.services.document_comparison import compare_workspace_documents
from nodesh_api.services.documents import create_document, delete_document, get_document, list_documents
from nodesh_api.services.extraction import TextExtractionError, extract_text
from nodesh_api.services.workspaces import resume_workspace
from nodesh_api.storage import DocumentUploadError, get_uploads_directory, store_upload

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/documents", tags=["documents"])


def require_workspace(session: Session, workspace_id: UUID) -> None:
    if resume_workspace(session, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    uploads_directory: Path = Depends(get_uploads_directory),
) -> DocumentRead:
    """Store and extract one document in an existing anonymous workspace with strict quota controls."""
    require_workspace(session, workspace_id)
    settings = get_settings()

    # Enforce workspace document count quota
    existing_docs = (
        session.scalar(
            select(func.count(Document.id)).where(Document.workspace_id == workspace_id)
        )
        or 0
    )
    if existing_docs >= settings.max_workspace_documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace document limit reached (maximum {settings.max_workspace_documents} documents)",
        )

    # Enforce workspace total storage quota
    existing_storage = (
        session.scalar(
            select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
                Document.workspace_id == workspace_id
            )
        )
        or 0
    )
    if existing_storage >= settings.max_workspace_storage_bytes:
        max_mb = settings.max_workspace_storage_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace storage quota reached (maximum {max_mb}MB)",
        )

    try:
        upload = await store_upload(
            file=file,
            workspace_id=workspace_id,
            uploads_directory=uploads_directory,
            max_upload_bytes=settings.max_upload_bytes,
        )
    except DocumentUploadError as error:
        err_msg = str(error)
        if "bytes or smaller" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=err_msg
            ) from error
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=err_msg
        ) from error

    # Check for empty file
    if upload.size_bytes == 0:
        upload.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This file appears to be empty.",
        )

    try:
        extracted_text = extract_text(upload.path, upload.media_type)
    except TextExtractionError as error:
        upload.path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    return create_document(
        session,
        workspace_id=workspace_id,
        upload=upload,
        extracted_text=extracted_text,
    )


@router.get("", response_model=list[DocumentRead])
def get_documents(workspace_id: UUID, session: Session = Depends(get_session)) -> list[DocumentRead]:
    """List document metadata for one workspace."""
    require_workspace(session, workspace_id)
    return list_documents(session, workspace_id)


@router.get("/comparison", response_model=WorkspaceDocumentComparison)
def get_documents_comparison(
    workspace_id: UUID, session: Session = Depends(get_session)
) -> WorkspaceDocumentComparison:
    """Return multi-document comparison showing shared and unique concepts and pairwise Jaccard overlap."""
    require_workspace(session, workspace_id)
    return compare_workspace_documents(session, workspace_id)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document_detail(
    workspace_id: UUID, document_id: UUID, session: Session = Depends(get_session)
) -> DocumentDetail:
    """Return a document's stored extracted text within its owning workspace."""
    require_workspace(session, workspace_id)
    document = get_document(session, workspace_id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    workspace_id: UUID,
    document_id: UUID,
    session: Session = Depends(get_session),
    uploads_directory: Path = Depends(get_uploads_directory),
) -> Response:
    """Delete a document, its physical file, and its concept links."""
    require_workspace(session, workspace_id)
    if not delete_document(session, workspace_id, document_id, uploads_directory):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
