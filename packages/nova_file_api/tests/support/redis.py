"""Shared in-memory Redis doubles for nova_file_api tests."""

from __future__ import annotations

import pytest


class MemoryRedisClient:
    """Deterministic in-memory Redis double for route-style tests.

    Attributes:
        _data: Backing key/value store used for deterministic test behavior.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory Redis-like store."""
        self._data: dict[str, str] = {}

    def replace_string(self, key: str, value: str) -> None:
        """Set ``key`` to ``value``, overwriting any prior entry.

        Used by tests that need to bypass ``SET``/``NX`` semantics of
        :meth:`set`.
        """
        self._data[key] = value

    async def get(self, key: str) -> str | None:
        """Return the value for a key.

        Args:
            key: Redis key to read.

        Returns:
            The stored string value, or ``None`` when the key is absent.
        """
        return self._data.get(key)

    async def set(
        self,
        *,
        name: str,
        value: str,
        ex: int,
        nx: bool = False,
    ) -> bool:
        """Store a value, optionally only when absent.

        Args:
            name: Redis key to write.
            value: String payload to store.
            ex: Expiration time in seconds (ignored by this test double).
            nx: Whether to write only when the key does not exist.

        Returns:
            ``True`` when the value is written, otherwise ``False``.
        """
        del ex
        if nx and name in self._data:
            return False
        self._data[name] = value
        return True

    async def delete(self, key: str) -> int:
        """Delete a key from the store.

        Args:
            key: Redis key to delete.

        Returns:
            ``1`` when a key is removed, otherwise ``0``.
        """
        return 1 if self._data.pop(key, None) is not None else 0

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        expected_value: str,
    ) -> int:
        """Simulate compare-and-delete script behavior.

        Args:
            script: Lua script body (ignored by this test double).
            numkeys: Number of keys provided (ignored by this test double).
            key: Redis key to compare and potentially delete.
            expected_value: Expected current value required for deletion.

        Returns:
            ``1`` when the key matches and is deleted, otherwise ``0``.
        """
        del script, numkeys
        if self._data.get(key) != expected_value:
            return 0
        return await self.delete(key)

    async def ping(self) -> bool:
        """Report health for the in-memory test backend.

        Returns:
            ``True`` because this in-memory backend is always available.
        """
        return True


@pytest.fixture
def memory_redis_client() -> MemoryRedisClient:
    """Provide a reusable in-memory Redis client fixture.

    Returns:
        A fresh ``MemoryRedisClient`` instance.
    """
    return MemoryRedisClient()
