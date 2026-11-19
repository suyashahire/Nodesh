"""Text extraction for supported source document formats with strict security safeguards."""

import csv
import io
from pathlib import Path
import zipfile

from docx import Document as DocxDocument
from pypdf import PdfReader

from nodesh_api.config import get_settings


class TextExtractionError(ValueError):
    """Raised when a stored document cannot be read as its declared format."""


def _extract_csv_text(raw_text: str) -> str:
    """Parse CSV text into semantically structured sentences for NLP concept extraction."""
    if not raw_text.strip():
        return ""

    sample = raw_text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except Exception:
        dialect = csv.excel

    try:
        reader = csv.reader(io.StringIO(raw_text), dialect)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    except Exception:
        reader = csv.reader(io.StringIO(raw_text))
        rows = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        return ""

    first_row = [c.strip() for c in rows[0]]
    has_header = (
        len(rows) > 1
        and len(first_row) > 1
        and all(len(c) > 0 for c in first_row)
        and not any(c.replace(".", "", 1).replace("-", "", 1).isdigit() for c in first_row)
    )

    lines: list[str] = []
    if has_header:
        header = first_row
        for row in rows[1:]:
            parts: list[str] = []
            for i, cell in enumerate(row):
                val = cell.strip()
                if not val:
                    continue
                col = header[i] if i < len(header) else f"Field_{i+1}"
                if val.endswith((".", "!", "?")):
                    parts.append(f"{col}: {val}")
                else:
                    parts.append(f"{col}: {val}.")
            if parts:
                lines.append(" ".join(parts))
    else:
        for row in rows:
            clean_cells = [c.strip() for c in row if c.strip()]
            if clean_cells:
                row_str = ", ".join(clean_cells)
                if not row_str.endswith((".", "!", "?")):
                    row_str += "."
                lines.append(row_str)

    return "\n".join(lines) if lines else raw_text


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

        elif media_type in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
            try:
                raw_text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raw_text = path.read_text(encoding="utf-8", errors="replace")

            extracted = _extract_csv_text(raw_text)

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
