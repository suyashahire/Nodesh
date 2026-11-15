from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def test_analyze_pipeline_builds_concepts_relationships_and_graph(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={
            "file": (
                "research.txt",
                b"Knowledge graph connects evidence. Knowledge graph connects sources.",
                "text/plain",
            )
        },
    )
    assert uploaded.status_code == 201

    analyzed = client.post(f"/api/v1/workspaces/{workspace_id}/analyze")
    assert analyzed.status_code == 200
    data = analyzed.json()

    assert data["documents_analyzed"] == 1
    assert len(data["concepts"]) > 0
    assert "graph" in data
    assert len(data["graph"]["nodes"]) == len(data["concepts"])
    assert len(data["relationships"]) == len(data["graph"]["edges"])


def test_analyze_pipeline_requires_workspace(client: TestClient) -> None:
    import uuid
    response = client.post(f"/api/v1/workspaces/{uuid.uuid4()}/analyze")
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}
