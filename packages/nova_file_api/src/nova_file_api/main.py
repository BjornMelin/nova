"""ASGI entrypoint for local development and tooling."""

from nova_file_api.app import create_app

app = create_app()

__all__ = ["app"]
