"""ASGI entrypoint for local development and tooling."""

from nova_file_api.app import create_managed_app

app = create_managed_app()

__all__ = ["app"]
