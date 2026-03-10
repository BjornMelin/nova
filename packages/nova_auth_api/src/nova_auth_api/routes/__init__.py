"""Route modules for nova-auth-api."""

from nova_auth_api.routes.health import router as health_router
from nova_auth_api.routes.token import router as token_router

__all__ = ["health_router", "token_router"]
