import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_http_client, get_store
from app.models import LoadedSpec, SpecLoadRequest
from app.services.spec_service import SpecFetchError, SpecParseError, load_spec
from app.services.store import EnvironmentStore

router = APIRouter(prefix="/api/spec", tags=["spec"])


@router.post("/load", response_model=LoadedSpec)
async def load_spec_endpoint(
    body: SpecLoadRequest,
    store: EnvironmentStore = Depends(get_store),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    environment = None
    if body.environment_id:
        environment = await store.get(body.environment_id)
        if environment is None:
            raise HTTPException(status_code=404, detail="Environment not found")

    try:
        loaded = await load_spec(body.url, http_client, environment)
    except SpecFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except SpecParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    store.spec = loaded
    return loaded


@router.get("")
async def get_spec(store: EnvironmentStore = Depends(get_store)):
    if store.spec is None:
        return {"loaded": False}
    return store.spec


@router.delete("")
async def clear_spec(store: EnvironmentStore = Depends(get_store)):
    store.spec = None
    return {"cleared": True}
