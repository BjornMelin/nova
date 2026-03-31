# mypy: disable-error-code=import-not-found

"""Reserved-concurrency policy helpers for the Nova runtime stack."""

from __future__ import annotations

from typing import Final

PRODUCTION_ENVIRONMENTS: Final[frozenset[str]] = frozenset(
    {"prod", "production"}
)
STANDARD_LAMBDA_ACCOUNT_CONCURRENCY: Final[int] = 1000


def is_production_environment(deployment_environment: str) -> bool:
    """Return whether one deployment environment is production."""
    return deployment_environment in PRODUCTION_ENVIRONMENTS


def default_api_reserved_concurrency(deployment_environment: str) -> int:
    """Return the canonical API reserved-concurrency default."""
    if is_production_environment(deployment_environment):
        return 25
    return 5


def default_workflow_reserved_concurrency(deployment_environment: str) -> int:
    """Return the canonical workflow-task reserved-concurrency default."""
    if is_production_environment(deployment_environment):
        return 10
    return 2


def low_quota_account_disables_reserved_concurrency(
    account_concurrency_limit: int,
) -> bool:
    """Return whether one account should fall back to no reservations."""
    return account_concurrency_limit < STANDARD_LAMBDA_ACCOUNT_CONCURRENCY
