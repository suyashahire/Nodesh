"""Multi-document comparison service."""

from collections import defaultdict
from itertools import combinations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from nodesh_api.models.concept import Concept, DocumentConcept
from nodesh_api.models.document import Document
from nodesh_api.schemas.comparison import (
    DocumentConceptOverview,
    DocumentPairOverlap,
    SharedConceptOverview,
    WorkspaceDocumentComparison,
)


def compare_workspace_documents(
    session: Session, workspace_id: UUID
) -> WorkspaceDocumentComparison:
    """Analyze concept overlaps and distinctions across workspace documents."""
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at)
        )
    )

    doc_concepts: dict[UUID, set[tuple[UUID, str]]] = defaultdict(set)
    concept_docs: dict[UUID, list[UUID]] = defaultdict(list)
    concept_map: dict[UUID, Concept] = {}

    for doc in documents:
        dc_rows = list(
            session.scalars(
                select(DocumentConcept).where(DocumentConcept.document_id == doc.id)
            )
        )
        for dc in dc_rows:
            concept = session.get(Concept, dc.concept_id)
            if concept is not None:
                concept_map[concept.id] = concept
                doc_concepts[doc.id].add((concept.id, concept.name))
                concept_docs[concept.id].append(doc.id)

    doc_id_to_filename = {doc.id: doc.original_filename for doc in documents}

    # 1. Shared Concepts (present in 2 or more documents)
    shared_concepts_list: list[SharedConceptOverview] = []
    for concept_id, doc_ids in concept_docs.items():
        if len(doc_ids) >= 2:
            concept = concept_map[concept_id]
            shared_concepts_list.append(
                SharedConceptOverview(
                    id=concept.id,
                    name=concept.name,
                    document_count=len(doc_ids),
                    total_occurrences=concept.total_occurrences,
                    document_ids=doc_ids,
                    document_names=[doc_id_to_filename[did] for did in doc_ids],
                )
            )

    shared_concepts_list.sort(key=lambda sc: (-sc.document_count, -sc.total_occurrences, sc.name))

    # 2. Document Overviews (unique concepts per doc)
    doc_overviews: list[DocumentConceptOverview] = []
    for doc in documents:
        c_tuples = doc_concepts[doc.id]
        unique_names = [
            c_name for c_id, c_name in c_tuples if len(concept_docs[c_id]) == 1
        ]
        unique_names.sort()
        doc_overviews.append(
            DocumentConceptOverview(
                document_id=doc.id,
                filename=doc.original_filename,
                total_concepts=len(c_tuples),
                unique_concept_count=len(unique_names),
                unique_concepts=unique_names,
            )
        )

    # 3. Pairwise Document Overlap
    pairwise_overlaps: list[DocumentPairOverlap] = []
    for doc_a, doc_b in combinations(documents, 2):
        names_a = {c_name for _, c_name in doc_concepts[doc_a.id]}
        names_b = {c_name for _, c_name in doc_concepts[doc_b.id]}
        shared_names = sorted(list(names_a & names_b))
        union_count = len(names_a | names_b)
        jaccard = round(len(shared_names) / union_count, 3) if union_count > 0 else 0.0

        pairwise_overlaps.append(
            DocumentPairOverlap(
                doc_a_id=doc_a.id,
                doc_a_name=doc_a.original_filename,
                doc_b_id=doc_b.id,
                doc_b_name=doc_b.original_filename,
                shared_concept_count=len(shared_names),
                jaccard_similarity=jaccard,
                shared_concepts=shared_names,
            )
        )

    pairwise_overlaps.sort(key=lambda p: (-p.shared_concept_count, -p.jaccard_similarity))

    return WorkspaceDocumentComparison(
        workspace_id=workspace_id,
        total_documents=len(documents),
        documents=doc_overviews,
        shared_concepts=shared_concepts_list,
        pairwise_overlap=pairwise_overlaps,
    )
