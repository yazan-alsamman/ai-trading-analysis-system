from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_openapi_available() -> None:
    client = TestClient(app)
    assert client.get("/openapi.json").status_code == 200
