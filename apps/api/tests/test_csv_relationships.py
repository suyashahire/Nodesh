"""Tests for enhanced CSV knowledge graph concept and relationship extraction."""

from fastapi.testclient import TestClient


def create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def test_csv_triple_edge_list_extraction(client: TestClient) -> None:
    """CSVs formatted as graph triples (source, relationship, target) extract true directed SPO edges."""
    workspace_id = create_workspace(client)
    csv_content = (
        b"source,relationship,target\n"
        b"FastAPI,uses,Pydantic\n"
        b"FastAPI,runs_on,Python\n"
        b"FastAPI,powers,Nodesh\n"
        b"Nodesh,integrates_with,PostgreSQL\n"
        b"FastAPI,uses,Pydantic\n"
        b"FastAPI,runs_on,Python\n"
        b"FastAPI,powers,Nodesh\n"
        b"Nodesh,integrates_with,PostgreSQL\n"
    )

    upload_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("graph_triples.csv", csv_content, "text/csv")},
    )
    assert upload_resp.status_code == 201

    # Extract concepts
    c_resp = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")
    assert c_resp.status_code == 200
    concepts = c_resp.json()["concepts"]
    concept_names = {c["name"] for c in concepts}
    assert "fastapi" in concept_names
    assert "pydantic" in concept_names
    assert "python" in concept_names
    assert "nodesh" in concept_names
    # Ensure boilerplate words like 'source', 'target', 'relationship' are not concepts
    assert "source" not in concept_names
    assert "target" not in concept_names
    assert "relationship" not in concept_names

    # Extract relationships
    r_resp = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert r_resp.status_code == 200
    relationships = r_resp.json()["relationships"]

    # Verify FastAPI -> uses -> Pydantic
    fastapi_pydantic = next(
        (r for r in relationships if r["source_name"] == "fastapi" and r["target_name"] == "pydantic"),
        None,
    )
    assert fastapi_pydantic is not None
    assert fastapi_pydantic["relationship_type"] == "uses"

    # Verify FastAPI -> runs_on -> Python
    fastapi_python = next(
        (r for r in relationships if r["source_name"] == "fastapi" and r["target_name"] == "python"),
        None,
    )
    assert fastapi_python is not None
    assert fastapi_python["relationship_type"] == "runs_on"

    # Verify FastAPI -> powers -> Nodesh
    fastapi_nodesh = next(
        (r for r in relationships if r["source_name"] == "fastapi" and r["target_name"] == "nodesh"),
        None,
    )
    assert fastapi_nodesh is not None
    assert fastapi_nodesh["relationship_type"] == "powers"

    # Verify Nodesh -> integrates_with -> PostgreSQL
    nodesh_pg = next(
        (r for r in relationships if r["source_name"] == "nodesh" and r["target_name"] == "postgresql"),
        None,
    )
    assert nodesh_pg is not None
    assert nodesh_pg["relationship_type"] in {"integrates_with", "integrated_with"}


def test_csv_tabular_entity_extraction(client: TestClient) -> None:
    """Tabular CSVs (Entity-Attribute rows) map headers to semantic predicates."""
    workspace_id = create_workspace(client)
    csv_content = (
        b"Framework,Language,Database,Platform\n"
        b"FastAPI,Python,PostgreSQL,Docker\n"
        b"Nextjs,TypeScript,PostgreSQL,Vercel\n"
        b"FastAPI,Python,PostgreSQL,Docker\n"
        b"Nextjs,TypeScript,PostgreSQL,Vercel\n"
    )

    upload_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("tech_stack.csv", csv_content, "text/csv")},
    )
    assert upload_resp.status_code == 201

    c_resp = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")
    assert c_resp.status_code == 200

    r_resp = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert r_resp.status_code == 200
    relationships = r_resp.json()["relationships"]

    # FastAPI is built with Python
    fastapi_python = next(
        (r for r in relationships if r["source_name"] == "fastapi" and r["target_name"] == "python"),
        None,
    )
    assert fastapi_python is not None
    assert fastapi_python["relationship_type"] == "built_with"

    # FastAPI integrates with PostgreSQL
    fastapi_pg = next(
        (r for r in relationships if r["source_name"] == "fastapi" and r["target_name"] == "postgresql"),
        None,
    )
    assert fastapi_pg is not None
    assert fastapi_pg["relationship_type"] in {"integrates_with", "integrated_with"}

    # FastAPI runs on Docker
    fastapi_docker = next(
        (r for r in relationships if r["source_name"] == "fastapi" and r["target_name"] == "docker"),
        None,
    )
    assert fastapi_docker is not None
    assert fastapi_docker["relationship_type"] == "runs_on"


def test_csv_multivalue_cells_and_delimiters(client: TestClient) -> None:
    """CSVs with semicolon-separated values in cells link all entities properly."""
    workspace_id = create_workspace(client)
    csv_content = (
        b"Framework;Languages;Databases\n"
        b"FastAPI;Python;PostgreSQL\n"
        b"FastAPI;Python;PostgreSQL\n"
    )

    upload_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("semicolon.csv", csv_content, "text/csv")},
    )
    assert upload_resp.status_code == 201

    c_resp = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")
    assert c_resp.status_code == 200
    concept_names = {c["name"] for c in c_resp.json()["concepts"]}
    assert "fastapi" in concept_names
    assert "python" in concept_names
    assert "postgresql" in concept_names


def test_csv_with_id_column_skips_index(client: TestClient) -> None:
    """CSVs with an initial ID/UUID column select the entity name column as primary Subject."""
    workspace_id = create_workspace(client)
    csv_content = (
        b"id,Tool,Written In,Deployed On\n"
        b"1,Nodesh,Python,Render\n"
        b"2,FastAPI,Python,Docker\n"
        b"1,Nodesh,Python,Render\n"
        b"2,FastAPI,Python,Docker\n"
    )

    upload_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("indexed.csv", csv_content, "text/csv")},
    )
    assert upload_resp.status_code == 201

    c_resp = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")
    assert c_resp.status_code == 200
    concept_names = {c["name"] for c in c_resp.json()["concepts"]}
    assert "nodesh" in concept_names
    assert "fastapi" in concept_names
    assert "python" in concept_names
    assert "render" in concept_names
    assert "docker" in concept_names
    assert "id" not in concept_names

    r_resp = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert r_resp.status_code == 200
    relationships = r_resp.json()["relationships"]

    # Nodesh is built with Python
    nodesh_python = next(
        (r for r in relationships if r["source_name"] == "nodesh" and r["target_name"] == "python"),
        None,
    )
    assert nodesh_python is not None
    assert nodesh_python["relationship_type"] == "built_with"

    # Nodesh runs on Render
    nodesh_render = next(
        (r for r in relationships if r["source_name"] == "nodesh" and r["target_name"] == "render"),
        None,
    )
    assert nodesh_render is not None
    assert nodesh_render["relationship_type"] == "runs_on"


def test_csv_domain_causes_and_improves(client: TestClient) -> None:
    """Domain CSVs with symptoms and treatments map causes and improves predicates."""
    workspace_id = create_workspace(client)
    csv_content = (
        b"Condition,Symptom,Treatment\n"
        b"Hypertension,Headache,Beta Blockers\n"
        b"Hypertension,Headache,Beta Blockers\n"
    )

    upload_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("clinical.csv", csv_content, "text/csv")},
    )
    assert upload_resp.status_code == 201

    c_resp = client.post(f"/api/v1/workspaces/{workspace_id}/concepts/extract")
    assert c_resp.status_code == 200

    r_resp = client.post(f"/api/v1/workspaces/{workspace_id}/relationships/extract")
    assert r_resp.status_code == 200
    relationships = r_resp.json()["relationships"]

    # Hypertension causes Headache
    ht_headache = next(
        (r for r in relationships if r["source_name"] == "hypertension" and r["target_name"] == "headache"),
        None,
    )
    assert ht_headache is not None
    assert ht_headache["relationship_type"] == "causes"

    # Beta Blockers improves Hypertension
    bb_ht = next(
        (r for r in relationships if r["source_name"] == "beta blocker" and r["target_name"] == "hypertension"),
        None,
    )
    assert bb_ht is not None
    assert bb_ht["relationship_type"] == "improves"
