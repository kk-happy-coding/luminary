from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_store
from app.models import EnvironmentCreate, EnvironmentPublic, EnvironmentUpdate
from app.services.store import EnvironmentStore

router = APIRouter(prefix="/api/environments", tags=["environments"])


@router.get("", response_model=list[EnvironmentPublic])
async def list_environments(store: EnvironmentStore = Depends(get_store)):
    envs = await store.get_all()
    return [EnvironmentPublic.from_env(e) for e in envs]


@router.post("", response_model=EnvironmentPublic, status_code=201)
async def create_environment(
    body: EnvironmentCreate,
    store: EnvironmentStore = Depends(get_store),
):
    env = await store.create(body)
    return EnvironmentPublic.from_env(env)


@router.get("/{env_id}", response_model=EnvironmentPublic)
async def get_environment(
    env_id: str,
    store: EnvironmentStore = Depends(get_store),
):
    env = await store.get(env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return EnvironmentPublic.from_env(env)


@router.put("/{env_id}", response_model=EnvironmentPublic)
async def update_environment(
    env_id: str,
    body: EnvironmentUpdate,
    store: EnvironmentStore = Depends(get_store),
):
    env = await store.update(env_id, body)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return EnvironmentPublic.from_env(env)


@router.delete("/{env_id}")
async def delete_environment(
    env_id: str,
    store: EnvironmentStore = Depends(get_store),
):
    deleted = await store.delete(env_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Environment not found")
    return {"deleted": True}
