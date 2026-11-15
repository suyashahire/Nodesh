"""Safe local storage for source documents."""

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from uuid import UUID, uuid4

from fastapi import UploadFile

from nodesh_api.config import get_settings

SUPPORTED_DOCUMENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
}


class DocumentUploadError(ValueError):
    """Raised when an upload does not meet Nodesh's ingestion requirements."""


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    media_type: str
    path: Path
    storage_key: str
    size_bytes: int


def get_uploads_directory() -> Path:
    return get_settings().uploads_dir


def delete_workspace_storage(uploads_directory: Path, workspace_id: UUID) -> None:
    """Remove only the generated storage directory for one workspace."""
    root = uploads_directory.resolve()
    workspace_directory = (root / str(workspace_id)).resolve()
    if workspace_directory.parent != root:
        raise ValueError("Workspace storage path is outside the configured uploads directory")
    if workspace_directory.is_dir():
        shutil.rmtree(workspace_directory)


def validate_upload(file: UploadFile) -> tuple[str, str]:
    if not file.filename:
        raise DocumentUploadError("A filename is required")

    suffix = Path(file.filename).suffix.lower()
    accepted_media_types = SUPPORTED_DOCUMENT_TYPES.get(suffix)
    if accepted_media_types is None:
        raise DocumentUploadError("Supported formats are PDF, DOCX, TXT, and Markdown")

    declared_media_type = file.content_type or "application/octet-stream"
    if declared_media_type not in accepted_media_types:
        raise DocumentUploadError("The declared media type does not match the file extension")

    canonical_media_type = next(
        media_type
        for media_type in accepted_media_types
        if media_type != "application/octet-stream"
    )
    return suffix, canonical_media_type


def _validate_file_signature(suffix: str, chunk: bytes) -> None:
    """Inspect magic bytes in the first stream chunk to prevent MIME-type spoofing."""
    if len(chunk) == 0:
        return

    if suffix == ".pdf":
        # PDF files must start with %PDF- (or contain %PDF- within the first 1024 bytes)
        if not (chunk.startswith(b"%PDF-") or b"%PDF-" in chunk[:1024]):
            raise DocumentUploadError("Invalid PDF document: missing %PDF- file signature")

    elif suffix == ".docx":
        # DOCX is an OpenXML ZIP archive starting with PK\x03\x04
        if not chunk.startswith(b"PK\x03\x04"):
            raise DocumentUploadError("Invalid DOCX document: missing PK zip signature header")

    elif suffix in {".txt", ".md"}:
        # Reject executable / binary payloads disguised as text
        if chunk.startswith(b"MZ") or chunk.startswith(b"\x7fELF"):
            raise DocumentUploadError("Invalid text document: executable binary signature detected")
        if b"\x00" in chunk[:4096]:
            raise DocumentUploadError("Invalid text document: binary null bytes detected")


def _sanitize_filename(name: str, fallback_suffix: str) -> str:
    """Sanitize original filename to remove BIDI overrides, control characters, and excess length."""
    base = Path(name).name
    # Strip BIDI override unicode characters (U+202A to U+202E, U+2066 to U+2069)
    cleaned = re.sub(r"[\u202a-\u202e\u2066-\u2069]", "", base)
    # Strip non-printable control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned).strip()
    if not cleaned:
        cleaned = f"document{fallback_suffix}"
    if len(cleaned) > 128:
        suffix = Path(cleaned).suffix or fallback_suffix
        stem = Path(cleaned).stem[: 128 - len(suffix)]
        cleaned = f"{stem}{suffix}"
    return cleaned


async def store_upload(
    *,
    file: UploadFile,
    workspace_id: UUID,
    uploads_directory: Path,
    max_upload_bytes: int,
) -> StoredUpload:
    """Stream an uploaded file to a server-generated path with a size limit and signature checks."""
    suffix, media_type = validate_upload(file)
    workspace_directory = uploads_directory / str(workspace_id)
    workspace_directory.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4()}{suffix}"
    destination = workspace_directory / storage_name
    size_bytes = 0
    header_verified = False

    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                if not header_verified:
                    _validate_file_signature(suffix, chunk)
                    header_verified = True

                size_bytes += len(chunk)
                if size_bytes > max_upload_bytes:
                    raise DocumentUploadError(
                        f"Documents must be {max_upload_bytes} bytes or smaller"
                        f" (uploaded {size_bytes} bytes)"
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    safe_filename = _sanitize_filename(file.filename or f"document{suffix}", suffix)

    return StoredUpload(
        original_filename=safe_filename,
        media_type=media_type,
        path=destination,
        storage_key=str(destination.relative_to(uploads_directory)),
        size_bytes=size_bytes,
    )
