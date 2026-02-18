import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_http_client, get_store
from app.models import ProxyRequest, ProxyResponse
from app.services.proxy_service import (
    ProxyConnectionError,
    ProxyTimeoutError,
    execute_proxy,
)
from app.services.store import EnvironmentStore

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


@router.post("/execute", response_model=ProxyResponse)
async def proxy_execute(
    body: ProxyRequest,
    store: EnvironmentStore = Depends(get_store),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    env = await store.get(body.environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    try:
        result = await execute_proxy(body, env, http_client)
    except ProxyTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"Upstream timeout: {exc}")
    except ProxyConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream unreachable: {exc}")

    return result
