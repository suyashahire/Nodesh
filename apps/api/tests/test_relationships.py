from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def upload_and_extract_concepts(client: TestClient, workspace_id: str, filename: str, content: str) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (filename, content.encode(), "text/plain")},
    )
    assert response.status_code == 201


def test_extracts_resolved_relationships_with_document_evidence(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    upload_and_extract_concepts(
        client,
        workspace_id,
        "research.txt",
        "Knowledge graph maps sources. The evidence confirms it. Knowledge graph maps sources. The evidence confirms it.",
    )
    upload_and_extract_concepts(
        client,
        workspace_id,
        "notes.txt",
        "Knowledge graph links data. The evidence confirms it. Knowledge graph links data. The evidence confirms it.",
    )
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200

    extracted = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")

    assert extracted.status_code == 200
    payload = extracted.json()
    assert payload["documents_analyzed"] == 2
    relationship = next(
        item
        for item in payload["relationships"]
        if {item["source_name"], item["target_name"]} == {"knowledge graph", "evidence confirm"}
    )
    assert relationship["relationship_type"] == "co_occurs_with"
    assert relationship["document_count"] == 2
    assert relationship["strength"] == 8.0

    evidence = client.get(
        f"/api/v1/workspaces/{workspace_id}/relationships/{relationship['id']}/evidence"
    )
    assert evidence.status_code == 200
    assert [item["original_filename"] for item in evidence.json()] == ["notes.txt", "research.txt"]


def test_relationship_extraction_is_idempotent(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    upload_and_extract_concepts(
        client,
        workspace_id,
        "ideas.txt",
        "Knowledge graph links ideas. Knowledge graph links ideas.",
    )
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200

    first = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    second = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")

    assert second.status_code == 200
    assert [
        (item["id"], item["source_concept_id"], item["target_concept_id"], item["document_count"], item["strength"])
        for item in second.json()["relationships"]
    ] == [
        (item["id"], item["source_concept_id"], item["target_concept_id"], item["document_count"], item["strength"])
        for item in first.json()["relationships"]
    ]


def test_relationships_are_isolated_to_their_workspace(client: TestClient) -> None:
    first_workspace_id = create_workspace(client)
    second_workspace_id = create_workspace(client)
    upload_and_extract_concepts(
        client,
        first_workspace_id,
        "private.txt",
        "Private graph connects evidence. Private graph connects evidence.",
    )
    assert client.post(f"/api/v1/workspaces/{first_workspace_id}/concepts/extract").status_code == 200
    assert client.post(f"/api/v1/workspaces/{first_workspace_id}/relationships/extract").status_code == 200

    response = client.get(f"/api/v1/workspaces/{second_workspace_id}/relationships")
    assert response.status_code == 200
    assert response.json() == []


def test_proximity_isolates_unrelated_paragraphs(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    doc_text = (
        "Built high-performance REST APIs using Python, FastAPI, and MongoDB. "
        "Built high-performance REST APIs using Python, FastAPI, and MongoDB.\n\n"
        "Graduated from Maharashtra State Board with distinction in physics. "
        "Graduated from Maharashtra State Board with distinction in physics."
    )
    upload_and_extract_concepts(client, workspace_id, "resume.txt", doc_text)
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200

    response = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert response.status_code == 200
    relationships = response.json()["relationships"]

    pair_names = {
        tuple(sorted([rel["source_name"], rel["target_name"]]))
        for rel in relationships
    }
    # Verify concepts in different paragraphs are NOT connected
    for name_a, name_b in pair_names:
        assert not (
            ("python" in name_a and "maharashtra state board" in name_b)
            or ("python" in name_b and "maharashtra state board" in name_a)
        )
        assert not (
            ("fastapi" in name_a and "maharashtra state board" in name_b)
            or ("fastapi" in name_b and "maharashtra state board" in name_a)
        )


def test_pmi_and_npmi_recorded_on_relationships(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    doc_text = (
        "REST API built with Python and FastAPI.\n\n"
        "REST API built with Python and FastAPI.\n\n"
        "Standalone section about databases and storage."
    )
    upload_and_extract_concepts(client, workspace_id, "backend.txt", doc_text)
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200

    response = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert response.status_code == 200
    relationships = response.json()["relationships"]
    assert relationships
    for rel in relationships:
        assert "pmi" in rel
        assert "npmi" in rel
        assert isinstance(rel["pmi"], float)
        assert isinstance(rel["npmi"], float)
        assert -1.0 <= rel["npmi"] <= 1.0


def test_relationship_predicates_are_typed(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    doc_text = (
        "Bachelor of Computer Engineering at Maharashtra State Board.\n\n"
        "Bachelor of Computer Engineering at Maharashtra State Board."
    )
    upload_and_extract_concepts(client, workspace_id, "edu.txt", doc_text)
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200

    response = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert response.status_code == 200
    relationships = response.json()["relationships"]
    assert any(r["relationship_type"] == "affiliated_with" for r in relationships)


def test_subject_predicate_object_directionality(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    doc_text = (
        "FastAPI utilizes Pydantic for data validation. "
        "FastAPI utilizes Pydantic for data validation.\n\n"
        "Knowledge graphs are powered by PageRank. "
        "Knowledge graphs are powered by PageRank."
    )
    upload_and_extract_concepts(client, workspace_id, "spo.txt", doc_text)
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200

    response = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert response.status_code == 200
    relationships = response.json()["relationships"]

    # Active voice: FastAPI utilizes Pydantic -> source=fastapi, target=pydantic, rel=uses
    fastapi_pydantic = next(
        (
            r
            for r in relationships
            if r["source_name"] == "fastapi" and r["target_name"] == "pydantic"
        ),
        None,
    )
    assert fastapi_pydantic is not None
    assert fastapi_pydantic["relationship_type"] == "uses"

    # Passive voice: Knowledge graphs are powered by PageRank -> source=pagerank, target=knowledge graph, rel=powers
    powers_rel = next(
        (r for r in relationships if r["relationship_type"] == "powers"), None
    )
    assert powers_rel is not None
    assert powers_rel["source_name"] == "pagerank"
    assert powers_rel["target_name"] == "knowledge graph"




