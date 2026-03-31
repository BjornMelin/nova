# mypy: disable-error-code=import-not-found

"""Reserved-concurrency policy helpers for the Nova runtime stack."""

from __future__ import annotations

from typing import Final

PRODUCTION_ENVIRONMENTS: Final[frozenset[str]] = frozenset(
    {"prod", "production"}
)
STANDARD_LAMBDA_ACCOUNT_CONCURRENCY: Final[int] = 1000


def is_production_environment(deployment_environment: str) -> bool:
    """Return whether one deployment environment is production.

    Args:
        deployment_environment: Environment name supplied to the runtime
            stack or deployment workflow.

    Returns:
        True when the normalized environment name maps to a production
        environment; otherwise False.
    """
    return deployment_environment.strip().casefold() in PRODUCTION_ENVIRONMENTS


def default_api_reserved_concurrency(deployment_environment: str) -> int:
    """Return the canonical API reserved-concurrency default.

    Args:
        deployment_environment: Environment name supplied to the runtime
            stack or deployment workflow.

    Returns:
        The default reserved concurrency for the public API Lambda.
    """
    if is_production_environment(deployment_environment):
        return 25
    return 5


def default_workflow_reserved_concurrency(deployment_environment: str) -> int:
    """Return the canonical workflow-task reserved-concurrency default.

    Args:
        deployment_environment: Environment name supplied to the runtime
            stack or deployment workflow.

    Returns:
        The default reserved concurrency for each workflow task Lambda.
    """
    if is_production_environment(deployment_environment):
        return 10
    return 2


def low_quota_account_disables_reserved_concurrency(
    account_concurrency_limit: int,
) -> bool:
    """Return whether one account should fall back to no reservations.

    Args:
        account_concurrency_limit: Regional Lambda concurrency quota for the
            target AWS account.

    Returns:
        True when the account quota is below Nova's standard concurrency
        baseline and reserved concurrency should stay disabled.
    """
    return account_concurrency_limit < STANDARD_LAMBDA_ACCOUNT_CONCURRENCY
