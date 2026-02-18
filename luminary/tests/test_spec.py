
import respx
import httpx

SIMPLE_JSON_SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "tags": ["pets"],
                "parameters": [
                    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "tags": ["pets"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": {"name": {"type": "string"}}}
                        }
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
        }
    },
}

SIMPLE_YAML_SPEC = """\
openapi: "3.0.0"
info:
  title: YAML API
  version: "2.0"
servers:
  - url: https://yaml.example.com
paths:
  /items:
    get:
      operationId: listItems
      summary: List items
      tags: [items]
      responses:
        "200":
          description: OK
"""


@respx.mock
def test_load_json_spec(client):
    respx.get("https://spec.example.com/openapi.json").mock(
        return_value=httpx.Response(200, json=SIMPLE_JSON_SPEC)
    )
    resp = client.post("/api/spec/load", json={"url": "https://spec.example.com/openapi.json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test API"
    assert data["version"] == "1.0.0"
    assert data["base_url"] == "https://api.example.com"
    assert len(data["endpoints"]) == 2
    methods = {e["method"] for e in data["endpoints"]}
    assert methods == {"GET", "POST"}


@respx.mock
def test_load_yaml_spec(client):
    respx.get("https://spec.example.com/openapi.yaml").mock(
        return_value=httpx.Response(200, text=SIMPLE_YAML_SPEC, headers={"content-type": "application/yaml"})
    )
    resp = client.post("/api/spec/load", json={"url": "https://spec.example.com/openapi.yaml"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "YAML API"
    assert data["base_url"] == "https://yaml.example.com"
    assert len(data["endpoints"]) == 1


@respx.mock
def test_load_spec_unreachable_returns_502(client):
    respx.get("https://unreachable.example.com/spec.yaml").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    resp = client.post("/api/spec/load", json={"url": "https://unreachable.example.com/spec.yaml"})
    assert resp.status_code == 502


@respx.mock
def test_load_spec_invalid_returns_422(client):
    respx.get("https://spec.example.com/bad.json").mock(
        return_value=httpx.Response(200, json={"not": "a spec"})
    )
    resp = client.post("/api/spec/load", json={"url": "https://spec.example.com/bad.json"})
    assert resp.status_code == 422


def test_get_spec_not_loaded(client):
    resp = client.get("/api/spec")
    assert resp.status_code == 200
    assert resp.json() == {"loaded": False}


@respx.mock
def test_get_spec_after_load(client):
    respx.get("https://spec.example.com/openapi.json").mock(
        return_value=httpx.Response(200, json=SIMPLE_JSON_SPEC)
    )
    client.post("/api/spec/load", json={"url": "https://spec.example.com/openapi.json"})
    resp = client.get("/api/spec")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test API"


@respx.mock
def test_clear_spec(client):
    respx.get("https://spec.example.com/openapi.json").mock(
        return_value=httpx.Response(200, json=SIMPLE_JSON_SPEC)
    )
    client.post("/api/spec/load", json={"url": "https://spec.example.com/openapi.json"})
    resp = client.delete("/api/spec")
    assert resp.status_code == 200
    assert resp.json() == {"cleared": True}
    # Should be unloaded
    resp2 = client.get("/api/spec")
    assert resp2.json() == {"loaded": False}
