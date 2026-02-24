"""ASGI entrypoint for nova-auth-api."""

from nova_auth_api.app import create_app

app = create_app()
