from fastapi.testclient import TestClient

from app.main import app


def test_health_live() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/live")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "documind-api"
