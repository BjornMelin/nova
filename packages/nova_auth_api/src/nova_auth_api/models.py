"""Pydantic models for nova-auth-api endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Strict base model with forbidden extra fields."""

    model_config = ConfigDict(extra="forbid")


def normalize_str_sequence(value: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize and deduplicate a tuple of strings preserving order."""
    output: list[str] = []
    for entry in value:
        normalized = entry.strip()
        if normalized:
            output.append(normalized)
    return tuple(dict.fromkeys(output))


class Principal(StrictModel):
    """Authorized caller identity resolved from token claims."""

    subject: str
    scope_id: str
    tenant_id: str | None = None
    scopes: tuple[str, ...] = Field(default=(), max_length=256)
    permissions: tuple[str, ...] = Field(default=(), max_length=256)


class TokenVerifyRequest(StrictModel):
    """Request payload for access token verification."""

    access_token: str = Field(min_length=1)
    required_scopes: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()

    @field_validator("required_scopes", "required_permissions")
    @classmethod
    def _normalize_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_str_sequence(value)


class TokenVerifyResponse(StrictModel):
    """Response payload for token verification."""

    principal: Principal
    claims: dict[str, Any]


class TokenIntrospectRequest(StrictModel):
    """Request payload for token introspection."""

    access_token: str = Field(min_length=1)
    required_scopes: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()

    @field_validator("required_scopes", "required_permissions")
    @classmethod
    def _normalize_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_str_sequence(value)


class TokenIntrospectResponse(StrictModel):
    """Response payload for token introspection."""

    active: bool
    principal: Principal | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(StrictModel):
    """Health check response payload."""

    status: Literal["ok"]
    service: Literal["nova-auth-api"]
    request_id: str


class ErrorBody(StrictModel):
    """Canonical error payload body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorEnvelope(StrictModel):
    """Canonical error envelope."""

    error: ErrorBody
