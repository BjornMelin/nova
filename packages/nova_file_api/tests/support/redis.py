"""Shared in-memory Redis doubles for nova_file_api tests."""

from __future__ import annotations

import pytest


class MemoryRedisClient:
    """Deterministic in-memory Redis double for route-style tests."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(
        self,
        *,
        name: str,
        value: str,
        ex: int,
        nx: bool = False,
    ) -> bool:
        del ex
        if nx and name in self._data:
            return False
        self._data[name] = value
        return True

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        expected_value: str,
    ) -> int:
        del script, numkeys
        if self._data.get(key) != expected_value:
            return 0
        return await self.delete(key)

    async def ping(self) -> bool:
        return True


@pytest.fixture
def memory_redis_client() -> MemoryRedisClient:
    """Provide a reusable in-memory Redis client for tests."""
    return MemoryRedisClient()
