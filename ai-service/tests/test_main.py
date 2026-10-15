from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_signal_placeholder() -> None:
    res = client.post("/v1/signal", json={"symbol": "BTC/USDT"})
    assert res.status_code == 200
    assert res.json()["direction"] == "hold"
