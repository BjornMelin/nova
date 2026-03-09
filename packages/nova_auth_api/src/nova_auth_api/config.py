"""Settings models for nova-auth-api."""

from __future__ import annotations

import importlib.metadata

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_app_version() -> str:
    """Return installed package version with resilient fallback."""
    try:
        return importlib.metadata.version("nova-auth-api")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="nova-auth-api", alias="APP_NAME")
    app_version: str = Field(
        default_factory=_default_app_version,
        alias="APP_VERSION",
    )
    environment: str = Field(default="dev", alias="ENVIRONMENT")

    oidc_issuer: str | None = Field(default=None, alias="OIDC_ISSUER")
    oidc_audience: str | None = Field(default=None, alias="OIDC_AUDIENCE")
    oidc_jwks_url: str | None = Field(default=None, alias="OIDC_JWKS_URL")
    oidc_required_scopes: str = Field(default="", alias="OIDC_REQUIRED_SCOPES")
    oidc_required_permissions: str = Field(
        default="",
        alias="OIDC_REQUIRED_PERMISSIONS",
    )
    oidc_clock_skew_seconds: int = Field(
        default=0,
        alias="OIDC_CLOCK_SKEW_SECONDS",
        ge=0,
        le=120,
    )
    oidc_verifier_thread_tokens: int = Field(
        default=40,
        alias="OIDC_VERIFIER_THREAD_TOKENS",
        ge=1,
        le=1000,
    )
    @property
    def default_required_scopes(self) -> tuple[str, ...]:
        """Return configured default required scopes."""
        if not self.oidc_required_scopes.strip():
            return ()
        return tuple(v for v in self.oidc_required_scopes.split(" ") if v)

    @property
    def default_required_permissions(self) -> tuple[str, ...]:
        """Return configured default required permissions."""
        if not self.oidc_required_permissions.strip():
            return ()
        return tuple(
            value
            for value in self.oidc_required_permissions.split(" ")
            if value
        )
