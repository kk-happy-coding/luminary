

ENV_PAYLOAD = {
    "name": "Morpheus Prod",
    "base_url": "https://morpheus.example.com",
    "auth": {
        "type": "bearer",
        "token": "super-secret-token",
        "bearer_prefix": "BEARER",
    },
    "verify_ssl": False,
}


def test_create_environment(client):
    resp = client.post("/api/environments", json=ENV_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Morpheus Prod"
    assert data["base_url"] == "https://morpheus.example.com"
    assert data["verify_ssl"] is False
    assert "id" in data
    assert "created_at" in data


def test_secret_not_exposed(client):
    resp = client.post("/api/environments", json=ENV_PAYLOAD)
    data = resp.json()
    auth = data["auth"]
    # Token must not be returned
    assert "token" not in auth
    assert "password" not in auth
    # But flags must be present
    assert auth["has_token"] is True
    assert auth["has_password"] is False
    assert auth["bearer_prefix"] == "BEARER"


def test_list_environments(client):
    client.post("/api/environments", json=ENV_PAYLOAD)
    client.post("/api/environments", json={**ENV_PAYLOAD, "name": "Dev"})
    resp = client.get("/api/environments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_environment(client):
    created = client.post("/api/environments", json=ENV_PAYLOAD).json()
    env_id = created["id"]
    resp = client.get(f"/api/environments/{env_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == env_id


def test_get_environment_not_found(client):
    resp = client.get("/api/environments/doesnotexist")
    assert resp.status_code == 404


def test_update_environment(client):
    created = client.post("/api/environments", json=ENV_PAYLOAD).json()
    env_id = created["id"]
    resp = client.put(f"/api/environments/{env_id}", json={"name": "Updated Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["base_url"] == ENV_PAYLOAD["base_url"]


def test_update_environment_not_found(client):
    resp = client.put("/api/environments/ghost", json={"name": "X"})
    assert resp.status_code == 404


def test_delete_environment(client):
    created = client.post("/api/environments", json=ENV_PAYLOAD).json()
    env_id = created["id"]
    resp = client.delete(f"/api/environments/{env_id}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}
    # Verify it's gone
    resp2 = client.get(f"/api/environments/{env_id}")
    assert resp2.status_code == 404


def test_delete_environment_not_found(client):
    resp = client.delete("/api/environments/ghost")
    assert resp.status_code == 404
