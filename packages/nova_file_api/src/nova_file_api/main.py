"""ASGI entrypoint."""

from nova_file_api.app import create_app

app = create_app()
