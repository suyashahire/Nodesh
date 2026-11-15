from fastapi.testclient import TestClient

from nodesh_api.main import app


def test_health_check_reports_healthy_service() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "nodesh-api"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
