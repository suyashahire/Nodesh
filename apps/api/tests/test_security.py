"""Automated security regression tests for strict limits, magic bytes, quotas, and headers."""

import io
from pathlib import Path
from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def test_security_headers_present_on_all_responses(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "no-referrer"
    assert headers.get("Cross-Origin-Resource-Policy") == "same-site"
    assert "camera=()" in headers.get("Permissions-Policy", "")
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")


def test_rejects_spoofed_pdf_missing_magic_bytes(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # File named .pdf but containing plain text without %PDF- signature
    fake_pdf = b"Hello, this is just plain text disguised as a PDF."
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
    )
    assert response.status_code == 415
    assert "missing %PDF- file signature" in response.json()["detail"]


def test_rejects_spoofed_docx_missing_zip_header(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # File named .docx but not a valid PK zip archive
    fake_docx = b"Plain text disguised as a docx file."
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={
            "file": (
                "fake.docx",
                fake_docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 415
    assert "missing PK zip signature" in response.json()["detail"]


def test_rejects_binary_null_bytes_in_text_upload(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # File named .txt containing binary null bytes
    binary_payload = b"Text header\x00\x01\x02\x03corrupted binary data"
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("malicious.txt", binary_payload, "text/plain")},
    )
    assert response.status_code == 415
    assert "binary null bytes detected" in response.json()["detail"]


def test_rejects_binary_null_bytes_in_csv_upload(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    binary_payload = b"col1,col2\nval1,\x00\x01corrupted"
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("malicious.csv", binary_payload, "text/csv")},
    )
    assert response.status_code == 415
    assert "binary null bytes detected" in response.json()["detail"]


def test_rejects_executable_signature_in_text_upload(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # Windows PE executable starting with MZ
    exe_payload = b"MZ\x90\x00\x03\x00\x00\x00"
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("malware.txt", exe_payload, "text/plain")},
    )
    assert response.status_code == 415
    assert "executable binary signature detected" in response.json()["detail"]


def test_sanitizes_bidi_override_characters_in_filename(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # Filename containing right-to-left override \u202E
    bidi_filename = "harmless\u202eexe.txt"
    content = b"Content of legitimate text document."
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (bidi_filename, content, "text/plain")},
    )
    assert response.status_code == 201
    clean_name = response.json()["original_filename"]
    assert "\u202e" not in clean_name
    assert clean_name == "harmlessexe.txt"


def test_rejects_oversized_upload(client: TestClient, monkeypatch) -> None:
    from dataclasses import replace
    from nodesh_api import config
    from nodesh_api.routers import documents as doc_router
    from nodesh_api import storage

    # Temporarily set max_upload_bytes to 500 bytes for testing
    custom = replace(config.get_settings(), max_upload_bytes=500)
    monkeypatch.setattr(config, "get_settings", lambda: custom)
    monkeypatch.setattr(doc_router, "get_settings", lambda: custom)
    monkeypatch.setattr(storage, "get_settings", lambda: custom)

    workspace_id = create_workspace(client)
    oversized_data = b"A" * 600
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("oversized.txt", oversized_data, "text/plain")},
    )
    assert response.status_code == 413
    assert "500 bytes or smaller" in response.json()["detail"]


def test_enforces_workspace_document_limit(client: TestClient, monkeypatch) -> None:
    from dataclasses import replace
    from nodesh_api import config
    from nodesh_api.routers import documents as doc_router

    # Set max documents to 2 for quota test
    custom = replace(config.get_settings(), max_workspace_documents=2)
    monkeypatch.setattr(config, "get_settings", lambda: custom)
    monkeypatch.setattr(doc_router, "get_settings", lambda: custom)

    workspace_id = create_workspace(client)
    # Upload 1
    res1 = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("doc1.txt", b"First document text.", "text/plain")},
    )
    assert res1.status_code == 201

    # Upload 2
    res2 = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("doc2.txt", b"Second document text.", "text/plain")},
    )
    assert res2.status_code == 201

    # Upload 3 (exceeds limit of 2)
    res3 = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("doc3.txt", b"Third document text.", "text/plain")},
    )
    assert res3.status_code == 400
    assert "Workspace document limit reached" in res3.json()["detail"]


def test_rejects_excessive_json_request_body(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    # Payload over 1MB sent to a JSON endpoint
    giant_payload = {"key": "X" * (1024 * 1024 + 50)}
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/concepts/merge",
        json=giant_payload,
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]
