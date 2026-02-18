import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.config as _config
from app.routers import environments, proxy, spec
from app.services.store import EnvironmentStore

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = EnvironmentStore(_config.DATA_DIR / "environments.json")
    await app.state.store.load()
    app.state.http_client = httpx.AsyncClient(timeout=60.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="Luminary", version="0.2.0", lifespan=lifespan)

app.include_router(environments.router)
app.include_router(spec.router)
app.include_router(proxy.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    return {"message": "Hello World", "version": "0.2.0"}
