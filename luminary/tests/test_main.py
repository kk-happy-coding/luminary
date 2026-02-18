from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_info():
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Hello World"
    assert data["version"] == "0.1.0"
