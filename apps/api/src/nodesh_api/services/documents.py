"""Document ingestion and lookup domain services."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept, DocumentConcept
from nodesh_api.models.document import Document
from nodesh_api.models.relationship import ConceptRelationship, RelationshipEvidence
from nodesh_api.storage import StoredUpload


def create_document(
    session: Session, *, workspace_id: UUID, upload: StoredUpload, extracted_text: str
) -> Document:
    document = Document(
        workspace_id=workspace_id,
        original_filename=upload.original_filename,
        media_type=upload.media_type,
        storage_key=upload.storage_key,
        size_bytes=upload.size_bytes,
        extracted_characters=len(extracted_text),
        extracted_text=extracted_text,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def list_documents(session: Session, workspace_id: UUID) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc())
        )
    )


def get_document(session: Session, workspace_id: UUID, document_id: UUID) -> Document | None:
    return session.scalar(
        select(Document).where(
            Document.workspace_id == workspace_id, Document.id == document_id
        )
    )


def delete_document(
    session: Session, workspace_id: UUID, document_id: UUID, uploads_directory: Path
) -> bool:
    """Delete a document, its physical file, database row, and purge orphaned concepts/relationships."""
    document = get_document(session, workspace_id, document_id)
    if document is None:
        return False
    # 1. Delete physical file
    physical_path = uploads_directory / document.storage_key
    physical_path.unlink(missing_ok=True)

    # 2. Explicitly delete observation links
    session.execute(delete(DocumentConcept).where(DocumentConcept.document_id == document_id))
    session.execute(delete(RelationshipEvidence).where(RelationshipEvidence.document_id == document_id))
    session.flush()

    # 3. Delete DB row
    session.delete(document)
    session.flush()

    # 4. Clean up any concepts in this workspace that no longer belong to any document
    concepts = list(session.scalars(select(Concept).where(Concept.workspace_id == workspace_id)))
    for concept in concepts:
        has_links = session.scalar(
            select(DocumentConcept.document_id).where(DocumentConcept.concept_id == concept.id).limit(1)
        )
        if has_links is None:
            session.delete(concept)
        else:
            links = list(session.scalars(select(DocumentConcept).where(DocumentConcept.concept_id == concept.id)))
            concept.document_count = len(links)
            concept.total_occurrences = sum(l.occurrence_count for l in links)
            concept.tfidf_score = round(max((l.tfidf_score for l in links), default=0.0), 3)

    # 5. Clean up any relationships that have no evidence remaining
    relationships = list(
        session.scalars(select(ConceptRelationship).where(ConceptRelationship.workspace_id == workspace_id))
    )
    for rel in relationships:
        has_evidence = session.scalar(
            select(RelationshipEvidence.document_id).where(RelationshipEvidence.relationship_id == rel.id).limit(1)
        )
        if has_evidence is None:
            session.delete(rel)
        else:
            evidence = list(session.scalars(select(RelationshipEvidence).where(RelationshipEvidence.relationship_id == rel.id)))
            rel.document_count = len(evidence)
            rel.strength = float(sum(e.source_occurrences * e.target_occurrences for e in evidence))

    session.commit()
    return True
