from __future__ import annotations

from nova_file_api.models import Principal
from starlette.requests import Request


class StubAuthenticator:
    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        del request, session_id
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )

    async def healthcheck(self) -> bool:
        """Return healthy status for tests using this stub authenticator.

        Returns:
            ``True`` to indicate the test double is always healthy.
        """
        return True


class StubTransferService:
    pass
