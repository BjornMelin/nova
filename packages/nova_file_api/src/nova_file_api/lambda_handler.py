"""Native AWS Lambda entrypoint for the FastAPI runtime."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI
from mangum import Mangum

from nova_file_api.app import create_app


def create_lambda_handler(
    *,
    app: FastAPI | None = None,
    lifespan: Literal["auto", "on", "off"] = "on",
) -> Mangum:
    """Build the native Lambda adapter for a FastAPI ASGI application.

    Args:
        app: Optional FastAPI application instance. When omitted, builds the
            canonical application with `create_app()`.
        lifespan: ASGI lifespan mode passed to Mangum.

    Returns:
        Configured Mangum adapter for the resolved FastAPI application.
    """
    resolved_app = create_app() if app is None else app
    return Mangum(resolved_app, lifespan=lifespan)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle one AWS Lambda proxy event with the canonical FastAPI adapter.

    Args:
        event: Lambda proxy event payload from API Gateway.
        context: AWS Lambda invocation context object.

    Returns:
        API Gateway-compatible response payload emitted by Mangum.
    """
    return create_lambda_handler()(event, context)
