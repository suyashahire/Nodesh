"""Evidence-backed extraction of resolved concept co-occurrence relationships with PMI."""

from collections import Counter
from itertools import combinations
import math
import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from nodesh_api.models.concept import Concept, DocumentConcept
from nodesh_api.models.document import Document
from nodesh_api.models.relationship import ConceptRelationship, RelationshipEvidence
from nodesh_api.services.concept_extraction import (
    WORD_PATTERN,
    extract_context_blocks,
    normalize_word,
)


PREDICATE_PATTERNS = [
    (re.compile(r"\b(built|develop(?:ed)?|implement(?:ed)?|creat(?:ed)?)\b.{0,40}?\b(?:with|using|in|on)\b", re.I), "built_with"),
    (re.compile(r"\b(improv(?:es?|ed|ing)|optimiz(?:es?|ed|ing)|enhanc(?:es?|ed|ing)|boost(?:s|ed|ing)?|maximiz(?:es?|ed|ing))\b", re.I), "improves"),
    (re.compile(r"\b(leads?\s+to|caus(?:es?|ed|ing)|results?\s+in|produc(?:es?|ed|ing)|generat(?:es?|ed|ing))\b", re.I), "causes"),
    (re.compile(r"\b(compar(?:ed|ing)\s+(?:to|with)|outperforms?|versus|vs\.?|surpass(?:es|ed)?)\b", re.I), "compared_to"),
    (re.compile(r"\b(using|uses|utiliz(?:ed|ing)|leverag(?:ed|ing)|powered\s+by)\b", re.I), "uses"),
    (re.compile(r"\b(for|applied\s+to|aimed\s+at|detect(?:ing|ion)?|predict(?:ing|ion)?)\b", re.I), "applied_to"),
    (re.compile(r"\b(fine-?tun(?:ed|ing)|train(?:ed|ing)|evaluat(?:ed|ing)|benchmarked?\s+on)\b", re.I), "trained_for"),
    (re.compile(r"\b(at|under|graduat(?:ed)?\s+from|affiliat(?:ed)?\s+with)\b", re.I), "affiliated_with"),
    (re.compile(r"\b(integrat(?:ed|ing)?|connect(?:ed|ing)?|deploys?\s+on)\b", re.I), "integrated_with"),
    (re.compile(r"\b(part\s+of|includ(?:ing|es)?|consists?\s+of)\b", re.I), "part_of"),
]


def infer_predicate(snippet: str) -> str:
    """Infer a semantic relationship predicate from connective words in snippet."""
    if not snippet:
        return "co_occurs_with"
    for pat, pred in PREDICATE_PATTERNS:
        if pat.search(snippet):
            return pred
    return "co_occurs_with"


def calculate_pmi(
    total_blocks: int, count_a: int, count_b: int, count_ab: int
) -> tuple[float, float]:
    """Calculate Pointwise Mutual Information (PMI) and Normalized PMI (NPMI)."""
    if total_blocks == 0 or count_ab == 0 or count_a == 0 or count_b == 0:
        return 0.0, 0.0

    p_a = count_a / total_blocks
    p_b = count_b / total_blocks
    p_ab = count_ab / total_blocks

    ratio = p_ab / (p_a * p_b)
    pmi = math.log2(ratio) if ratio > 0 else 0.0

    if p_ab >= 1.0:
        npmi = 1.0
    else:
        denom = -math.log2(p_ab)
        npmi = max(-1.0, min(1.0, pmi / denom)) if denom > 0 else 0.0

    return round(pmi, 3), round(npmi, 3)


def _find_concept_positions(tokens: list[str], concept_tokens: list[str]) -> list[int]:
    n = len(concept_tokens)
    if n == 0:
        return []
    positions = []
    for i in range(len(tokens) - n + 1):
        if tokens[i : i + n] == concept_tokens:
            positions.append(i)
    return positions


def find_cooccurring_pairs(
    text: str,
    concepts_by_id: dict[UUID, str],
    max_word_distance: int = 35,
) -> tuple[dict[tuple[UUID, UUID], dict[str, int]], dict[UUID, int], dict[tuple[UUID, UUID], int], int]:
    """Find pairs of concepts that appear within close contextual proximity in text."""
    blocks = extract_context_blocks(text)
    evidence_by_pair: dict[tuple[UUID, UUID], dict[str, int]] = {}
    concept_blocks: dict[UUID, int] = Counter()
    pair_blocks: dict[tuple[UUID, UUID], int] = Counter()

    tokenized_concepts = {
        cid: [normalize_word(w) for w in WORD_PATTERN.findall(norm_name)]
        for cid, norm_name in concepts_by_id.items()
    }

    for block in blocks:
        tokens = [normalize_word(w) for w in WORD_PATTERN.findall(block)]
        if not tokens:
            continue

        concept_positions: dict[UUID, list[int]] = {}
        for cid, c_tokens in tokenized_concepts.items():
            pos = _find_concept_positions(tokens, c_tokens)
            if pos:
                concept_positions[cid] = pos
                concept_blocks[cid] += 1

        present_cids = list(concept_positions.keys())
        for i in range(len(present_cids)):
            for j in range(i + 1, len(present_cids)):
                id1, id2 = sorted([present_cids[i], present_cids[j]], key=str)
                pos1 = concept_positions[id1]
                pos2 = concept_positions[id2]

                min_dist = min(abs(p1 - p2) for p1 in pos1 for p2 in pos2)
                if min_dist <= max_word_distance:
                    key = (id1, id2)
                    pair_blocks[key] += 1
                    if key not in evidence_by_pair:
                        evidence_by_pair[key] = {
                            "source_occurrences": 0,
                            "target_occurrences": 0,
                            "snippet": " ".join(block.split())[:260],
                        }
                    evidence_by_pair[key]["source_occurrences"] += len(pos1)
                    evidence_by_pair[key]["target_occurrences"] += len(pos2)

    return evidence_by_pair, concept_blocks, pair_blocks, len(blocks)


def list_workspace_relationships(
    session: Session, workspace_id: UUID
) -> list[ConceptRelationship]:
    return list(
        session.scalars(
            select(ConceptRelationship)
            .where(ConceptRelationship.workspace_id == workspace_id)
            .options(
                joinedload(ConceptRelationship.source_concept),
                joinedload(ConceptRelationship.target_concept),
            )
            .order_by(
                ConceptRelationship.strength.desc(),
                ConceptRelationship.document_count.desc(),
                ConceptRelationship.source_concept_id,
                ConceptRelationship.target_concept_id,
            )
        )
    )


def extract_workspace_relationships(
    session: Session, workspace_id: UUID
) -> tuple[int, list[ConceptRelationship]]:
    documents = list(
        session.scalars(select(Document).where(Document.workspace_id == workspace_id))
    )
    if not documents:
        session.execute(
            delete(ConceptRelationship).where(ConceptRelationship.workspace_id == workspace_id)
        )
        session.commit()
        return 0, []

    existing_relationships = list_workspace_relationships(session, workspace_id)
    by_pair = {
        (relationship.source_concept_id, relationship.target_concept_id): relationship
        for relationship in existing_relationships
    }
    relationship_ids = [relationship.id for relationship in existing_relationships]
    if relationship_ids:
        session.execute(
            delete(RelationshipEvidence).where(
                RelationshipEvidence.relationship_id.in_(relationship_ids)
            )
        )
        session.flush()

    total_workspace_blocks = 0
    workspace_concept_blocks: dict[UUID, int] = Counter()
    workspace_pair_blocks: dict[tuple[UUID, UUID], int] = Counter()
    doc_pair_evidence: list[tuple[UUID, tuple[UUID, UUID], dict[str, int]]] = []

    for document in documents:
        concept_links = list(
            session.scalars(
                select(DocumentConcept).where(DocumentConcept.document_id == document.id)
            )
        )
        if not concept_links:
            continue

        concept_ids = [link.concept_id for link in concept_links]
        concepts = list(
            session.scalars(select(Concept).where(Concept.id.in_(concept_ids)))
        )
        concepts_by_id = {c.id: c.normalized_name for c in concepts}
        link_counts = {link.concept_id: link.occurrence_count for link in concept_links}

        if document.extracted_text and document.extracted_text.strip():
            cooccurring, c_blocks, p_blocks, n_blocks = find_cooccurring_pairs(
                document.extracted_text,
                concepts_by_id,
                max_word_distance=35,
            )
            total_workspace_blocks += n_blocks
            for cid, count in c_blocks.items():
                workspace_concept_blocks[cid] += count
            for pair, count in p_blocks.items():
                workspace_pair_blocks[pair] += count

            for pair, pair_data in cooccurring.items():
                doc_pair_evidence.append((document.id, pair, pair_data))
        else:
            total_workspace_blocks += 1
            for left, right in combinations(concept_links, 2):
                source_id, target_id = sorted((left.concept_id, right.concept_id), key=str)
                key = (source_id, target_id)
                workspace_concept_blocks[source_id] += 1
                workspace_concept_blocks[target_id] += 1
                workspace_pair_blocks[key] += 1
                doc_pair_evidence.append(
                    (
                        document.id,
                        key,
                        {
                            "source_occurrences": link_counts[source_id],
                            "target_occurrences": link_counts[target_id],
                        },
                    )
                )

    total_blocks = max(total_workspace_blocks, 1)

    # Compute PMI metrics for all observed pairs
    pair_pmi: dict[tuple[UUID, UUID], tuple[float, float]] = {}
    for pair in workspace_pair_blocks:
        src, tgt = pair
        pmi, npmi = calculate_pmi(
            total_blocks,
            workspace_concept_blocks[src],
            workspace_concept_blocks[tgt],
            workspace_pair_blocks[pair],
        )
        pair_pmi[pair] = (pmi, npmi)

    # Add evidence and filter out statistically negative coincidences
    for doc_id, pair, pair_data in doc_pair_evidence:
        pmi, npmi = pair_pmi.get(pair, (0.0, 0.0))

        # Prune pairs with negative NPMI when there are enough context blocks (pure coincidence)
        if total_blocks >= 4 and npmi < 0.0:
            continue

        relationship = by_pair.get(pair)
        predicate = infer_predicate(pair_data.get("snippet", ""))
        if relationship is None:
            relationship = ConceptRelationship(
                workspace_id=workspace_id,
                source_concept_id=pair[0],
                target_concept_id=pair[1],
                relationship_type=predicate,
                pmi=pmi,
                npmi=npmi,
            )
            session.add(relationship)
            session.flush()
            by_pair[pair] = relationship
        else:
            relationship.pmi = pmi
            relationship.npmi = npmi
            if predicate != "co_occurs_with":
                relationship.relationship_type = predicate

        session.add(
            RelationshipEvidence(
                relationship_id=relationship.id,
                document_id=doc_id,
                source_occurrences=pair_data["source_occurrences"],
                target_occurrences=pair_data["target_occurrences"],
            )
        )

    session.flush()
    _refresh_workspace_aggregates(session, workspace_id, pair_pmi)
    session.commit()
    return len(documents), list_workspace_relationships(session, workspace_id)


def extract_relationship_snippet(text: str, source_name: str, target_name: str) -> str:
    """Find a context block where source and target concepts co-occur and extract a clean snippet."""
    if not text or not text.strip():
        return ""
    blocks = extract_context_blocks(text)
    src_tokens = [normalize_word(w) for w in WORD_PATTERN.findall(source_name)]
    tgt_tokens = [normalize_word(w) for w in WORD_PATTERN.findall(target_name)]
    if not src_tokens or not tgt_tokens:
        return ""

    for block in blocks:
        tokens = [normalize_word(w) for w in WORD_PATTERN.findall(block)]
        src_pos = _find_concept_positions(tokens, src_tokens)
        tgt_pos = _find_concept_positions(tokens, tgt_tokens)
        if src_pos and tgt_pos:
            min_dist = min(abs(s - t) for s in src_pos for t in tgt_pos)
            if min_dist <= 35:
                clean_block = " ".join(block.split())
                if len(clean_block) > 260:
                    return clean_block[:257] + "..."
                return clean_block

    for block in blocks:
        tokens = [normalize_word(w) for w in WORD_PATTERN.findall(block)]
        if _find_concept_positions(tokens, src_tokens) and _find_concept_positions(tokens, tgt_tokens):
            clean_block = " ".join(block.split())
            if len(clean_block) > 260:
                return clean_block[:257] + "..."
            return clean_block

    return ""


def list_relationship_evidence(
    session: Session, workspace_id: UUID, relationship_id: UUID
) -> list[tuple[RelationshipEvidence, Document]] | None:
    relationship = session.get(ConceptRelationship, relationship_id)
    if relationship is None or relationship.workspace_id != workspace_id:
        return None
    return list(
        session.execute(
            select(RelationshipEvidence, Document)
            .join(Document, Document.id == RelationshipEvidence.document_id)
            .where(RelationshipEvidence.relationship_id == relationship_id)
            .order_by(Document.original_filename)
        )
    )


def _refresh_workspace_aggregates(
    session: Session,
    workspace_id: UUID,
    pair_pmi: dict[tuple[UUID, UUID], tuple[float, float]] | None = None,
) -> None:
    relationships = list(
        session.scalars(
            select(ConceptRelationship).where(ConceptRelationship.workspace_id == workspace_id)
        )
    )
    for relationship in relationships:
        evidence = list(
            session.scalars(
                select(RelationshipEvidence).where(
                    RelationshipEvidence.relationship_id == relationship.id
                )
            )
        )
        if not evidence:
            session.delete(relationship)
            continue
        document_count = len(evidence)
        strength = float(
            sum(item.source_occurrences * item.target_occurrences for item in evidence)
        )
        if relationship.document_count != document_count:
            relationship.document_count = document_count
        if relationship.strength != strength:
            relationship.strength = strength

        if pair_pmi:
            pair_key = (relationship.source_concept_id, relationship.target_concept_id)
            if pair_key in pair_pmi:
                pmi_val, npmi_val = pair_pmi[pair_key]
                relationship.pmi = pmi_val
                relationship.npmi = npmi_val
