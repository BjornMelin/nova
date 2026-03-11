"""Canonical runtime routers grouped by domain."""

from nova_file_api.routes.jobs import jobs_router
from nova_file_api.routes.platform import ops_router, platform_router
from nova_file_api.routes.transfers import transfer_router

__all__ = [
    "jobs_router",
    "ops_router",
    "platform_router",
    "transfer_router",
]
