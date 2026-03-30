"""Native AWS Lambda entrypoint for the FastAPI runtime."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal, cast

from fastapi import FastAPI
from mangum import Mangum

from nova_file_api.app import create_app


def create_lambda_handler(
    *,
    app: FastAPI | None = None,
    lifespan: Literal["auto", "on", "off"] = "on",
) -> Any:
    """Build the native Lambda adapter for a FastAPI ASGI application."""
    resolved_app = create_app() if app is None else app
    return Mangum(resolved_app, lifespan=lifespan)


@lru_cache
def _cached_handler() -> Any:
    """Cache the Lambda adapter for execution-environment reuse."""
    return create_lambda_handler()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle one AWS Lambda proxy event with the cached FastAPI adapter."""
    return cast(dict[str, Any], _cached_handler()(event, context))
