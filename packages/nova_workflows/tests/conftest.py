from __future__ import annotations

import pytest
from botocore.config import Config


class _AsyncContextValue:
    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> bool:
        del exc_type, exc, tb
        return False


class RecordingSession:
    def __init__(self) -> None:
        self.client_calls: list[tuple[str, Config | None]] = []
        self.resource_calls: list[tuple[str, Config | None]] = []

    def client(
        self, service_name: str, *, config: Config | None = None
    ) -> _AsyncContextValue:
        self.client_calls.append((service_name, config))
        return _AsyncContextValue(object())

    def resource(
        self, service_name: str, *, config: Config | None = None
    ) -> _AsyncContextValue:
        self.resource_calls.append((service_name, config))
        return _AsyncContextValue(object())


@pytest.fixture
def recording_session() -> RecordingSession:
    return RecordingSession()
