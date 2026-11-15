"""Environment-backed application configuration."""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


@dataclass(frozen=True)
class Settings:
    database_url: str
    web_origin: str
    uploads_dir: Path
    max_upload_bytes: int
    max_workspace_documents: int
    max_workspace_storage_bytes: int
    max_extracted_characters: int
    max_pdf_pages: int
    max_docx_uncompressed_bytes: int
    max_textrank_sentences: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://nodesh:nodesh_dev_password@localhost:5432/nodesh",
        ),
        web_origin=os.getenv("WEB_ORIGIN", "http://localhost:3000"),
        uploads_dir=Path(os.getenv("UPLOADS_DIR", "uploads")).resolve(),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        max_workspace_documents=int(os.getenv("MAX_WORKSPACE_DOCUMENTS", "25")),
        max_workspace_storage_bytes=int(
            os.getenv("MAX_WORKSPACE_STORAGE_BYTES", str(50 * 1024 * 1024))
        ),
        max_extracted_characters=int(os.getenv("MAX_EXTRACTED_CHARACTERS", "300000")),
        max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "50")),
        max_docx_uncompressed_bytes=int(
            os.getenv("MAX_DOCX_UNCOMPRESSED_BYTES", str(25 * 1024 * 1024))
        ),
        max_textrank_sentences=int(os.getenv("MAX_TEXTRANK_SENTENCES", "250")),
    )
