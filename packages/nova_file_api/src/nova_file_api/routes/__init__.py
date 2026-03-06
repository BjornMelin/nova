"""Canonical runtime routers grouped by domain."""

from __future__ import annotations

from fastapi import APIRouter

from nova_file_api.routes.jobs import jobs_router
from nova_file_api.routes.platform import ops_router, platform_router
from nova_file_api.routes.transfers import transfer_router

v1_router = APIRouter()
v1_router.include_router(jobs_router)
v1_router.include_router(platform_router)

__all__ = ["ops_router", "transfer_router", "v1_router"]
