import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
import yaml

from app.models import (
    EndpointSummary,
    Environment,
    LoadedSpec,
    ParameterInfo,
)

HTTP_METHODS = frozenset(
    ["get", "post", "put", "patch", "delete", "head", "options", "trace"]
)


# ─── External $ref fetching ───────────────────────────────────────────────────

async def _fetch_external(
    url: str,
    http_client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    cache: dict[str, dict],
) -> dict:
    if url in cache:
        return cache[url]
    async with sem:
        try:
            resp = await http_client.get(url, follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
        except Exception:
            cache[url] = {}
            return {}
        is_yaml = (
            "yaml" in resp.headers.get("content-type", "")
            or url.endswith(".yaml")
            or url.endswith(".yml")
        )
        try:
            parsed = yaml.safe_load(resp.text) if is_yaml else json.loads(resp.text)
            result = parsed if isinstance(parsed, dict) else {}
        except Exception:
            result = {}
        cache[url] = result
        return result


async def _resolve_external_path_items(
    spec: dict,
    spec_url: str,
    http_client: httpx.AsyncClient,
) -> None:
    """
    Fetch external path-item $refs concurrently, then inline their parameter $refs.
    Mutates spec["paths"] in-place.
    """
    paths = spec.get("paths", {})
    cache: dict[str, dict] = {}
    sem = asyncio.Semaphore(30)

    # Base dir of the spec file (for resolving relative refs)
    spec_base = spec_url.rsplit("/", 1)[0] + "/"

    # Phase 1: collect external path-item refs
    external: dict[str, str] = {}  # path → absolute URL
    for path, path_item in paths.items():
        if (
            isinstance(path_item, dict)
            and list(path_item.keys()) == ["$ref"]
            and not path_item["$ref"].startswith("#")
        ):
            external[path] = urljoin(spec_base, path_item["$ref"])

    if not external:
        return

    # Phase 2: fetch all path-item files concurrently
    items: dict[str, tuple[dict, str]] = {}  # path → (doc, file_url)

    async def _fetch_path_item(path: str, url: str) -> None:
        doc = await _fetch_external(url, http_client, sem, cache)
        items[path] = (doc, url)

    await asyncio.gather(*[_fetch_path_item(p, u) for p, u in external.items()])

    # Phase 3: collect all parameter $refs (relative to their path-item file)
    param_urls: set[str] = set()
    for _path, (doc, file_url) in items.items():
        if not doc:
            continue
        file_base = file_url.rsplit("/", 1)[0] + "/"
        for method in HTTP_METHODS:
            op = doc.get(method)
            if not isinstance(op, dict):
                continue
            for param in op.get("parameters", []):
                if isinstance(param, dict) and "$ref" in param:
                    ref = param["$ref"]
                    if not ref.startswith("#"):
                        param_urls.add(urljoin(file_base, ref))

    # Phase 4: fetch all parameter files concurrently
    if param_urls:
        await asyncio.gather(
            *[_fetch_external(u, http_client, sem, cache) for u in param_urls]
        )

    # Phase 5: inline path items, resolving their parameter refs
    for path, (doc, file_url) in items.items():
        if not doc:
            continue
        file_base = file_url.rsplit("/", 1)[0] + "/"
        for method in HTTP_METHODS:
            op = doc.get(method)
            if not isinstance(op, dict):
                continue
            inlined_params = []
            for param in op.get("parameters", []):
                if isinstance(param, dict) and "$ref" in param:
                    ref = param["$ref"]
                    if not ref.startswith("#"):
                        resolved = cache.get(urljoin(file_base, ref), param)
                        inlined_params.append(resolved)
                    else:
                        inlined_params.append(param)
                else:
                    inlined_params.append(param)
            op["parameters"] = inlined_params
        paths[path] = doc


# ─── Internal $ref resolution (single-document) ──────────────────────────────

def _resolve_internal_ref(ref: str, spec: dict) -> dict:
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
        return _resolve_internal_ref(schema["$ref"], spec)
    return schema


# ─── Endpoint flattening ─────────────────────────────────────────────────────

def _extract_parameters(
    operation: dict, path_item: dict, spec: dict
) -> list[ParameterInfo]:
    raw: list[dict] = list(path_item.get("parameters", []))
    raw.extend(operation.get("parameters", []))
    params = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        if "$ref" in p:
            p = _resolve_internal_ref(p["$ref"], spec)
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
        rb = _resolve_internal_ref(rb["$ref"], spec)
    required = rb.get("required", False)
    content = rb.get("content", {})
    for media_type in (
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ):
        if media_type in content:
            schema = _resolve_schema(
                content[media_type].get("schema", {}), spec
            )
            return True, schema, required
    return True, None, required


def _flatten_endpoints(spec: dict) -> list[EndpointSummary]:
    paths = spec.get("paths", {})
    endpoints = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            parameters = _extract_parameters(operation, path_item, spec)
            has_body, body_schema, body_required = _extract_request_body(
                operation, spec
            )
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


# ─── Public entry point ───────────────────────────────────────────────────────

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
            headers[auth.header_name or "X-API-Key"] = auth.token

    try:
        resp = await http_client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpecFetchError(f"Timeout fetching spec from {url}") from exc
    except httpx.HTTPError as exc:
        raise SpecFetchError(f"Failed to fetch spec from {url}: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    is_yaml = (
        "yaml" in content_type
        or url.endswith(".yaml")
        or url.endswith(".yml")
    )
    try:
        spec = yaml.safe_load(resp.text) if is_yaml else json.loads(resp.text)
        if not isinstance(spec, dict):
            try:
                spec = yaml.safe_load(resp.text)
            except Exception:
                pass
    except Exception as exc:
        raise SpecParseError(f"Failed to parse spec: {exc}") from exc

    if not isinstance(spec, dict):
        raise SpecParseError("Parsed spec is not a mapping")
    if "openapi" not in spec and "swagger" not in spec:
        raise SpecParseError(
            "Not a valid OpenAPI/Swagger spec (missing 'openapi' or 'swagger' key)"
        )

    # Resolve external path-item $refs (e.g. Morpheus modular spec)
    await _resolve_external_path_items(spec, url, http_client)

    info = spec.get("info", {})
    title = info.get("title", "Untitled")
    version = info.get("version", "unknown")
    description = info.get("description")

    base_url: str | None = None
    if "servers" in spec and spec["servers"]:
        base_url = spec["servers"][0].get("url")
    elif "host" in spec:
        scheme = spec.get("schemes", ["https"])[0]
        base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}"

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
