"""Deterministic suggestion-only alias detection and manual concept merging."""

from difflib import SequenceMatcher
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept, DocumentConcept
from nodesh_api.models.relationship import ConceptRelationship, RelationshipEvidence
from nodesh_api.schemas.concept import ConceptMergeResult, ConceptMergeSuggestion
from nodesh_api.services.concepts import _refresh_workspace_aggregates
from nodesh_api.services.graph import build_workspace_graph


def find_merge_suggestions(
    session: Session, workspace_id: UUID
) -> list[ConceptMergeSuggestion]:
    """Find potential concept aliases using deterministic string similarity rules."""
    concepts = list(
        session.scalars(
            select(Concept)
            .where(Concept.workspace_id == workspace_id)
            .order_by(Concept.name)
        )
    )

    suggestions: list[ConceptMergeSuggestion] = []
    seen_pairs: set[tuple[UUID, UUID]] = set()

    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            ca, cb = concepts[i], concepts[j]

            # Choose canonical target (more occurrences / documents) and alias source
            if (ca.total_occurrences, ca.document_count) >= (
                cb.total_occurrences,
                cb.document_count,
            ):
                target, source = ca, cb
            else:
                target, source = cb, ca

            pair_key = (source.id, target.id)
            if pair_key in seen_pairs:
                continue

            sa = target.name.lower().strip()
            sb = source.name.lower().strip()

            score = 0.0
            reason = ""

            # Rule 1: Punctuation/hyphen/space variance
            norm_a = re.sub(r"[\s\-_]+", " ", sa)
            norm_b = re.sub(r"[\s\-_]+", " ", sb)
            if norm_a == norm_b:
                score = 0.98
                reason = "Punctuation/hyphen variant"

            tokens_a = set(re.split(r"[\s\-_]+", sa))
            tokens_b = set(re.split(r"[\s\-_]+", sb))

            # Rule 2: Plural / singular stem variant
            if not reason:
                stemmed_a = {w[:-1] if w.endswith("s") and len(w) > 3 else w for w in tokens_a}
                stemmed_b = {w[:-1] if w.endswith("s") and len(w) > 3 else w for w in tokens_b}
                if stemmed_a == stemmed_b:
                    score = 0.95
                    reason = "Plural/singular variant"

            # Rule 3: Sub-phrase / token containment
            if not reason:
                intersection = tokens_a & tokens_b
                union = tokens_a | tokens_b
                jaccard = len(intersection) / len(union) if union else 0.0
                if (tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a)) and jaccard >= 0.50:
                    score = round(0.70 + 0.25 * jaccard, 2)
                    reason = f"Sub-phrase containment ({int(jaccard * 100)}%)"

            # Rule 4: String Edit Similarity (difflib)
            if not reason:
                ratio = SequenceMatcher(None, sa, sb).ratio()
                if ratio >= 0.80:
                    score = round(ratio, 2)
                    reason = f"Text similarity ({int(ratio * 100)}%)"

            if score >= 0.80 and reason:
                seen_pairs.add(pair_key)
                suggestions.append(
                    ConceptMergeSuggestion(
                        source_concept_id=source.id,
                        source_name=source.name,
                        target_concept_id=target.id,
                        target_name=target.name,
                        similarity=score,
                        reason=reason,
                    )
                )

    suggestions.sort(key=lambda s: (-s.similarity, s.target_name, s.source_name))
    return suggestions


def merge_concepts(
    session: Session,
    workspace_id: UUID,
    source_concept_id: UUID,
    target_concept_id: UUID,
) -> ConceptMergeResult:
    """Deterministically merge source concept into target concept."""
    if source_concept_id == target_concept_id:
        raise ValueError("Cannot merge a concept into itself")

    source_concept = session.get(Concept, source_concept_id)
    target_concept = session.get(Concept, target_concept_id)

    if source_concept is None or source_concept.workspace_id != workspace_id:
        raise ValueError("Source concept not found in workspace")
    if target_concept is None or target_concept.workspace_id != workspace_id:
        raise ValueError("Target concept not found in workspace")

    source_occurrences = source_concept.total_occurrences

    # 1. Reassign DocumentConcept links
    source_doc_links = list(
        session.scalars(
            select(DocumentConcept).where(DocumentConcept.concept_id == source_concept_id)
        )
    )
    for s_link in source_doc_links:
        t_link = session.get(DocumentConcept, (s_link.document_id, target_concept_id))
        if t_link is not None:
            t_link.occurrence_count += s_link.occurrence_count
            t_link.score = max(t_link.score, s_link.score)
            t_link.tfidf_score = max(t_link.tfidf_score, s_link.tfidf_score)
            session.delete(s_link)
        else:
            new_link = DocumentConcept(
                document_id=s_link.document_id,
                concept_id=target_concept_id,
                occurrence_count=s_link.occurrence_count,
                score=s_link.score,
                tfidf_score=s_link.tfidf_score,
            )
            session.delete(s_link)
            session.flush()
            session.add(new_link)

    session.flush()

    # 2. Reassign ConceptRelationships
    rels = list(
        session.scalars(
            select(ConceptRelationship).where(
                ConceptRelationship.workspace_id == workspace_id,
                (ConceptRelationship.source_concept_id == source_concept_id)
                | (ConceptRelationship.target_concept_id == source_concept_id),
            )
        )
    )

    for rel in rels:
        partner_id = (
            rel.target_concept_id
            if rel.source_concept_id == source_concept_id
            else rel.source_concept_id
        )

        if partner_id == target_concept_id:
            session.delete(rel)
            continue

        if rel.source_concept_id == source_concept_id:
            new_src = target_concept_id
            new_tgt = rel.target_concept_id
        else:
            new_src = rel.source_concept_id
            new_tgt = target_concept_id

        existing_rel = session.scalar(
            select(ConceptRelationship).where(
                ConceptRelationship.workspace_id == workspace_id,
                ConceptRelationship.source_concept_id == new_src,
                ConceptRelationship.target_concept_id == new_tgt,
                ConceptRelationship.relationship_type == rel.relationship_type,
            )
        )

        evidence_items = list(
            session.scalars(
                select(RelationshipEvidence).where(
                    RelationshipEvidence.relationship_id == rel.id
                )
            )
        )

        if existing_rel is not None:
            for ev in evidence_items:
                ex_ev = session.get(RelationshipEvidence, (existing_rel.id, ev.document_id))
                if ex_ev is not None:
                    ex_ev.source_occurrences += ev.source_occurrences
                    ex_ev.target_occurrences += ev.target_occurrences
                    session.delete(ev)
                else:
                    new_ev = RelationshipEvidence(
                        relationship_id=existing_rel.id,
                        document_id=ev.document_id,
                        source_occurrences=ev.source_occurrences,
                        target_occurrences=ev.target_occurrences,
                    )
                    session.delete(ev)
                    session.flush()
                    session.add(new_ev)

            existing_rel.strength += rel.strength
            distinct_docs = len(
                list(
                    session.scalars(
                        select(RelationshipEvidence.document_id)
                        .where(RelationshipEvidence.relationship_id == existing_rel.id)
                        .distinct()
                    )
                )
            )
            existing_rel.document_count = distinct_docs
            session.delete(rel)
        else:
            rel.source_concept_id = new_src
            rel.target_concept_id = new_tgt

    session.flush()

    # 3. Delete source concept
    session.delete(source_concept)
    session.flush()

    # 4. Refresh workspace aggregates
    _refresh_workspace_aggregates(session, workspace_id)

    # 5. Build updated graph & commit
    graph = build_workspace_graph(session, workspace_id)
    session.commit()

    return ConceptMergeResult(
        merged_into_concept_id=target_concept.id,
        merged_concept_name=target_concept.name,
        source_occurrences_merged=source_occurrences,
        new_total_occurrences=target_concept.total_occurrences,
        graph=graph,
    )
