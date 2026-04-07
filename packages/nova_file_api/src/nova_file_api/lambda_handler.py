"""Native AWS Lambda entrypoint for the FastAPI runtime."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from mangum import Mangum

from nova_file_api.app import create_app
from nova_file_api.config import Settings
from nova_file_api.runtime import RuntimeBootstrap, bootstrap_api_runtime

_DEFAULT_BOOTSTRAP_LOOP: asyncio.AbstractEventLoop | None = None
_DEFAULT_RUNTIME_BOOTSTRAP: RuntimeBootstrap | None = None
_DEFAULT_HANDLER: Mangum | None = None


def _get_bootstrap_loop() -> asyncio.AbstractEventLoop:
    """Return the dedicated event loop used for Lambda runtime bootstrap."""
    global _DEFAULT_BOOTSTRAP_LOOP
    if _DEFAULT_BOOTSTRAP_LOOP is None or _DEFAULT_BOOTSTRAP_LOOP.is_closed():
        _DEFAULT_BOOTSTRAP_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(_DEFAULT_BOOTSTRAP_LOOP)
    return _DEFAULT_BOOTSTRAP_LOOP


def _get_default_runtime_bootstrap() -> RuntimeBootstrap:
    """Return the cached process-wide runtime bootstrap for Lambda."""
    global _DEFAULT_RUNTIME_BOOTSTRAP
    if _DEFAULT_RUNTIME_BOOTSTRAP is None:
        loop = _get_bootstrap_loop()
        _DEFAULT_RUNTIME_BOOTSTRAP = loop.run_until_complete(
            bootstrap_api_runtime(settings=Settings())
        )
    return _DEFAULT_RUNTIME_BOOTSTRAP


def _build_default_app() -> FastAPI:
    """Build the canonical FastAPI app bound to the cached Lambda runtime."""
    return create_app(runtime=_get_default_runtime_bootstrap().runtime)


def create_lambda_handler() -> Mangum:
    """Build the canonical native Lambda adapter for the FastAPI runtime."""
    return Mangum(_build_default_app(), lifespan="off")


def _get_default_handler() -> Mangum:
    """Return the cached canonical Lambda handler."""
    global _DEFAULT_HANDLER
    if _DEFAULT_HANDLER is None:
        _DEFAULT_HANDLER = create_lambda_handler()
    return _DEFAULT_HANDLER


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle one AWS Lambda proxy event with the canonical FastAPI adapter."""
    return _get_default_handler()(event, context)
