# ruff: noqa
"""A client library for accessing nova-file-api"""

from .client import AuthenticatedClient, Client

__all__ = (
    "AuthenticatedClient",
    "Client",
)
