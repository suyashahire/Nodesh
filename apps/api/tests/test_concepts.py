from fastapi.testclient import TestClient

from nodesh_api.services.concept_extraction import extract_concepts


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def upload_text_document(client: TestClient, workspace_id: str, filename: str, content: str) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (filename, content.encode(), "text/plain")},
    )
    assert response.status_code == 201


def test_extractor_prefers_repeated_meaningful_phrases() -> None:
    candidates = extract_concepts(
        "A knowledge graph connects evidence. A knowledge graph connects documents."
    )

    knowledge_graph = next(candidate for candidate in candidates if candidate.name == "knowledge graph")
    assert knowledge_graph.occurrence_count == 2
    assert knowledge_graph.score == 6


def test_extractor_handles_trigrams_and_deduplication() -> None:
    candidates = extract_concepts(
        "Deep learning model processes inputs. Deep learning model generates outputs."
    )
    names = [c.name for c in candidates]
    assert "deep learning model" in names
    trigram = next(c for c in candidates if c.name == "deep learning model")
    assert trigram.occurrence_count == 2
    assert trigram.score == 10.0
    # Component words like 'deep' shouldn't duplicate as single words if they don't appear separately
    assert "deep" not in names



def test_extracts_and_aggregates_workspace_concepts(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    upload_text_document(
        client,
        workspace_id,
        "research.txt",
        "Knowledge graph maps sources. Knowledge graph maps evidence.",
    )
    upload_text_document(
        client,
        workspace_id,
        "notes.txt",
        "Knowledge graph supports discovery. Knowledge graph supports context.",
    )

    analyzed = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")

    assert analyzed.status_code == 200
    payload = analyzed.json()
    assert payload["documents_analyzed"] == 2
    knowledge_graph = next(item for item in payload["concepts"] if item["name"] == "knowledge graph")
    assert knowledge_graph["document_count"] == 2
    assert knowledge_graph["total_occurrences"] == 4

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/concepts")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [item["id"] for item in payload["concepts"]]

    repeated = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")
    assert repeated.status_code == 200
    assert repeated.json()["concepts"] == payload["concepts"]


def test_concepts_are_not_visible_to_another_workspace(client: TestClient) -> None:
    first_workspace_id = create_workspace(client)
    second_workspace_id = create_workspace(client)
    upload_text_document(
        client,
        first_workspace_id,
        "private.txt",
        "Private analysis Private analysis Private analysis.",
    )
    assert client.post(f"/api/v1/workspaces/{first_workspace_id}/concepts/extract").status_code == 200

    response = client.get(f"/api/v1/workspaces/{second_workspace_id}/concepts")
    assert response.status_code == 200
    assert response.json() == []


def test_tfidf_ranking_downweights_common_fillers() -> None:
    text = (
        "Section one project. Built with FastAPI and MongoDB.\n\n"
        "Section two project. Another document section.\n\n"
        "Section three project. Another document section.\n\n"
        "Section four project. Another document section."
    )
    candidates = extract_concepts(text, limit=10, use_tfidf=True)
    c_map = {c.name: c for c in candidates}
    # Distinctive tech term should have higher TF-IDF than ubiquitous 'project'
    assert "fastapi" in c_map
    assert "project" in c_map
    assert c_map["fastapi"].tfidf_score > c_map["project"].tfidf_score

