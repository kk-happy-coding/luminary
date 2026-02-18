import httpx
from fastapi import Request

from app.services.store import EnvironmentStore


def get_store(request: Request) -> EnvironmentStore:
    return request.app.state.store


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client
