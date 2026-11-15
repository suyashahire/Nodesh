from fastapi.testclient import TestClient

from nodesh_api.services.textrank import run_textrank


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


def test_textrank_pure_algorithm() -> None:
    sentences = [
        "Machine learning models analyze complex data patterns across large distributed systems.",
        "Data patterns reveal critical insights when processed through machine learning architectures.",
        "The weather today is completely sunny with no clouds in sight.",
        "Deep learning and machine learning provide statistical predictive accuracy for data.",
    ]
    top = run_textrank(sentences, top_k=2, priority_terms=["machine learning", "data patterns"])
    assert len(top) == 2
    # The unrelated weather sentence should not be among the top 2
    assert "The weather today is completely sunny with no clouds in sight." not in top
    # The sentences with overlapping terminology should be selected
    assert any("machine learning" in s.lower() for s in top)


def test_concept_dossier_endpoint(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    text = (
        "Random forest is an ensemble machine learning algorithm for classification and regression tasks. "
        "It operates by constructing a multitude of decision trees at training time. "
        "Random forest models output the class selected by most trees to prevent overfitting. "
        "Supervised learning algorithms require labeled training data to generalize well on test sets."
    )
    upload_text_document(client, workspace_id, "rf_guide.txt", text)

    # Analyze workspace
    client.post(f"/api/v1/workspaces/{workspace_id}/analyze")

    # Get concepts
    concepts_resp = client.get(f"/api/v1/workspaces/{workspace_id}/concepts")
    assert concepts_resp.status_code == 200
    concepts = concepts_resp.json()
    assert len(concepts) > 0

    rf_concept = next(c for c in concepts if "random forest" in c["name"].lower())

    # Fetch dossier
    dossier_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/concepts/{rf_concept['id']}/dossier"
    )
    assert dossier_resp.status_code == 200
    data = dossier_resp.json()

    assert data["concept_id"] == rf_concept["id"]
    assert data["concept_name"] == rf_concept["name"]
    assert len(data["key_sentences"]) >= 1
    assert "rf_guide.txt" in data["source_documents"]
    assert len(data["summary"]) > 10


def test_concept_dossier_not_found(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/concepts/{fake_id}/dossier")
    assert resp.status_code == 404
