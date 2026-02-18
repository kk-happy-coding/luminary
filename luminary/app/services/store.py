import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.models import Environment, EnvironmentCreate, EnvironmentUpdate, LoadedSpec


class EnvironmentStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, Environment] = {}
        self._lock = asyncio.Lock()
        self.spec: LoadedSpec | None = None

    async def load(self) -> None:
        if self._path.exists():
            try:
                text = self._path.read_text()
                raw = json.loads(text)
                for item in raw:
                    env = Environment.model_validate(item)
                    self._data[env.id] = env
            except Exception:
                pass

    async def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        payload = [e.model_dump(mode="json") for e in self._data.values()]
        tmp.write_text(json.dumps(payload, default=str))
        os.replace(tmp, self._path)

    async def get_all(self) -> list[Environment]:
        async with self._lock:
            return list(self._data.values())

    async def get(self, env_id: str) -> Environment | None:
        async with self._lock:
            return self._data.get(env_id)

    async def create(self, data: EnvironmentCreate) -> Environment:
        now = datetime.now(timezone.utc)
        env = Environment(
            name=data.name,
            base_url=data.base_url,
            auth=data.auth,
            verify_ssl=data.verify_ssl,
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._data[env.id] = env
            await self._persist()
        return env

    async def update(self, env_id: str, data: EnvironmentUpdate) -> Environment | None:
        async with self._lock:
            env = self._data.get(env_id)
            if env is None:
                return None
            update_data = data.model_dump(exclude_none=True)
            updated = env.model_copy(
                update={**update_data, "updated_at": datetime.now(timezone.utc)}
            )
            self._data[env_id] = updated
            await self._persist()
            return updated

    async def delete(self, env_id: str) -> bool:
        async with self._lock:
            if env_id not in self._data:
                return False
            del self._data[env_id]
            await self._persist()
            return True
