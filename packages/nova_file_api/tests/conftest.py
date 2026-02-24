from __future__ import annotations

import pytest

from ._test_doubles import StubAuthenticator, StubTransferService


@pytest.fixture
def stub_authenticator() -> StubAuthenticator:
    return StubAuthenticator()


@pytest.fixture
def stub_transfer_service() -> StubTransferService:
    return StubTransferService()
