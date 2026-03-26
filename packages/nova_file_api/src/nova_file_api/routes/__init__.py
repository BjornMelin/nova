"""Canonical runtime routers grouped by domain."""

from nova_file_api.routes.exports import exports_router
from nova_file_api.routes.platform import ops_router, platform_router
from nova_file_api.routes.transfers import transfer_router

__all__ = [
    "exports_router",
    "ops_router",
    "platform_router",
    "transfer_router",
]
