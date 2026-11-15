from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

def test_create_and_resume_anonymous_workspace(client: TestClient) -> None:
    created = client.post("/api/v1/workspaces")

    assert created.status_code == 201
    payload = created.json()
    assert UUID(payload["id"])
    assert datetime.fromisoformat(payload["created_at"])
    assert datetime.fromisoformat(payload["last_active_at"])

    resumed = client.get(f"/api/v1/workspaces/{payload['id']}")

    assert resumed.status_code == 200
    assert resumed.json()["id"] == payload["id"]


def test_unknown_workspace_cannot_be_resumed(client: TestClient) -> None:
    response = client.get(f"/api/v1/workspaces/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}


def test_deleting_workspace_removes_its_data_and_source_files(
    client: TestClient, tmp_path: Path
) -> None:
    workspace_id = client.post("/api/v1/workspaces").json()["id"]
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("private.txt", b"private workspace data", "text/plain")},
    )
    assert uploaded.status_code == 201

    deleted = client.delete(f"/api/v1/workspaces/{workspace_id}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/workspaces/{workspace_id}").status_code == 404
    assert not (tmp_path / "uploads" / workspace_id).exists()


def test_workspace_stats_returns_counts(client: TestClient) -> None:
    workspace_id = client.post("/api/v1/workspaces").json()["id"]

    # Initial stats
    stats = client.get(f"/api/v1/workspaces/{workspace_id}/stats")
    assert stats.status_code == 200
    assert stats.json() == {
        "document_count": 0,
        "concept_count": 0,
        "relationship_count": 0,
        "total_characters": 0,
    }

    # Upload document
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )

    stats2 = client.get(f"/api/v1/workspaces/{workspace_id}/stats").json()
    assert stats2["document_count"] == 1
    assert stats2["total_characters"] == len("hello world")

