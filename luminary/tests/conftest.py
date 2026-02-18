import pytest
from fastapi.testclient import TestClient



@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Point DATA_DIR at a temp directory so tests never touch /app/data."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def client(tmp_data_dir):
    """TestClient with a fresh in-memory store backed by tmp_path."""
    # Re-import app after patching DATA_DIR
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
async def seeded_env(client):
    """Create a test environment and return the public representation."""
    payload = {
        "name": "Test Env",
        "base_url": "https://example.com",
        "auth": {"type": "bearer", "token": "secret", "bearer_prefix": "Bearer"},
        "verify_ssl": True,
    }
    resp = client.post("/api/environments", json=payload)
    assert resp.status_code == 201
    return resp.json()
