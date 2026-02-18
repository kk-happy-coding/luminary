import httpx
import respx


MORPHEUS_ENV = {
    "name": "Morpheus Test",
    "base_url": "https://mock-morpheus.local",
    "auth": {
        "type": "bearer",
        "token": "test-token",
        "bearer_prefix": "BEARER",
    },
    "verify_ssl": False,
}

API_KEY_ENV = {
    "name": "API Key Env",
    "base_url": "https://mock-api.local",
    "auth": {
        "type": "api_key",
        "token": "my-api-key",
        "header_name": "X-Custom-Key",
    },
    "verify_ssl": True,
}


def _create_env(client, payload=None) -> str:
    payload = payload or MORPHEUS_ENV
    resp = client.post("/api/environments", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


@respx.mock
def test_proxy_get_request(client):
    env_id = _create_env(client)
    respx.get("https://mock-morpheus.local/api/instances").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    resp = client.post(
        "/api/proxy/execute",
        json={"environment_id": env_id, "method": "GET", "path": "/api/instances"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status_code"] == 200
    assert data["body"] == {"data": []}
    assert "duration_ms" in data


@respx.mock
def test_proxy_bearer_injection(client):
    env_id = _create_env(client)
    captured_headers = {}

    def capture(request):
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    respx.get("https://mock-morpheus.local/api/whoami").mock(side_effect=capture)
    resp = client.post(
        "/api/proxy/execute",
        json={"environment_id": env_id, "method": "GET", "path": "/api/whoami"},
    )
    assert resp.status_code == 200
    assert captured_headers.get("authorization") == "BEARER test-token"


@respx.mock
def test_proxy_api_key_injection(client):
    env_id = _create_env(client, API_KEY_ENV)
    captured_headers = {}

    def capture(request):
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    respx.get("https://mock-api.local/items").mock(side_effect=capture)
    resp = client.post(
        "/api/proxy/execute",
        json={"environment_id": env_id, "method": "GET", "path": "/items"},
    )
    assert resp.status_code == 200
    assert captured_headers.get("x-custom-key") == "my-api-key"


@respx.mock
def test_proxy_path_param_substitution(client):
    env_id = _create_env(client)
    respx.get("https://mock-morpheus.local/api/instances/42").mock(
        return_value=httpx.Response(200, json={"id": 42})
    )
    resp = client.post(
        "/api/proxy/execute",
        json={
            "environment_id": env_id,
            "method": "GET",
            "path": "/api/instances/{id}",
            "path_params": {"id": "42"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["body"]["id"] == 42


@respx.mock
def test_proxy_query_params(client):
    env_id = _create_env(client)
    captured_url = {}

    def capture(request):
        captured_url["url"] = str(request.url)
        return httpx.Response(200, json={})

    respx.get("https://mock-morpheus.local/api/instances").mock(side_effect=capture)
    resp = client.post(
        "/api/proxy/execute",
        json={
            "environment_id": env_id,
            "method": "GET",
            "path": "/api/instances",
            "query_params": {"max": "10", "offset": "0"},
        },
    )
    assert resp.status_code == 200
    assert "max=10" in captured_url["url"]
    assert "offset=0" in captured_url["url"]


@respx.mock
def test_proxy_timeout_returns_504(client):
    env_id = _create_env(client)
    respx.get("https://mock-morpheus.local/api/slow").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    resp = client.post(
        "/api/proxy/execute",
        json={"environment_id": env_id, "method": "GET", "path": "/api/slow"},
    )
    assert resp.status_code == 504


@respx.mock
def test_proxy_connect_error_returns_502(client):
    env_id = _create_env(client)
    respx.get("https://mock-morpheus.local/api/offline").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    resp = client.post(
        "/api/proxy/execute",
        json={"environment_id": env_id, "method": "GET", "path": "/api/offline"},
    )
    assert resp.status_code == 502


def test_proxy_unknown_env_returns_404(client):
    resp = client.post(
        "/api/proxy/execute",
        json={"environment_id": "doesnotexist", "method": "GET", "path": "/api/test"},
    )
    assert resp.status_code == 404
