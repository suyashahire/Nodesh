"""Text extraction for supported source document formats with strict security safeguards."""

import csv
import io
from pathlib import Path
import re
import zipfile

from docx import Document as DocxDocument
from pypdf import PdfReader

from nodesh_api.config import get_settings


class TextExtractionError(ValueError):
    """Raised when a stored document cannot be read as its declared format."""


def _is_numeric_or_trivial(val: str) -> bool:
    if not val:
        return True
    cleaned = val.replace(".", "", 1).replace("-", "", 1).replace(",", "", 1).strip("%$€£ ")
    if cleaned.isdigit():
        return True
    return val.lower() in {"true", "false", "yes", "no", "null", "none", "n/a", "na", "-", "nil", "undefined"}


def _split_multivalue(cell: str) -> list[str]:
    """Split cell containing multiple values (e.g. 'Python, TypeScript' or 'A; B | C')."""
    raw = cell.strip()
    if not raw:
        return []
    if ";" in raw:
        items = [i.strip() for i in raw.split(";") if i.strip()]
        if len(items) > 1:
            return items
    if "|" in raw:
        items = [i.strip() for i in raw.split("|") if i.strip()]
        if len(items) > 1:
            return items
    if "," in raw and not any(p in raw for p in [".", "!", "?"]):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if 2 <= len(parts) <= 8 and all(len(p.split()) <= 4 for p in parts):
            return parts
    return [raw]


def _format_triple_sentence(source: str, predicate: str, target: str) -> str:
    """Format an explicit Subject-Predicate-Object triple into a natural declarative sentence."""
    p_norm = predicate.lower().strip().replace(" ", "_").replace("-", "_")

    if p_norm in {"uses", "utilizes", "use", "utilize", "leveraging", "leverages"}:
        return f"{source} utilizes {target}."
    if p_norm in {"built_with", "developed_with", "coded_in", "written_in"}:
        return f"{source} is built with {target}."
    if p_norm in {"runs_on", "runs", "deployed_on", "hosted_on", "deploys_on"}:
        return f"{source} runs on {target}."
    if p_norm in {"powers", "drives", "serves"}:
        return f"{source} powers {target}."
    if p_norm in {"produces", "generates", "outputs", "yields", "creates"}:
        return f"{source} produces {target}."
    if p_norm in {"analyzes", "evaluates", "measures", "benchmarks", "monitors"}:
        return f"{source} analyzes {target}."
    if p_norm in {"improves", "optimizes", "enhances", "boosts"}:
        return f"{source} improves {target}."
    if p_norm in {"depends_on", "requires", "needs"}:
        return f"{source} depends on {target}."
    if p_norm in {"integrates_with", "connects_with", "connected_to"}:
        return f"{source} integrates with {target}."
    if p_norm in {"affiliated_with", "associated_with", "works_at", "member_of"}:
        return f"{source} is affiliated with {target}."
    if p_norm in {"part_of", "includes", "component_of", "belongs_to"}:
        return f"{source} is part of {target}."
    if p_norm in {"causes", "leads_to", "results_in"}:
        return f"{source} causes {target}."
    if p_norm in {"applied_to", "aimed_at", "used_for"}:
        return f"{source} is applied to {target}."
    if p_norm in {"trained_for", "trained_on", "fine_tuned_for"}:
        return f"{source} is trained for {target}."
    if p_norm in {"compared_to", "versus", "vs"}:
        return f"{source} is compared to {target}."
    if p_norm in {"consists_of", "composed_of"}:
        return f"{source} consists of {target}."

    clean_p = predicate.strip().replace("_", " ")
    if clean_p.endswith(("s", "ed", "ing")) or clean_p.startswith(("is ", "are ", "was ", "has ")):
        return f"{source} {clean_p} {target}."
    return f"{source} is {clean_p} {target}."


def _map_header_to_predicate(header: str) -> tuple[str, str]:
    """Map a column header name to a natural sentence template linking Subject {S} to Object {O}."""
    h = header.lower().strip()

    # 1. Architecture, Language, Stack
    if re.search(r"\b(lang(?:uages?|s)?|written\s*in|built\s*with|frameworks?|stacks?|tech(?:nolog(?:y|ies))?|tools?|engines?|librar(?:y|ies))\b", h):
        return ("{S} is built with {O}.", "built_with")

    # 2. Database, Storage, Integration
    if re.search(r"\b(databases?|dbs?|storages?|backends?|stores?|integrated?\s*with|connect(?:ed|ion|ions)?)\b", h):
        return ("{S} integrates with {O}.", "integrated_with")

    # 3. Platform, Cloud, Deployment, OS
    if re.search(r"\b(platforms?|deploy(?:ments?|ed\s*on)?|clouds?|hosts?|hostings?|os|operating\s*systems?|infrastructures?|infra|environments?)\b", h):
        return ("{S} runs on {O}.", "runs_on")

    # 4. Dependency, Requirements
    if re.search(r"\b(depends?\s*(?:on)?|dependenc(?:y|ies)|requir(?:es?|ements?)|prereq(?:uisite)?s?)\b", h):
        return ("{S} depends on {O}.", "depends_on")

    # 5. Use, Utilizes
    if re.search(r"\b(uses?|utiliz(?:es?|ing)?|leverag(?:es?|ing)?)\b", h):
        return ("{S} utilizes {O}.", "uses")

    # 6. Purpose, Application, Target Goal
    if re.search(r"\b(used\s*for|purposes?|applications?|targets?|aims?|goals?|solves?|tasks?|problems?)\b", h):
        return ("{S} is applied to {O}.", "applied_to")

    # 7. Powers, Drives
    if re.search(r"\b(powers?|drives?|serves?|fuels?)\b", h):
        return ("{S} powers {O}.", "powers")

    # 8. Produces, Generates, Outputs
    if re.search(r"\b(produces?|outputs?|generat(?:es?|ion|ions)?|yields?|creates?|results?)\b", h):
        return ("{S} produces {O}.", "produces")

    # 9. Analyzes, Evaluates, Measures
    if re.search(r"\b(analyz(?:es?|ing|is)?|evaluat(?:es?|ion|ions)?|measures?|benchmarks?|monitors?|tracks?)\b", h):
        return ("{S} analyzes {O}.", "analyzes")

    # 10. Improves, Optimizes, Enhances
    if re.search(r"\b(improv(?:es?|ing|ements?)?|optimiz(?:es?|ing|ations?)?|enhanc(?:es?|ing|ements?)?|boosts?)\b", h):
        return ("{S} improves {O}.", "improves")

    # 11. Causes, Symptoms, Risks
    if re.search(r"\b(symptoms?|causes?|leads?\s*to|risks?|origins?)\b", h):
        return ("{S} causes {O}.", "causes")

    # 12. Treatment, Remedy (Object improves Subject)
    if re.search(r"\b(treat(?:ments?|s)?|remed(?:y|ies)|cures?|medications?|drugs?|solutions?)\b", h):
        return ("{O} improves {S}.", "improves")

    # 13. Category, Type, Taxonomy, Domain
    if re.search(r"\b(categor(?:y|ies)|types?|class(?:es|ifications?)?|domains?|fields?|genres?|sectors?|industr(?:y|ies)|part\s*of)\b", h):
        return ("{S} is part of {O}.", "part_of")

    # 14. Affiliation, Company, Author, Creator, Founder, Location
    if re.search(r"\b(compan(?:y|ies)|org(?:anizations?)?|affiliat(?:ed|ions?)?|authors?|creators?|founders?|developers?|teams?|owners?|vendors?|institutions?|universit(?:y|ies)|publishers?|locations?|headquarters|hq|cit(?:y|ies)|countr(?:y|ies)|regions?)\b", h):
        return ("{S} is affiliated with {O}.", "affiliated_with")

    # 15. Dataset, Model, Training
    if re.search(r"\b(datasets?|corp(?:us|ora)|trained\s*(?:on|for)|models?)\b", h):
        return ("{S} is trained for {O}.", "trained_for")

    # 16. Components, Subtopics
    if re.search(r"\b(consists?\s*of|components?|modules?|subtopics?|members?)\b", h):
        return ("{S} consists of {O}.", "consists_of")

    # 17. Comparison, Alternatives
    if re.search(r"\b(compared?\s*(?:to|with)?|competitors?|alternatives?|vs\.?)\b", h):
        return ("{S} is compared to {O}.", "compared_to")

    # 18. Definition, Description
    if re.search(r"\b(desc(?:riptions?)?|def(?:initions?)?|summar(?:y|ies)|meanings?|overviews?|about)\b", h):
        return ("{S} describes {O}.", "part_of")

    # Default fallback: clean statement without adjacent nouns
    return ("{S} is associated with {O}.", "co_occurs_with")


def _extract_csv_text(raw_text: str) -> str:
    """Parse CSV text into semantically structured SPO sentences for NLP concept extraction."""
    if not raw_text.strip():
        return ""

    sample = raw_text[:4096]
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
    header_lower = [c.lower() for c in first_row]

    has_header = (
        len(rows) > 1
        and len(first_row) > 1
        and all(len(c) > 0 for c in first_row)
        and not any(c.replace(".", "", 1).replace("-", "", 1).isdigit() for c in first_row)
    )

    if not has_header:
        # Headerless rows: join cells into relational phrases per row
        row_blocks: list[str] = []
        for row in rows:
            clean_cells = [c.strip() for c in row if c.strip() and not _is_numeric_or_trivial(c.strip())]
            if len(clean_cells) >= 2:
                primary = clean_cells[0]
                rest = ", ".join(clean_cells[1:])
                row_blocks.append(f"{primary} is associated with {rest}.")
            elif clean_cells:
                row_blocks.append(clean_cells[0] + ".")
        return "\n\n".join(row_blocks)

    # 1. Check if Schema is Direct Graph Triples / Edge List
    src_idx: int | None = None
    tgt_idx: int | None = None
    rel_idx: int | None = None

    for i, h in enumerate(header_lower):
        if h in {"source", "subject", "from", "head", "node1", "node_1", "src", "entity1", "entity_1"}:
            src_idx = i
        elif h in {"target", "object", "to", "tail", "node2", "node_2", "dst", "entity2", "entity_2"}:
            tgt_idx = i
        elif h in {"relationship", "predicate", "relation", "type", "rel", "edge", "label", "link"}:
            rel_idx = i

    if src_idx is not None and tgt_idx is not None:
        triple_sentences: list[str] = []
        for row in rows[1:]:
            if src_idx >= len(row) or tgt_idx >= len(row):
                continue
            src = row[src_idx].strip()
            tgt = row[tgt_idx].strip()
            if not src or not tgt or _is_numeric_or_trivial(src) or _is_numeric_or_trivial(tgt):
                continue
            rel = (
                row[rel_idx].strip()
                if rel_idx is not None and rel_idx < len(row) and row[rel_idx].strip()
                else "relates to"
            )
            triple_sentences.append(_format_triple_sentence(src, rel, tgt))
        return "\n\n".join(triple_sentences)

    # 2. Schema is Entity-Attribute / Tabular Data
    # Determine the primary entity column (first non-numeric, non-ID column)
    id_headers = {"id", "uuid", "no", "num", "number", "index", "#", "row_id", "key", "_id"}
    primary_idx = 0
    for i, h in enumerate(header_lower):
        if h not in id_headers:
            primary_idx = i
            break

    paragraph_blocks: list[str] = []
    header = first_row

    for row in rows[1:]:
        if primary_idx >= len(row):
            continue
        primary_entity = row[primary_idx].strip()
        if not primary_entity or _is_numeric_or_trivial(primary_entity):
            continue

        row_statements: list[str] = []
        for i, cell in enumerate(row):
            if i == primary_idx or i >= len(header):
                continue
            cell_val = cell.strip()
            if not cell_val or _is_numeric_or_trivial(cell_val):
                continue

            col_header = header[i]
            template, _ = _map_header_to_predicate(col_header)

            values = _split_multivalue(cell_val)
            for val in values:
                if not _is_numeric_or_trivial(val):
                    stmt = template.format(S=primary_entity, O=val)
                    if not stmt.endswith("."):
                        stmt += "."
                    row_statements.append(stmt)

        if row_statements:
            paragraph_blocks.append(" ".join(row_statements))

    return "\n\n".join(paragraph_blocks) if paragraph_blocks else raw_text


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
