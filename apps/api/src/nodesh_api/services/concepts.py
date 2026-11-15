"""Persistence and aggregation service for extracted concepts."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept, DocumentConcept
from nodesh_api.models.document import Document
from nodesh_api.schemas.concept import ConceptRead
from nodesh_api.services.concept_extraction import extract_concepts


def list_workspace_concepts(session: Session, workspace_id: UUID) -> list[ConceptRead]:
    concepts = list(
        session.scalars(
            select(Concept)
            .where(Concept.workspace_id == workspace_id)
            .order_by(Concept.total_occurrences.desc(), Concept.document_count.desc(), Concept.name)
        )
    )
    result: list[ConceptRead] = []
    for concept in concepts:
        filenames = list(
            session.scalars(
                select(Document.original_filename)
                .join(DocumentConcept, DocumentConcept.document_id == Document.id)
                .where(DocumentConcept.concept_id == concept.id)
                .order_by(Document.original_filename)
            )
        )
        result.append(
            ConceptRead(
                id=concept.id,
                name=concept.name,
                document_count=concept.document_count,
                total_occurrences=concept.total_occurrences,
                tfidf_score=concept.tfidf_score,
                source_documents=filenames,
                created_at=concept.created_at,
                updated_at=concept.updated_at,
            )
        )
    return result


def analyze_workspace(
    session: Session, workspace_id: UUID, *, limit: int = 20,
) -> tuple[int, list[ConceptRead]]:
    documents = list(
        session.scalars(select(Document).where(Document.workspace_id == workspace_id))
    )
    if not documents:
        session.execute(
            delete(DocumentConcept).where(
                DocumentConcept.concept_id.in_(
                    select(Concept.id).where(Concept.workspace_id == workspace_id)
                )
            )
        )
        session.execute(delete(Concept).where(Concept.workspace_id == workspace_id))
        session.commit()
        return 0, []

    corpus_texts = [
        doc.extracted_text for doc in documents if doc.extracted_text and doc.extracted_text.strip()
    ]
    for document in documents:
        _replace_document_concepts(session, document, corpus_texts=corpus_texts, limit=limit)

    _refresh_workspace_aggregates(session, workspace_id)
    session.commit()
    return len(documents), list_workspace_concepts(session, workspace_id)


def _replace_document_concepts(
    session: Session,
    document: Document,
    *,
    corpus_texts: list[str] | None = None,
    limit: int = 20,
) -> None:
    session.execute(delete(DocumentConcept).where(DocumentConcept.document_id == document.id))
    session.flush()

    for candidate in extract_concepts(
        document.extracted_text, limit=limit, corpus_texts=corpus_texts, use_tfidf=True
    ):
        concept = session.scalar(
            select(Concept).where(
                Concept.workspace_id == document.workspace_id,
                Concept.normalized_name == candidate.normalized_name,
            )
        )
        if concept is None:
            concept = Concept(
                workspace_id=document.workspace_id,
                name=candidate.name,
                normalized_name=candidate.normalized_name,
            )
            session.add(concept)
            session.flush()

        session.add(
            DocumentConcept(
                document_id=document.id,
                concept_id=concept.id,
                occurrence_count=candidate.occurrence_count,
                score=candidate.score,
                tfidf_score=candidate.tfidf_score,
            )
        )


def _refresh_workspace_aggregates(session: Session, workspace_id: UUID) -> None:
    concepts = list(
        session.scalars(select(Concept).where(Concept.workspace_id == workspace_id))
    )
    session.flush()
    for concept in concepts:
        links = list(
            session.scalars(
                select(DocumentConcept).where(DocumentConcept.concept_id == concept.id)
            )
        )
        if not links:
            session.delete(concept)
            continue
        concept.document_count = len(links)
        concept.total_occurrences = sum(link.occurrence_count for link in links)
        concept.tfidf_score = round(max((link.tfidf_score for link in links), default=0.0), 3)
