import json
from datetime import datetime, timezone

import httpx
import yaml

from app.models import (
    EndpointSummary,
    Environment,
    LoadedSpec,
    ParameterInfo,
)


def _resolve_ref(ref: str, spec: dict) -> dict:
    """Resolve a simple $ref like '#/components/schemas/Foo' one level deep."""
    if not ref.startswith("#/"):
        return {}
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _resolve_schema(schema: dict, spec: dict) -> dict:
    if "$ref" in schema:
        return _resolve_ref(schema["$ref"], spec)
    return schema


def _extract_parameters(operation: dict, path_item: dict, spec: dict) -> list[ParameterInfo]:
    raw_params: list[dict] = list(path_item.get("parameters", []))
    raw_params.extend(operation.get("parameters", []))
    params = []
    for p in raw_params:
        if "$ref" in p:
            p = _resolve_ref(p["$ref"], spec)
        if not p:
            continue
        schema = _resolve_schema(p.get("schema", {}), spec)
        params.append(
            ParameterInfo(
                name=p.get("name", ""),
                location=p.get("in", "query"),
                required=p.get("required", False),
                description=p.get("description"),
                schema=schema,
            )
        )
    return params


def _extract_request_body(
    operation: dict, spec: dict
) -> tuple[bool, dict | None, bool]:
    rb = operation.get("requestBody")
    if rb is None:
        return False, None, False
    if "$ref" in rb:
        rb = _resolve_ref(rb["$ref"], spec)
    required = rb.get("required", False)
    content = rb.get("content", {})
    for media_type in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data"):
        if media_type in content:
            schema = content[media_type].get("schema", {})
            schema = _resolve_schema(schema, spec)
            return True, schema, required
    return True, None, required


def _flatten_endpoints(spec: dict) -> list[EndpointSummary]:
    paths = spec.get("paths", {})
    endpoints = []
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in http_methods:
                continue
            if not isinstance(operation, dict):
                continue

            parameters = _extract_parameters(operation, path_item, spec)
            has_body, body_schema, body_required = _extract_request_body(operation, spec)

            endpoints.append(
                EndpointSummary(
                    method=method.upper(),
                    path=path,
                    operation_id=operation.get("operationId"),
                    summary=operation.get("summary"),
                    description=operation.get("description"),
                    tags=operation.get("tags", []),
                    parameters=parameters,
                    has_request_body=has_body,
                    request_body_schema=body_schema,
                    request_body_required=body_required,
                )
            )
    return endpoints


async def load_spec(
    url: str,
    http_client: httpx.AsyncClient,
    environment: Environment | None = None,
) -> LoadedSpec:
    headers: dict[str, str] = {}

    if environment is not None:
        auth = environment.auth
        if auth.type == "bearer" and auth.token:
            headers["Authorization"] = f"{auth.bearer_prefix} {auth.token}"
        elif auth.type == "api_key" and auth.token:
            key_header = auth.header_name or "X-API-Key"
            headers[key_header] = auth.token

    try:
        resp = await http_client.get(
            url,
            headers=headers,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpecFetchError(f"Timeout fetching spec from {url}") from exc
    except httpx.HTTPError as exc:
        raise SpecFetchError(f"Failed to fetch spec from {url}: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    raw_text = resp.text

    # Detect YAML vs JSON
    is_yaml = (
        "yaml" in content_type
        or url.endswith(".yaml")
        or url.endswith(".yml")
    )

    try:
        if is_yaml:
            spec = yaml.safe_load(raw_text)
        else:
            try:
                spec = json.loads(raw_text)
            except json.JSONDecodeError:
                spec = yaml.safe_load(raw_text)
    except Exception as exc:
        raise SpecParseError(f"Failed to parse spec: {exc}") from exc

    if not isinstance(spec, dict):
        raise SpecParseError("Parsed spec is not a mapping")

    if "openapi" not in spec and "swagger" not in spec:
        raise SpecParseError("Not a valid OpenAPI/Swagger spec (missing 'openapi' or 'swagger' key)")

    info = spec.get("info", {})
    title = info.get("title", "Untitled")
    version = info.get("version", "unknown")
    description = info.get("description")

    # Extract base URL
    base_url: str | None = None
    if "servers" in spec and spec["servers"]:
        base_url = spec["servers"][0].get("url")
    elif "host" in spec:
        scheme = spec.get("schemes", ["https"])[0]
        base_path = spec.get("basePath", "")
        base_url = f"{scheme}://{spec['host']}{base_path}"

    endpoints = _flatten_endpoints(spec)

    return LoadedSpec(
        title=title,
        version=str(version),
        description=description,
        base_url=base_url,
        endpoints=endpoints,
        raw=spec,
        source_url=url,
        loaded_at=datetime.now(timezone.utc).isoformat(),
    )


class SpecFetchError(Exception):
    pass


class SpecParseError(Exception):
    pass
