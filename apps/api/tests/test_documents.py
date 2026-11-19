from pathlib import Path

from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_extract_and_read_text_document(client: TestClient, tmp_path: Path) -> None:
    workspace_id = create_workspace(client)

    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("notes.txt", b"Nodesh connects related ideas.", "text/plain")},
    )

    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["original_filename"] == "notes.txt"
    assert document["media_type"] == "text/plain"
    assert document["extracted_characters"] == len("Nodesh connects related ideas.")
    assert (tmp_path / "uploads" / workspace_id).is_dir()

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/documents")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document["id"]]

    detail = client.get(f"/api/v1/workspaces/{workspace_id}/documents/{document['id']}")
    assert detail.status_code == 200
    assert detail.json()["extracted_text"] == "Nodesh connects related ideas."


def test_rejects_unsupported_document_format(client: TestClient) -> None:
    workspace_id = create_workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("archive.zip", b"not a document", "application/zip")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Supported formats are PDF, DOCX, TXT, Markdown, and CSV"}


def test_uploads_and_extracts_csv_document(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    csv_content = b"Concept,Domain,Description\nKnowledge Graph,AI,Connected network of semantic entities.\nFastAPI,Web,High performance modern Python API framework."

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("concepts.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    document = response.json()
    assert document["original_filename"] == "concepts.csv"
    assert document["media_type"] == "text/csv"
    assert document["extraction_status"] == "completed"

    detail = client.get(f"/api/v1/workspaces/{workspace_id}/documents/{document['id']}")
    assert detail.status_code == 200
    extracted_text = detail.json()["extracted_text"]
    assert "Knowledge Graph" in extracted_text
    assert "FastAPI" in extracted_text
    assert "Connected network of semantic entities." in extracted_text


def test_documents_are_isolated_to_their_workspace(client: TestClient) -> None:
    first_workspace_id = create_workspace(client)
    second_workspace_id = create_workspace(client)
    uploaded = client.post(
        f"/api/v1/workspaces/{first_workspace_id}/documents",
        files={"file": ("private.md", b"# Private\nOnly the first workspace sees this.", "text/markdown")},
    )
    document_id = uploaded.json()["id"]

    response = client.get(
        f"/api/v1/workspaces/{second_workspace_id}/documents/{document_id}"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_delete_document_removes_file_and_record(client: TestClient, tmp_path: Path) -> None:
    workspace_id = create_workspace(client)
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("to_delete.txt", b"delete me later", "text/plain")},
    )
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["id"]

    # Verify listed
    listed = client.get(f"/api/v1/workspaces/{workspace_id}/documents").json()
    assert any(d["id"] == doc_id for d in listed)

    # Delete
    del_res = client.delete(f"/api/v1/workspaces/{workspace_id}/documents/{doc_id}")
    assert del_res.status_code == 204

    # Verify not listed anymore
    listed_after = client.get(f"/api/v1/workspaces/{workspace_id}/documents").json()
    assert not any(d["id"] == doc_id for d in listed_after)

    # Verify 404 on get detail
    detail = client.get(f"/api/v1/workspaces/{workspace_id}/documents/{doc_id}")
    assert detail.status_code == 404


def test_delete_document_purges_orphaned_concepts_and_graph(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("ml.txt", b"Neural networks learn deep representations using gradient descent.", "text/plain")},
    )
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["id"]

    # Analyze to populate concepts & graph
    analyze_res = client.post(f"/api/v1/workspaces/{workspace_id}/analyze")
    assert analyze_res.status_code == 200
    assert len(analyze_res.json()["concepts"]) > 0

    # Delete the only document
    del_res = client.delete(f"/api/v1/workspaces/{workspace_id}/documents/{doc_id}")
    assert del_res.status_code == 204

    # Graph and concepts should now be empty
    graph_res = client.get(f"/api/v1/workspaces/{workspace_id}/graph")
    assert graph_res.status_code == 200
    assert len(graph_res.json()["nodes"]) == 0
    assert len(graph_res.json()["edges"]) == 0

    # Analyze on empty workspace should also return 0 concepts & 0 relationships
    reanalyze_res = client.post(f"/api/v1/workspaces/{workspace_id}/analyze")
    assert reanalyze_res.status_code == 200
    assert reanalyze_res.json()["documents_analyzed"] == 0
    assert len(reanalyze_res.json()["concepts"]) == 0
    assert len(reanalyze_res.json()["relationships"]) == 0
    assert len(reanalyze_res.json()["graph"]["nodes"]) == 0


