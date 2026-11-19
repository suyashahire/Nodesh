"""Evidence-backed extraction of resolved concept relationships with Subject-Predicate-Object (SPO) inference."""

from collections import Counter, defaultdict
from itertools import combinations
import math
import re
from typing import Any
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

SEMANTIC_PREDICATE_RULES = [
    # Architecture & Construction
    (
        re.compile(
            r"\b(?:built|developed|implemented|created|coded|engineered|constructed)\s+(?:with|using|in|on|via)\b",
            re.I,
        ),
        "built_with",
        "normal",
    ),
    (
        re.compile(
            r"\b(?:powers|drives|serves\s+as\s+(?:the\s+)?backend\s+for|underpins)\b",
            re.I,
        ),
        "powers",
        "normal",
    ),
    (
        re.compile(r"\b(?:powered|driven)\s+by\b", re.I),
        "powers",
        "reverse",
    ),
    # Usage & Integration
    (
        re.compile(
            r"\b(?:uses|using|utiliz(?:es?|ed|ing)|leverag(?:es?|ed|ing)|relies\s+on|depends\s+on)\b",
            re.I,
        ),
        "uses",
        "normal",
    ),
    (
        re.compile(
            r"\b(?:integrat(?:es?|ed|ing)|connect(?:s|ed|ing)?|interfaces?\s+with|interoperates?\s+with)\b",
            re.I,
        ),
        "integrates_with",
        "normal",
    ),
    (
        re.compile(
            r"\b(?:runs\s+on|deploys?\s+(?:on|to)|hosted\s+on|executes?\s+on)\b",
            re.I,
        ),
        "runs_on",
        "normal",
    ),
    # Optimization & Performance
    (
        re.compile(
            r"\b(?:improv(?:es?|ed|ing)|optimiz(?:es?|ed|ing)|enhanc(?:es?|ed|ing)|boost(?:s|ed|ing)?|accelerat(?:es?|ed|ing)|streamlin(?:es?|ed|ing)|maximiz(?:es?|ed|ing))\b",
            re.I,
        ),
        "improves",
        "normal",
    ),
    # Production & Generation
    (
        re.compile(
            r"\b(?:produc(?:es?|ed|ing)|generat(?:es?|ed|ing)|extract(?:s|ed|ing)|yield(?:s|ed|ing)|comput(?:es?|ed|ing)|transform(?:s|ed|ing))\b",
            re.I,
        ),
        "produces",
        "normal",
    ),
    (
        re.compile(
            r"\b(?:is|are|was|were)\s+(?:generated|produced|extracted|computed)\s+by\b",
            re.I,
        ),
        "produces",
        "reverse",
    ),
    # Evaluation & Analysis
    (
        re.compile(
            r"\b(?:analyz(?:es?|ed|ing)|evaluat(?:es?|ed|ing)|benchmark(?:s|ed|ing)?|measur(?:es?|ed|ing)|inspect(?:s|ed|ing))\b",
            re.I,
        ),
        "analyzes",
        "normal",
    ),
    # Comparison
    (
        re.compile(
            r"\b(?:compar(?:ed|ing)\s+(?:to|with)|outperforms?|versus|vs\.?|surpass(?:es|ed)?|better\s+than)\b",
            re.I,
        ),
        "compared_to",
        "normal",
    ),
    # Causality
    (
        re.compile(
            r"\b(?:leads?\s+to|caus(?:es?|ed|ing)|results?\s+in|trigger(?:s|ed|ing))\b",
            re.I,
        ),
        "causes",
        "normal",
    ),
    # Structural / Composition
    (
        re.compile(
            r"\b(?:consists?\s+of|compris(?:es?|ed|ing)|includ(?:es?|ed|ing)|contain(?:s|ed|ing))\b",
            re.I,
        ),
        "consists_of",
        "normal",
    ),
    (
        re.compile(
            r"\b(?:part\s+of|component\s+of|element\s+of|subset\s+of|member\s+of)\b",
            re.I,
        ),
        "part_of",
        "normal",
    ),
    # Domain / Affiliation
    (
        re.compile(
            r"\b(?:graduat(?:ed|ing)?\s+from|studied\s+at|employed\s+(?:at|by)|affiliated\s+with|works?\s+(?:at|for)|at\b)\b",
            re.I,
        ),
        "affiliated_with",
        "normal",
    ),
    # Training & Application
    (
        re.compile(
            r"\b(?:train(?:ed|ing)?\s+(?:on|for)|fine-?tun(?:ed|ing)?\s+(?:on|for)|specializ(?:ed|ing)?\s+(?:in|for)|benchmarked?\s+on)\b",
            re.I,
        ),
        "trained_for",
        "normal",
    ),
    (
        re.compile(
            r"\b(?:applied\s+to|aimed\s+at|tailored\s+(?:to|for)|designed\s+for|detect(?:ing|ion)?|predict(?:ing|ion)?)\b",
            re.I,
        ),
        "applied_to",
        "normal",
    ),
]


def infer_predicate(snippet: str) -> str:
    """Infer a semantic relationship predicate from connective words in snippet."""
    if not snippet:
        return "co_occurs_with"
    for pat, pred, _ in SEMANTIC_PREDICATE_RULES:
        if pat.search(snippet):
            return pred
    return "co_occurs_with"


def infer_predicate_between(interval_text: str, sentence_text: str = "") -> tuple[str, str]:
    """Infer predicate and Subject/Object direction from the interval between two concepts."""
    if interval_text:
        for pat, pred, direction in SEMANTIC_PREDICATE_RULES:
            if pat.search(interval_text):
                return pred, direction
    if sentence_text:
        for pat, pred, direction in SEMANTIC_PREDICATE_RULES:
            if pat.search(sentence_text):
                return pred, direction
    return "co_occurs_with", "normal"


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


def _find_concept_positions(tokens: list[str], concept_tokens: list[str]) -> list[tuple[int, int]]:
    n = len(concept_tokens)
    if n == 0:
        return []
    spans: list[tuple[int, int]] = []
    for i in range(len(tokens) - n + 1):
        if tokens[i : i + n] == concept_tokens:
            spans.append((i, i + n))
    return spans


def find_cooccurring_pairs(
    text: str,
    concepts_by_id: dict[UUID, str],
    max_word_distance: int = 35,
) -> tuple[
    dict[tuple[UUID, UUID], dict[str, Any]],
    dict[UUID, int],
    dict[tuple[UUID, UUID], int],
    int,
]:
    """Extract evidence-backed concept relationships with Subject-Predicate-Object (SPO) inference."""
    blocks = extract_context_blocks(text)
    concept_blocks: dict[UUID, int] = Counter()
    undirected_pair_blocks: dict[tuple[UUID, UUID], int] = Counter()

    tokenized_concepts = {
        cid: [normalize_word(w) for w in WORD_PATTERN.findall(norm_name)]
        for cid, norm_name in concepts_by_id.items()
    }

    # Accumulate observations per concept pair: frozenset({A, B}) -> list of observations
    pair_observations: dict[frozenset[UUID], list[dict[str, Any]]] = defaultdict(list)

    for block in blocks:
        block_tokens = [normalize_word(w) for w in WORD_PATTERN.findall(block)]
        if not block_tokens:
            continue

        block_positions: dict[UUID, list[tuple[int, int]]] = {}
        for cid, c_tokens in tokenized_concepts.items():
            spans = _find_concept_positions(block_tokens, c_tokens)
            if spans:
                block_positions[cid] = spans
                concept_blocks[cid] += 1

        present_cids = list(block_positions.keys())
        if len(present_cids) < 2:
            continue

        # Record co-occurrence for all pairs in block within max_word_distance
        for i in range(len(present_cids)):
            for j in range(i + 1, len(present_cids)):
                id1, id2 = present_cids[i], present_cids[j]
                spans1 = block_positions[id1]
                spans2 = block_positions[id2]
                min_dist = min(abs(s1[0] - s2[0]) for s1 in spans1 for s2 in spans2)
                if min_dist <= max_word_distance:
                    undir_key = tuple(sorted([id1, id2], key=str))
                    undirected_pair_blocks[undir_key] += 1

        # Sentence-level SPO extraction within this block
        sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", block) if s.strip()]
        for sentence in sentences:
            sent_raw_tokens = WORD_PATTERN.findall(sentence)
            sent_norm_tokens = [normalize_word(w) for w in sent_raw_tokens]
            if not sent_norm_tokens:
                continue

            sent_positions: dict[UUID, list[tuple[int, int]]] = {}
            for cid, c_tokens in tokenized_concepts.items():
                spans = _find_concept_positions(sent_norm_tokens, c_tokens)
                if spans:
                    sent_positions[cid] = spans

            sent_cids = list(sent_positions.keys())
            for i in range(len(sent_cids)):
                for j in range(i + 1, len(sent_cids)):
                    cid_a, cid_b = sent_cids[i], sent_cids[j]
                    spans_a = sent_positions[cid_a]
                    spans_b = sent_positions[cid_b]

                    # Find closest span pair in this sentence
                    best_pair = None
                    min_token_dist = 999
                    for sa in spans_a:
                        for sb in spans_b:
                            dist = sb[0] - sa[1] if sa[1] <= sb[0] else sa[0] - sb[1]
                            if abs(dist) < min_token_dist:
                                min_token_dist = abs(dist)
                                best_pair = (sa, sb)

                    if best_pair and min_token_dist <= 25:
                        sa, sb = best_pair
                        if sa[0] < sb[0]:
                            interval_words = sent_raw_tokens[sa[1] : sb[0]]
                            first_id, second_id = cid_a, cid_b
                            first_occ, second_occ = len(spans_a), len(spans_b)
                        else:
                            interval_words = sent_raw_tokens[sb[1] : sa[0]]
                            first_id, second_id = cid_b, cid_a
                            first_occ, second_occ = len(spans_b), len(spans_a)

                        interval_text = " ".join(interval_words)
                        predicate, direction = infer_predicate_between(interval_text, sentence)

                        if direction == "normal":
                            subj_id, obj_id = first_id, second_id
                            subj_occ, obj_occ = first_occ, second_occ
                        else:
                            subj_id, obj_id = second_id, first_id
                            subj_occ, obj_occ = second_occ, first_occ

                        confidence = 3.0 if predicate != "co_occurs_with" else 1.5
                        pair_observations[frozenset([cid_a, cid_b])].append(
                            {
                                "source_id": subj_id,
                                "target_id": obj_id,
                                "predicate": predicate,
                                "confidence": confidence,
                                "source_occurrences": subj_occ,
                                "target_occurrences": obj_occ,
                                "snippet": sentence[:260],
                            }
                        )

        # For any pairs co-occurring in the block that had NO sentence-level hit:
        for i in range(len(present_cids)):
            for j in range(i + 1, len(present_cids)):
                cid_a, cid_b = present_cids[i], present_cids[j]
                pair_set = frozenset([cid_a, cid_b])
                if pair_set not in pair_observations:
                    spans_a = block_positions[cid_a]
                    spans_b = block_positions[cid_b]
                    min_dist = min(abs(s1[0] - s2[0]) for s1 in spans_a for s2 in spans_b)
                    if min_dist <= max_word_distance:
                        first_pos_a = min(s[0] for s in spans_a)
                        first_pos_b = min(s[0] for s in spans_b)
                        if first_pos_a <= first_pos_b:
                            s_id, t_id = cid_a, cid_b
                            s_occ, t_occ = len(spans_a), len(spans_b)
                        else:
                            s_id, t_id = cid_b, cid_a
                            s_occ, t_occ = len(spans_b), len(spans_a)

                        pair_observations[pair_set].append(
                            {
                                "source_id": s_id,
                                "target_id": t_id,
                                "predicate": "co_occurs_with",
                                "confidence": 1.0,
                                "source_occurrences": s_occ,
                                "target_occurrences": t_occ,
                                "snippet": " ".join(block.split())[:260],
                            }
                        )

    # Determine canonical directed triple and predicate per concept pair
    evidence_by_pair: dict[tuple[UUID, UUID], dict[str, Any]] = {}
    for pair_set, obs_list in pair_observations.items():
        if not obs_list:
            continue
        cids = list(pair_set)
        if len(cids) != 2:
            continue
        c1, c2 = cids[0], cids[1]

        semantic_obs = [o for o in obs_list if o["predicate"] != "co_occurs_with"]
        if semantic_obs:
            best_obs = max(semantic_obs, key=lambda o: o["confidence"])
            subj = best_obs["source_id"]
            obj = best_obs["target_id"]
            best_pred = best_obs["predicate"]
            best_snippet = best_obs["snippet"]
        else:
            votes_c1_to_c2 = sum(o["confidence"] for o in obs_list if o["source_id"] == c1)
            votes_c2_to_c1 = sum(o["confidence"] for o in obs_list if o["source_id"] == c2)
            if votes_c1_to_c2 > votes_c2_to_c1:
                subj, obj = c1, c2
            elif votes_c2_to_c1 > votes_c1_to_c2:
                subj, obj = c2, c1
            else:
                s_id, o_id = sorted([c1, c2], key=str)
                subj, obj = s_id, o_id
            best_pred = "co_occurs_with"
            best_snippet = obs_list[0]["snippet"]

        directed_key = (subj, obj)
        evidence_by_pair[directed_key] = {
            "source_occurrences": max(sum(o["source_occurrences"] for o in obs_list if o["source_id"] == subj), 1),
            "target_occurrences": max(sum(o["target_occurrences"] for o in obs_list if o["target_id"] == obj), 1),
            "predicate": best_pred,
            "snippet": best_snippet,
            "has_semantic_predicate": bool(semantic_obs),
            "undirected_key": tuple(sorted([c1, c2], key=str)),
        }

    return evidence_by_pair, concept_blocks, undirected_pair_blocks, len(blocks)


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
    by_pair_undirected = {
        frozenset([r.source_concept_id, r.target_concept_id]): r
        for r in existing_relationships
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
    doc_pair_evidence: list[tuple[UUID, tuple[UUID, UUID], dict[str, Any]]] = []

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
                src_id, tgt_id = pair
                if src_id in link_counts:
                    pair_data["source_occurrences"] = link_counts[src_id]
                if tgt_id in link_counts:
                    pair_data["target_occurrences"] = link_counts[tgt_id]
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
                            "predicate": "co_occurs_with",
                            "has_semantic_predicate": False,
                            "undirected_key": key,
                        },
                    )
                )

    total_blocks = max(total_workspace_blocks, 1)

    # Compute PMI and NPMI metrics
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

    # Topological Pruning & Degree Bounding (Anti-Hairball)
    generic_node_degree: Counter[UUID] = Counter()
    MAX_GENERIC_DEGREE = 8

    def evidence_priority(item: tuple[UUID, tuple[UUID, UUID], dict[str, Any]]) -> float:
        _, (s, t), pdata = item
        undir = pdata.get("undirected_key", tuple(sorted([s, t], key=str)))
        _, npmi = pair_pmi.get(undir, (0.0, 0.0))
        bonus = 10.0 if pdata.get("has_semantic_predicate") else 0.0
        return bonus + npmi

    doc_pair_evidence.sort(key=evidence_priority, reverse=True)

    persisted_by_directed_pair: dict[tuple[UUID, UUID], ConceptRelationship] = {}

    for doc_id, (subj, obj), pair_data in doc_pair_evidence:
        undir_key = pair_data.get("undirected_key", tuple(sorted([subj, obj], key=str)))
        pmi, npmi = pair_pmi.get(undir_key, (0.0, 0.0))
        has_semantic = pair_data.get("has_semantic_predicate", False)

        # 1. Filter out statistically negative coincidences
        if total_blocks >= 4 and npmi < 0.0 and not has_semantic:
            continue

        # 2. Bound generic degree to prevent hairball
        if not has_semantic and (
            generic_node_degree[subj] >= MAX_GENERIC_DEGREE
            or generic_node_degree[obj] >= MAX_GENERIC_DEGREE
        ):
            continue

        if not has_semantic:
            generic_node_degree[subj] += 1
            generic_node_degree[obj] += 1

        pair_key = (subj, obj)
        undir_set = frozenset([subj, obj])
        relationship = persisted_by_directed_pair.get(pair_key)

        if relationship is None:
            existing_candidate = by_pair_undirected.get(undir_set)
            predicate = pair_data.get("predicate", "co_occurs_with")
            if existing_candidate is not None:
                relationship = existing_candidate
                relationship.source_concept_id = subj
                relationship.target_concept_id = obj
                relationship.relationship_type = predicate
                relationship.pmi = pmi
                relationship.npmi = npmi
            else:
                relationship = ConceptRelationship(
                    workspace_id=workspace_id,
                    source_concept_id=subj,
                    target_concept_id=obj,
                    relationship_type=predicate,
                    pmi=pmi,
                    npmi=npmi,
                )
                session.add(relationship)
                session.flush()

            persisted_by_directed_pair[pair_key] = relationship
        else:
            relationship.pmi = pmi
            relationship.npmi = npmi
            pred = pair_data.get("predicate", "co_occurs_with")
            if pred != "co_occurs_with":
                relationship.relationship_type = pred

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
    """Find a context block or sentence where source and target concepts co-occur and extract a clean snippet."""
    if not text or not text.strip():
        return ""

    src_tokens = [normalize_word(w) for w in WORD_PATTERN.findall(source_name)]
    tgt_tokens = [normalize_word(w) for w in WORD_PATTERN.findall(target_name)]
    if not src_tokens or not tgt_tokens:
        return ""

    blocks = extract_context_blocks(text)

    # 1. Prefer sentence-level match where both appear
    for block in blocks:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", block) if s.strip()]
        for sentence in sentences:
            s_norm = [normalize_word(w) for w in WORD_PATTERN.findall(sentence)]
            if _find_concept_positions(s_norm, src_tokens) and _find_concept_positions(s_norm, tgt_tokens):
                clean_sent = " ".join(sentence.split())
                if len(clean_sent) <= 260:
                    return clean_sent
                return clean_sent[:257] + "..."

    # 2. Fallback to block-level proximity
    for block in blocks:
        tokens = [normalize_word(w) for w in WORD_PATTERN.findall(block)]
        src_pos = _find_concept_positions(tokens, src_tokens)
        tgt_pos = _find_concept_positions(tokens, tgt_tokens)
        if src_pos and tgt_pos:
            min_dist = min(abs(s[0] - t[0]) for s in src_pos for t in tgt_pos)
            if min_dist <= 35:
                clean_block = " ".join(block.split())
                if len(clean_block) <= 260:
                    return clean_block
                return clean_block[:257] + "..."

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
            undir_key = tuple(
                sorted([relationship.source_concept_id, relationship.target_concept_id], key=str)
            )
            if undir_key in pair_pmi:
                pmi_val, npmi_val = pair_pmi[undir_key]
                relationship.pmi = pmi_val
                relationship.npmi = npmi_val
