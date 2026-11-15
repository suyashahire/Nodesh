"""Text extraction for supported source document formats with strict security safeguards."""

from pathlib import Path
import zipfile

from docx import Document as DocxDocument
from pypdf import PdfReader

from nodesh_api.config import get_settings


class TextExtractionError(ValueError):
    """Raised when a stored document cannot be read as its declared format."""


def extract_text(path: Path, media_type: str) -> str:
    settings = get_settings()
    extracted = ""

    try:
        if media_type == "application/pdf":
            reader = PdfReader(path)
            max_pages = settings.max_pdf_pages
            pages_to_extract = (
                reader.pages[:max_pages] if len(reader.pages) > max_pages else reader.pages
            )
            extracted = "\n".join(page.extract_text() or "" for page in pages_to_extract)

        elif media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # Decompression bomb and zip bomb inspection
            with zipfile.ZipFile(path, "r") as zf:
                compressed_size = sum(info.compress_size for info in zf.infolist())
                uncompressed_size = sum(info.file_size for info in zf.infolist())
                max_uncompressed = settings.max_docx_uncompressed_bytes

                if uncompressed_size > max_uncompressed:
                    raise TextExtractionError(
                        f"DOCX uncompressed size ({uncompressed_size} bytes) exceeds limit of {max_uncompressed} bytes"
                    )
                if (
                    compressed_size > 0
                    and (uncompressed_size / compressed_size) > 10.0
                    and uncompressed_size > 1024 * 1024
                ):
                    raise TextExtractionError(
                        "DOCX compression ratio exceeds safety threshold (potential zip bomb)"
                    )

            extracted = "\n".join(paragraph.text for paragraph in DocxDocument(path).paragraphs)

        elif media_type in {"text/plain", "text/markdown"}:
            try:
                extracted = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                extracted = path.read_text(encoding="utf-8", errors="replace")

        else:
            raise TextExtractionError("The document format is not supported")

    except TextExtractionError:
        raise
    except Exception as error:
        raise TextExtractionError("The document could not be read") from error

    # Enforce global character ceiling to prevent downstream NLP / graph explosion
    max_chars = settings.max_extracted_characters
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars]

    return extracted
