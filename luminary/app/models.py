import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class AuthConfig(BaseModel):
    type: Literal["none", "bearer", "api_key", "basic"] = "none"
    token: str | None = None
    header_name: str | None = None
    bearer_prefix: str = "Bearer"
    username: str | None = None
    password: str | None = None


class AuthConfigPublic(BaseModel):
    type: str
    header_name: str | None
    bearer_prefix: str
    username: str | None
    has_token: bool
    has_password: bool


# ─── Environment ─────────────────────────────────────────────────────────────

class Environment(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    base_url: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    verify_ssl: bool = True
    created_at: datetime
    updated_at: datetime


class EnvironmentCreate(BaseModel):
    name: str
    base_url: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    verify_ssl: bool = True


class EnvironmentUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    auth: AuthConfig | None = None
    verify_ssl: bool | None = None


class EnvironmentPublic(BaseModel):
    id: str
    name: str
    base_url: str
    verify_ssl: bool
    created_at: datetime
    updated_at: datetime
    auth: AuthConfigPublic

    @classmethod
    def from_env(cls, env: Environment) -> "EnvironmentPublic":
        return cls(
            id=env.id,
            name=env.name,
            base_url=env.base_url,
            verify_ssl=env.verify_ssl,
            created_at=env.created_at,
            updated_at=env.updated_at,
            auth=AuthConfigPublic(
                type=env.auth.type,
                header_name=env.auth.header_name,
                bearer_prefix=env.auth.bearer_prefix,
                username=env.auth.username,
                has_token=env.auth.token is not None,
                has_password=env.auth.password is not None,
            ),
        )


# ─── Spec ────────────────────────────────────────────────────────────────────

class ParameterInfo(BaseModel):
    name: str
    location: str
    required: bool = False
    description: str | None = None
    schema_: dict = Field(alias="schema", default_factory=dict)

    model_config = {"populate_by_name": True}


class EndpointSummary(BaseModel):
    method: str
    path: str
    operation_id: str | None = None
    summary: str | None = None
    description: str | None = None
    tags: list[str] = []
    parameters: list[ParameterInfo] = []
    has_request_body: bool = False
    request_body_schema: dict | None = None
    request_body_required: bool = False


class LoadedSpec(BaseModel):
    title: str
    version: str
    description: str | None = None
    base_url: str | None = None
    endpoints: list[EndpointSummary]
    raw: dict
    source_url: str
    loaded_at: str


class SpecLoadRequest(BaseModel):
    url: str
    environment_id: str | None = None


# ─── Proxy ───────────────────────────────────────────────────────────────────

class ProxyRequest(BaseModel):
    environment_id: str
    method: str
    path: str
    path_params: dict[str, str] = {}
    query_params: dict[str, str] = {}
    headers: dict[str, str] = {}
    body: Any | None = None
    timeout: float = 30.0


class ProxyResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: Any
    duration_ms: float
    url: str
    error: str | None = None
