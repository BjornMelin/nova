"""Pytest fixtures for nova_file_api tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def aws_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Set inert AWS env vars so app lifespan can build local clients.

    Applied automatically to all tests in this package.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
