import time
import urllib.parse
from typing import Any

import httpx

from app.models import Environment, ProxyRequest, ProxyResponse

# Headers that must not be forwarded (hop-by-hop)
HOP_BY_HOP = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    ]
)


class ProxyConnectionError(Exception):
    pass


class ProxyTimeoutError(Exception):
    pass


def _substitute_path_params(path: str, path_params: dict[str, str]) -> str:
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", urllib.parse.quote(str(value), safe=""))
    return path


def _build_headers(req: ProxyRequest, env: Environment) -> dict[str, str]:
    headers: dict[str, str] = {}
    auth = env.auth

    if auth.type == "bearer" and auth.token:
        headers["Authorization"] = f"{auth.bearer_prefix} {auth.token}"
    elif auth.type == "api_key" and auth.token:
        key_header = auth.header_name or "X-API-Key"
        headers[key_header] = auth.token

    # Merge caller-supplied headers (may override auth — caller's choice)
    for k, v in req.headers.items():
        if k.lower() not in HOP_BY_HOP:
            headers[k] = v

    return headers


def _normalize_response_body(resp: httpx.Response) -> Any:
    content_type = resp.headers.get("content-type", "")
    if "json" in content_type:
        try:
            return resp.json()
        except Exception:
            pass
    return resp.text


def _filter_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in HOP_BY_HOP
    }


async def execute_proxy(
    req: ProxyRequest,
    env: Environment,
    http_client: httpx.AsyncClient,
) -> ProxyResponse:
    path = _substitute_path_params(req.path, req.path_params)
    url = env.base_url.rstrip("/") + path
    headers = _build_headers(req, env)

    kwargs: dict[str, Any] = {
        "headers": headers,
        "params": req.query_params or None,
        "follow_redirects": True,
        "timeout": req.timeout,
    }

    if env.auth.type == "basic" and env.auth.username:
        kwargs["auth"] = (env.auth.username, env.auth.password or "")

    if req.body is not None:
        kwargs["json"] = req.body

    start = time.monotonic()
    try:
        # For verify_ssl=False environments, create a temporary client.
        # The shared http_client is used for verified connections.
        if not env.verify_ssl:
            async with httpx.AsyncClient(verify=False) as tmp_client:
                resp = await tmp_client.request(req.method.upper(), url, **kwargs)
        else:
            resp = await http_client.request(req.method.upper(), url, **kwargs)
    except httpx.TimeoutException as exc:
        raise ProxyTimeoutError(str(exc)) from exc
    except httpx.ConnectError as exc:
        raise ProxyConnectionError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise ProxyConnectionError(str(exc)) from exc

    duration_ms = (time.monotonic() - start) * 1000
    body = _normalize_response_body(resp)
    resp_headers = _filter_headers(resp.headers)

    return ProxyResponse(
        status_code=resp.status_code,
        headers=resp_headers,
        body=body,
        duration_ms=round(duration_ms, 2),
        url=str(resp.url),
    )
