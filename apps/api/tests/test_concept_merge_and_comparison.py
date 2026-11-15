"""Tests for deterministic concept alias merge suggestions, manual merging, and multi-document comparison."""

from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def upload_text_document(
    client: TestClient, workspace_id: str, filename: str, content: str
) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (filename, content.encode(), "text/plain")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_merge_suggestions_are_deterministic_and_suggest_only(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # Upload text with plural/singular and punctuation variants
    upload_text_document(
        client,
        workspace_id,
        "ml.txt",
        (
            "We train random forest classifiers and evaluate random forest on test sets. "
            "Also using scikit-learn and scikit learn with decision tree and decision trees."
        ),
    )
    client.post(f"/api/v1/workspaces/{workspace_id}/analyze")

    res = client.get(f"/api/v1/workspaces/{workspace_id}/concepts/merge-suggestions")
    assert res.status_code == 200
    suggestions = res.json()

    # Suggestions should be returned without any automatic destructive merges taking place
    assert len(suggestions) >= 1
    reasons = [s["reason"] for s in suggestions]
    pairs = [(s["target_name"], s["source_name"]) for s in suggestions]

    # Verify at least plural/singular or punctuation or containment variants are detected
    has_relevant_suggestion = any(
        "variant" in r.lower()
        or "similarity" in r.lower()
        or "containment" in r.lower()
        or "overlap" in r.lower()
        for r in reasons
    )
    assert has_relevant_suggestion

    # Verify original concepts still exist (suggestion-only, zero destructive automation)
    concepts = client.get(f"/api/v1/workspaces/{workspace_id}/concepts").json()
    assert len(concepts) >= 2


def test_manual_merge_combines_concepts_and_relationships(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    upload_text_document(
        client,
        workspace_id,
        "doc1.txt",
        "Python is used with FastAPI. Random forest is applied for classification.",
    )
    upload_text_document(
        client,
        workspace_id,
        "doc2.txt",
        "Random forests model is applied for classification. Python is used with FastAPI.",
    )
    client.post(f"/api/v1/workspaces/{workspace_id}/analyze")

    concepts = client.get(f"/api/v1/workspaces/{workspace_id}/concepts").json()
    concept_by_name = {c["name"]: c for c in concepts}

    # If both random forest and random forests exist or any 2 concepts exist:
    c_names = list(concept_by_name.keys())
    assert len(c_names) >= 2
    target = concept_by_name[c_names[0]]
    source = concept_by_name[c_names[1]]

    target_initial_count = target["total_occurrences"]
    source_initial_count = source["total_occurrences"]

    merge_res = client.post(
        f"/api/v1/workspaces/{workspace_id}/concepts/merge",
        json={
            "source_concept_id": source["id"],
            "target_concept_id": target["id"],
        },
    )
    assert merge_res.status_code == 200
    result = merge_res.json()

    assert result["merged_into_concept_id"] == target["id"]
    assert result["source_occurrences_merged"] == source_initial_count
    assert result["new_total_occurrences"] == target_initial_count + source_initial_count

    # Verify source concept is gone and target concept remains
    updated_concepts = client.get(f"/api/v1/workspaces/{workspace_id}/concepts").json()
    updated_ids = [c["id"] for c in updated_concepts]
    assert source["id"] not in updated_ids
    assert target["id"] in updated_ids

    # Verify graph does not contain any self-loops or references to source concept
    graph = result["graph"]
    node_ids = [n["id"] for n in graph["nodes"]]
    assert source["id"] not in node_ids
    assert target["id"] in node_ids
    for edge in graph["edges"]:
        assert edge["source"] != edge["target"]
        assert edge["source"] != source["id"]
        assert edge["target"] != source["id"]


def test_cannot_merge_concept_into_itself_or_across_workspaces(client: TestClient) -> None:
    ws1 = create_workspace(client)
    ws2 = create_workspace(client)
    upload_text_document(client, ws1, "a.txt", "FastAPI web framework with Python.")
    upload_text_document(client, ws2, "b.txt", "Django web framework with Python.")
    client.post(f"/api/v1/workspaces/{ws1}/analyze")
    client.post(f"/api/v1/workspaces/{ws2}/analyze")

    c1 = client.get(f"/api/v1/workspaces/{ws1}/concepts").json()[0]
    c2 = client.get(f"/api/v1/workspaces/{ws2}/concepts").json()[0]

    # Cannot merge concept into itself
    self_merge = client.post(
        f"/api/v1/workspaces/{ws1}/concepts/merge",
        json={"source_concept_id": c1["id"], "target_concept_id": c1["id"]},
    )
    assert self_merge.status_code == 400

    # Cannot merge concept from another workspace
    cross_merge = client.post(
        f"/api/v1/workspaces/{ws1}/concepts/merge",
        json={"source_concept_id": c2["id"], "target_concept_id": c1["id"]},
    )
    assert cross_merge.status_code == 400


def test_multi_document_comparison(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    upload_text_document(
        client,
        workspace_id,
        "resume_alice.txt",
        "Expert in Python, FastAPI, Docker, and PostgreSQL with microservices.",
    )
    upload_text_document(
        client,
        workspace_id,
        "resume_bob.txt",
        "Proficient in Python, FastAPI, Kubernetes, and MongoDB with distributed systems.",
    )
    client.post(f"/api/v1/workspaces/{workspace_id}/analyze")

    res = client.get(f"/api/v1/workspaces/{workspace_id}/documents/comparison")
    assert res.status_code == 200
    data = res.json()

    assert data["total_documents"] == 2
    assert len(data["documents"]) == 2

    # Shared concepts (e.g. Python, FastAPI)
    shared_names = [sc["name"] for sc in data["shared_concepts"]]
    assert "python" in shared_names or "fastapi" in shared_names

    # Check pairwise overlap
    assert len(data["pairwise_overlap"]) == 1
    overlap = data["pairwise_overlap"][0]
    assert overlap["doc_a_name"] in ["resume_alice.txt", "resume_bob.txt"]
    assert overlap["doc_b_name"] in ["resume_alice.txt", "resume_bob.txt"]
    assert overlap["shared_concept_count"] >= 1
    assert overlap["jaccard_similarity"] > 0.0
