"""Classical TextRank extractive summarization service (Zero-ML, PageRank graph algorithm)."""

import math
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept, DocumentConcept
from nodesh_api.models.document import Document
from nodesh_api.schemas.concept import ConceptDossier
from nodesh_api.services.concept_extraction import STOP_WORDS


def _is_header_noise(sentence: str) -> bool:
    s_low = sentence.lower()
    if any(k in s_low for k in ["issn:", "isbn:", "doi:", "sjif rating", "volume:"]):
        return True
    if re.search(r"https?://", s_low) and len(s_low.split()) < 10:
        return True
    return False


def _split_into_sentences(text: str) -> list[str]:
    """Split text into clean sentences using standard punctuation boundaries."""
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned: list[str] = []
    for s in raw_sentences:
        s_clean = s.strip()
        # Require sentence to have at least 4 words, contain alphanumeric characters, and not be a citation/URL header
        if len(s_clean.split()) >= 4 and any(c.isalnum() for c in s_clean) and not _is_header_noise(s_clean):
            cleaned.append(s_clean)
    return cleaned


def _tokenize_sentence(sentence: str) -> set[str]:
    """Tokenize sentence into normalized content words, stripping stopwords and punctuation."""
    tokens = re.findall(r"\b[a-z]{3,}\b", sentence.lower())
    return {t for t in tokens if t not in STOP_WORDS}


def _compute_sentence_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Classical TextRank normalized overlap similarity between two sentences."""
    if not tokens_a or not tokens_b:
        return 0.0
    common = len(tokens_a & tokens_b)
    if common == 0:
        return 0.0
    # Normalized by log lengths as in classical Mihalcea & Tarau (2004) TextRank
    denom = math.log(len(tokens_a) + 1) + math.log(len(tokens_b) + 1)
    if denom <= 0:
        return 0.0
    return common / denom


def run_textrank(
    sentences: list[str],
    *,
    iterations: int = 20,
    damping: float = 0.85,
    top_k: int = 2,
    priority_terms: list[str] | None = None,
) -> list[str]:
    """Compute TextRank scores over sentence graph with strict sentence ceiling to prevent O(S^2) DoS."""
    max_sentences = 250
    if len(sentences) > max_sentences:
        priority_kw = [t.lower() for t in (priority_terms or []) if len(t) >= 3]
        if priority_kw:
            relevant = [s for s in sentences if any(kw in s.lower() for kw in priority_kw)]
            others = [s for s in sentences if not any(kw in s.lower() for kw in priority_kw)]
            sentences = (relevant + others)[:max_sentences]
        else:
            sentences = sentences[:max_sentences]

    n = len(sentences)
    if n <= top_k:
        return sentences

    token_sets = [_tokenize_sentence(s) for s in sentences]

    # Build adjacency matrix
    weights: list[list[float]] = [[0.0] * n for _ in range(n)]
    out_sums: list[float] = [0.0] * n

    for i in range(n):
        for j in range(i + 1, n):
            sim = _compute_sentence_similarity(token_sets[i], token_sets[j])
            if sim > 0:
                weights[i][j] = sim
                weights[j][i] = sim
                out_sums[i] += sim
                out_sums[j] += sim

    # Priority term boost (e.g. concept name keywords)
    priority_keywords = [t.lower() for t in (priority_terms or []) if len(t) >= 3]

    # Initialize scores
    scores = [1.0 / n] * n

    # Power iteration
    for _ in range(iterations):
        next_scores = [0.0] * n
        for i in range(n):
            in_sum = 0.0
            for j in range(n):
                if i != j and out_sums[j] > 0:
                    in_sum += (weights[j][i] / out_sums[j]) * scores[j]
            next_scores[i] = (1.0 - damping) / n + damping * in_sum
        scores = next_scores

    # Relevance boost for sentences directly mentioning priority concept terms
    final_ranked: list[tuple[int, float]] = []
    for i, s in enumerate(sentences):
        s_lower = s.lower()
        boost = 1.0
        if priority_keywords and any(kw in s_lower for kw in priority_keywords):
            boost = 1.35
        final_ranked.append((i, scores[i] * boost))

    # Sort descending by score
    final_ranked.sort(key=lambda x: x[1], reverse=True)
    top_indices = sorted([idx for idx, _ in final_ranked[:top_k]])

    return [sentences[idx] for idx in top_indices]


def build_concept_dossier(
    session: Session, workspace_id: UUID, concept_id: UUID
) -> ConceptDossier:
    """Generate a 2-sentence extractive dossier summary for a concept using classical TextRank."""
    concept = session.scalar(
        select(Concept).where(Concept.id == concept_id, Concept.workspace_id == workspace_id)
    )
    if concept is None:
        raise ValueError(f"Concept {concept_id} not found in workspace {workspace_id}")

    # Fetch documents linked to this concept
    doc_concepts = list(
        session.scalars(
            select(DocumentConcept).where(DocumentConcept.concept_id == concept_id)
        )
    )
    doc_ids = [dc.document_id for dc in doc_concepts]

    documents = (
        list(session.scalars(select(Document).where(Document.id.in_(doc_ids))))
        if doc_ids
        else []
    )

    source_filenames = sorted({doc.original_filename for doc in documents})

    # Collect candidate sentences mentioning the concept from extracted text
    concept_terms = [t for t in re.split(r"\s+", concept.name) if len(t) >= 3]
    concept_lower = concept.name.lower()

    direct_sentences: list[str] = []
    fallback_sentences: list[str] = []

    for doc in documents:
        if not doc.extracted_text:
            continue
        doc_sentences = _split_into_sentences(doc.extracted_text)
        for s in doc_sentences:
            s_lower = s.lower()
            if concept_lower in s_lower:
                direct_sentences.append(s)
            elif any(t.lower() in s_lower for t in concept_terms):
                fallback_sentences.append(s)

    candidates = (
        direct_sentences
        if len(direct_sentences) >= 2
        else (direct_sentences + fallback_sentences)
    )

    if not candidates:
        summary_text = (
            f"{concept.name} is referenced across {concept.document_count} document"
            f"{'s' if concept.document_count != 1 else ''} with a total of "
            f"{concept.total_occurrences} occurrence{'s' if concept.total_occurrences != 1 else ''}."
        )
        return ConceptDossier(
            concept_id=concept.id,
            concept_name=concept.name,
            summary=summary_text,
            key_sentences=[summary_text],
            source_documents=source_filenames,
        )

    # Run TextRank to distill top 2 most representative sentences
    key_sentences = run_textrank(
        candidates,
        top_k=2,
        priority_terms=concept_terms,
    )

    summary = " ".join(key_sentences)

    return ConceptDossier(
        concept_id=concept.id,
        concept_name=concept.name,
        summary=summary,
        key_sentences=key_sentences,
        source_documents=source_filenames,
    )
