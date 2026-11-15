from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def prepare_graph(client: TestClient, workspace_id: str) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={
            "file": (
                "research.txt",
                b"Knowledge graph connects evidence. Knowledge graph connects sources.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 201
    assert client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract").status_code == 200
    assert client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract").status_code == 200


def test_graph_snapshot_contains_resolved_nodes_and_edges(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    prepare_graph(client, workspace_id)

    response = client.get(f"/api/v1/workspaces/{workspace_id}/graph")

    assert response.status_code == 200
    graph = response.json()
    node_ids = {node["id"] for node in graph["nodes"]}
    assert node_ids
    assert graph["edges"]
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])


def test_graph_is_isolated_to_its_workspace(client: TestClient) -> None:
    first_workspace_id = create_workspace(client)
    second_workspace_id = create_workspace(client)
    prepare_graph(client, first_workspace_id)

    response = client.get(f"/api/v1/workspaces/{second_workspace_id}/graph")

    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}
