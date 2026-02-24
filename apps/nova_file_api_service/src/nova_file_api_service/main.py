"""ASGI entrypoint for nova-file-api service."""

from nova_file_api.app import create_app

app = create_app()
