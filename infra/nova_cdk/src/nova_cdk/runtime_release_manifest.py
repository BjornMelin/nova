"""Shared runtime and release authority for Nova Lambda surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from nova_runtime_support.transfer_limits import (
    DEFAULT_ACTIVE_MULTIPART_UPLOAD_LIMIT,
    DEFAULT_DAILY_INGRESS_BUDGET_BYTES,
    DEFAULT_POLICY_ID,
    DEFAULT_POLICY_VERSION,
    DEFAULT_SIGN_REQUESTS_PER_UPLOAD_LIMIT,
    DEFAULT_TARGET_UPLOAD_PART_COUNT,
)

from .concurrency import (
    default_api_reserved_concurrency,
    default_workflow_reserved_concurrency,
    is_production_environment,
    low_quota_account_disables_reserved_concurrency,
)

FUNCTION_GROUP = Literal["api", "workflow"]

FILE_TRANSFER_UPLOAD_PREFIX: Final[str] = "uploads/"
FILE_TRANSFER_EXPORT_PREFIX: Final[str] = "exports/"
FILE_TRANSFER_TMP_PREFIX: Final[str] = "tmp/"
EXPORTS_ENABLED: Final[str] = "true"
ACTIVITY_STORE_BACKEND: Final[str] = "dynamodb"
FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS: Final[int] = 1800
FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS: Final[int] = 900
FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES: Final[int] = 100 * 1024 * 1024
FILE_TRANSFER_PART_SIZE_BYTES: Final[int] = 128 * 1024 * 1024
FILE_TRANSFER_MAX_CONCURRENCY: Final[int] = 4
FILE_TRANSFER_MAX_UPLOAD_BYTES: Final[int] = 536_870_912_000
FILE_TRANSFER_POLICY_APPCONFIG_POLL_INTERVAL_SECONDS: Final[int] = 60
FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS: Final[int] = 24 * 60 * 60
FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT: Final[int] = 200
FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES: Final[int] = 2 * 1024 * 1024 * 1024
FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY_LIMIT: Final[int] = 8
FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS: Final[int] = 5
FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS: Final[int] = 30 * 60
FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES: Final[int] = (
    50 * 1024 * 1024 * 1024
)
IDEMPOTENCY_ENABLED_API: Final[str] = "true"
IDEMPOTENCY_ENABLED_WORKFLOW: Final[str] = "false"
FILE_TRANSFER_USE_ACCELERATE_ENDPOINT: Final[str] = "false"
FILE_TRANSFER_CHECKSUM_MODE: Final[str] = "none"


@dataclass(frozen=True)
class RuntimeEnvContractSpec:
    """Single runtime environment contract item."""

    name: str
    source: str
    condition: str
    value: str | None = None


@dataclass(frozen=True)
class RuntimeFunctionAuthority:
    """Canonical metadata for one deployable Lambda runtime surface."""

    logical_id: str
    function_name: str
    handler: str
    function_group: FUNCTION_GROUP


@dataclass(frozen=True)
class WorkflowRuntimeBindings:
    """Resolved CloudFormation values required by workflow task Lambdas."""

    file_transfer_bucket: str
    upload_sessions_table: str
    transfer_usage_table: str
    exports_dynamodb_table: str
    export_copy_parts_table: str
    export_copy_queue_url: str


@dataclass(frozen=True)
class ApiRuntimeBindings(WorkflowRuntimeBindings):
    """Resolved CloudFormation and deploy values required by the API Lambda."""

    allowed_origins_json: str
    activity_rollups_table: str
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    transfer_policy_appconfig_application: str
    transfer_policy_appconfig_environment: str
    transfer_policy_appconfig_profile: str
    idempotency_dynamodb_table: str
    export_workflow_state_machine_arn: str
    api_release_artifact_sha256: str


API_FUNCTION: Final[RuntimeFunctionAuthority] = RuntimeFunctionAuthority(
    logical_id="NovaApiFunction",
    function_name="NovaApiFunction",
    handler="nova_file_api.lambda_handler.handler",
    function_group="api",
)

WORKFLOW_FUNCTIONS: Final[tuple[RuntimeFunctionAuthority, ...]] = (
    RuntimeFunctionAuthority(
        logical_id="ValidateExportFunction",
        function_name="ValidateExportFunction",
        handler="nova_workflows.handlers.validate_export_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="PrepareExportCopyFunction",
        function_name="PrepareExportCopyFunction",
        handler="nova_workflows.handlers.prepare_export_copy_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="CopyExportFunction",
        function_name="CopyExportFunction",
        handler="nova_workflows.handlers.copy_export_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="StartQueuedExportCopyFunction",
        function_name="StartQueuedExportCopyFunction",
        handler="nova_workflows.handlers.start_queued_export_copy_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="PollQueuedExportCopyFunction",
        function_name="PollQueuedExportCopyFunction",
        handler="nova_workflows.handlers.poll_queued_export_copy_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="FinalizeExportFunction",
        function_name="FinalizeExportFunction",
        handler="nova_workflows.handlers.finalize_export_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="ExportCopyWorkerFunction",
        function_name="ExportCopyWorkerFunction",
        handler="nova_workflows.handlers.export_copy_worker_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="FailExportFunction",
        function_name="FailExportFunction",
        handler="nova_workflows.handlers.fail_export_handler",
        function_group="workflow",
    ),
    RuntimeFunctionAuthority(
        logical_id="ReconcileTransferStateFunction",
        function_name="ReconcileTransferStateFunction",
        handler="nova_workflows.handlers.reconcile_transfer_state_handler",
        function_group="workflow",
    ),
)

_WORKFLOW_COMMON_LITERAL_ENV: Final[dict[str, str]] = {
    "FILE_TRANSFER_UPLOAD_PREFIX": FILE_TRANSFER_UPLOAD_PREFIX,
    "FILE_TRANSFER_EXPORT_PREFIX": FILE_TRANSFER_EXPORT_PREFIX,
    "FILE_TRANSFER_TMP_PREFIX": FILE_TRANSFER_TMP_PREFIX,
    "EXPORTS_ENABLED": EXPORTS_ENABLED,
    "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES": str(
        FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES
    ),
    "FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES": str(
        FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES
    ),
    "FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS": str(
        FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS
    ),
    "FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS": str(
        FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS
    ),
}

_API_LITERAL_ENV: Final[dict[str, str]] = {
    "ACTIVITY_STORE_BACKEND": ACTIVITY_STORE_BACKEND,
    "FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS": str(
        FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS
    ),
    "FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS": str(
        FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS
    ),
    "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES": str(
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES
    ),
    "FILE_TRANSFER_PART_SIZE_BYTES": str(FILE_TRANSFER_PART_SIZE_BYTES),
    "FILE_TRANSFER_MAX_CONCURRENCY": str(FILE_TRANSFER_MAX_CONCURRENCY),
    "FILE_TRANSFER_MAX_UPLOAD_BYTES": str(FILE_TRANSFER_MAX_UPLOAD_BYTES),
    "FILE_TRANSFER_TARGET_UPLOAD_PART_COUNT": str(
        DEFAULT_TARGET_UPLOAD_PART_COUNT
    ),
    "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT": (
        FILE_TRANSFER_USE_ACCELERATE_ENDPOINT
    ),
    "FILE_TRANSFER_POLICY_ID": DEFAULT_POLICY_ID,
    "FILE_TRANSFER_POLICY_VERSION": DEFAULT_POLICY_VERSION,
    "FILE_TRANSFER_ACTIVE_MULTIPART_UPLOAD_LIMIT": str(
        DEFAULT_ACTIVE_MULTIPART_UPLOAD_LIMIT
    ),
    "FILE_TRANSFER_DAILY_INGRESS_BUDGET_BYTES": str(
        DEFAULT_DAILY_INGRESS_BUDGET_BYTES
    ),
    "FILE_TRANSFER_SIGN_REQUESTS_PER_UPLOAD_LIMIT": str(
        DEFAULT_SIGN_REQUESTS_PER_UPLOAD_LIMIT
    ),
    "FILE_TRANSFER_CHECKSUM_MODE": FILE_TRANSFER_CHECKSUM_MODE,
    "FILE_TRANSFER_POLICY_APPCONFIG_POLL_INTERVAL_SECONDS": str(
        FILE_TRANSFER_POLICY_APPCONFIG_POLL_INTERVAL_SECONDS
    ),
    "IDEMPOTENCY_ENABLED": IDEMPOTENCY_ENABLED_API,
}

_WORKFLOW_TASK_LITERAL_ENV: Final[dict[str, str]] = {
    "FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS": str(
        FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS
    ),
    "FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT": str(
        FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT
    ),
    "IDEMPOTENCY_ENABLED": IDEMPOTENCY_ENABLED_WORKFLOW,
}

_WORKFLOW_COMMON_CONTRACT: Final[tuple[RuntimeEnvContractSpec, ...]] = (
    RuntimeEnvContractSpec("FILE_TRANSFER_BUCKET", "stack resource", "always"),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_UPLOAD_PREFIX",
        "literal",
        "always",
        FILE_TRANSFER_UPLOAD_PREFIX,
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_PREFIX",
        "literal",
        "always",
        FILE_TRANSFER_EXPORT_PREFIX,
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_TMP_PREFIX",
        "literal",
        "always",
        FILE_TRANSFER_TMP_PREFIX,
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE", "stack resource", "always"
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_USAGE_TABLE", "stack resource", "always"
    ),
    RuntimeEnvContractSpec("EXPORTS_ENABLED", "literal", "always", "true"),
    RuntimeEnvContractSpec(
        "EXPORTS_DYNAMODB_TABLE", "stack resource", "always"
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES",
        "literal",
        "always",
        str(FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY",
        "derived from workflow reserved concurrency",
        "always",
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES",
        "literal",
        "always",
        str(FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS",
        "literal",
        "always",
        str(FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS",
        "literal",
        "always",
        str(FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE",
        "stack resource",
        "always",
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL",
        "stack resource",
        "always",
    ),
)

_API_ONLY_CONTRACT: Final[tuple[RuntimeEnvContractSpec, ...]] = (
    RuntimeEnvContractSpec("ALLOWED_ORIGINS", "CDK deploy input", "always"),
    RuntimeEnvContractSpec(
        "ACTIVITY_STORE_BACKEND",
        "literal",
        "always",
        ACTIVITY_STORE_BACKEND,
    ),
    RuntimeEnvContractSpec(
        "ACTIVITY_ROLLUPS_TABLE", "stack resource", "always"
    ),
    RuntimeEnvContractSpec("OIDC_ISSUER", "CDK deploy input", "always"),
    RuntimeEnvContractSpec("OIDC_AUDIENCE", "CDK deploy input", "always"),
    RuntimeEnvContractSpec("OIDC_JWKS_URL", "CDK deploy input", "always"),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
        "literal",
        "always",
        str(FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
        "literal",
        "always",
        str(FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_MAX_CONCURRENCY",
        "literal",
        "always",
        str(FILE_TRANSFER_MAX_CONCURRENCY),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_MAX_UPLOAD_BYTES",
        "literal",
        "always",
        str(FILE_TRANSFER_MAX_UPLOAD_BYTES),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        "literal",
        "always",
        str(FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_PART_SIZE_BYTES",
        "literal",
        "always",
        str(FILE_TRANSFER_PART_SIZE_BYTES),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_POLICY_ID",
        "literal",
        "always",
        DEFAULT_POLICY_ID,
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_POLICY_VERSION",
        "literal",
        "always",
        DEFAULT_POLICY_VERSION,
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_ACTIVE_MULTIPART_UPLOAD_LIMIT",
        "literal",
        "always",
        str(DEFAULT_ACTIVE_MULTIPART_UPLOAD_LIMIT),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_DAILY_INGRESS_BUDGET_BYTES",
        "literal",
        "always",
        str(DEFAULT_DAILY_INGRESS_BUDGET_BYTES),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_SIGN_REQUESTS_PER_UPLOAD_LIMIT",
        "literal",
        "always",
        str(DEFAULT_SIGN_REQUESTS_PER_UPLOAD_LIMIT),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION",
        "stack resource",
        "always",
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT",
        "stack resource",
        "always",
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_POLICY_APPCONFIG_POLL_INTERVAL_SECONDS",
        "literal",
        "always",
        str(FILE_TRANSFER_POLICY_APPCONFIG_POLL_INTERVAL_SECONDS),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE",
        "stack resource",
        "always",
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_TARGET_UPLOAD_PART_COUNT",
        "literal",
        "always",
        str(DEFAULT_TARGET_UPLOAD_PART_COUNT),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
        "literal",
        "always",
        FILE_TRANSFER_USE_ACCELERATE_ENDPOINT,
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_CHECKSUM_MODE",
        "literal",
        "always",
        FILE_TRANSFER_CHECKSUM_MODE,
    ),
    RuntimeEnvContractSpec(
        "IDEMPOTENCY_ENABLED",
        "literal",
        "always",
        IDEMPOTENCY_ENABLED_API,
    ),
    RuntimeEnvContractSpec(
        "IDEMPOTENCY_DYNAMODB_TABLE", "stack resource", "always"
    ),
    RuntimeEnvContractSpec(
        "EXPORT_WORKFLOW_STATE_MACHINE_ARN",
        "stack resource",
        "always",
    ),
    RuntimeEnvContractSpec(
        "API_RELEASE_ARTIFACT_SHA256",
        "release execution manifest",
        "always",
    ),
)

_WORKFLOW_TASK_ONLY_CONTRACT: Final[tuple[RuntimeEnvContractSpec, ...]] = (
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS",
        "literal",
        "always",
        str(FILE_TRANSFER_STALE_MULTIPART_CLEANUP_AGE_SECONDS),
    ),
    RuntimeEnvContractSpec(
        "FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT",
        "literal",
        "always",
        str(FILE_TRANSFER_RECONCILIATION_SCAN_LIMIT),
    ),
    RuntimeEnvContractSpec(
        "IDEMPOTENCY_ENABLED",
        "literal",
        "always",
        IDEMPOTENCY_ENABLED_WORKFLOW,
    ),
)


def default_export_copy_max_concurrency(
    workflow_reserved_concurrency: int | None,
) -> int:
    """Return the effective export-copy worker concurrency."""
    if workflow_reserved_concurrency is None:
        return FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY_LIMIT
    return min(
        FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY_LIMIT,
        workflow_reserved_concurrency,
    )


def build_workflow_common_environment(
    *,
    bindings: WorkflowRuntimeBindings,
    export_copy_max_concurrency: int,
) -> dict[str, str]:
    """Build the shared workflow and API Lambda environment block."""
    return {
        "FILE_TRANSFER_BUCKET": bindings.file_transfer_bucket,
        **_WORKFLOW_COMMON_LITERAL_ENV,
        "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE": (bindings.upload_sessions_table),
        "FILE_TRANSFER_USAGE_TABLE": bindings.transfer_usage_table,
        "EXPORTS_DYNAMODB_TABLE": bindings.exports_dynamodb_table,
        "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY": str(
            export_copy_max_concurrency
        ),
        "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE": (
            bindings.export_copy_parts_table
        ),
        "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL": (bindings.export_copy_queue_url),
    }


def build_api_lambda_environment(
    *,
    bindings: ApiRuntimeBindings,
    export_copy_max_concurrency: int,
) -> dict[str, str]:
    """Build the API Lambda environment from canonical authority."""
    common_env = build_workflow_common_environment(
        bindings=bindings,
        export_copy_max_concurrency=export_copy_max_concurrency,
    )
    return {
        **common_env,
        **_API_LITERAL_ENV,
        "ALLOWED_ORIGINS": bindings.allowed_origins_json,
        "ACTIVITY_ROLLUPS_TABLE": bindings.activity_rollups_table,
        "OIDC_ISSUER": bindings.oidc_issuer,
        "OIDC_AUDIENCE": bindings.oidc_audience,
        "OIDC_JWKS_URL": bindings.oidc_jwks_url,
        "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION": (
            bindings.transfer_policy_appconfig_application
        ),
        "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT": (
            bindings.transfer_policy_appconfig_environment
        ),
        "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE": (
            bindings.transfer_policy_appconfig_profile
        ),
        "IDEMPOTENCY_DYNAMODB_TABLE": bindings.idempotency_dynamodb_table,
        "EXPORT_WORKFLOW_STATE_MACHINE_ARN": (
            bindings.export_workflow_state_machine_arn
        ),
        "API_RELEASE_ARTIFACT_SHA256": bindings.api_release_artifact_sha256,
    }


def build_workflow_task_environment(
    *,
    bindings: WorkflowRuntimeBindings,
    export_copy_max_concurrency: int,
) -> dict[str, str]:
    """Build the workflow task Lambda environment from canonical authority."""
    common_env = build_workflow_common_environment(
        bindings=bindings,
        export_copy_max_concurrency=export_copy_max_concurrency,
    )
    return {
        **common_env,
        **_WORKFLOW_TASK_LITERAL_ENV,
    }


def api_lambda_environment_contract() -> tuple[RuntimeEnvContractSpec, ...]:
    """Return the API Lambda contract metadata."""
    return _WORKFLOW_COMMON_CONTRACT + _API_ONLY_CONTRACT


def workflow_task_environment_contract() -> tuple[RuntimeEnvContractSpec, ...]:
    """Return the workflow task Lambda contract metadata."""
    return _WORKFLOW_COMMON_CONTRACT + _WORKFLOW_TASK_ONLY_CONTRACT


def workflow_handler_names() -> tuple[str, ...]:
    """Return the canonical workflow task handler inventory."""
    return tuple(item.handler for item in WORKFLOW_FUNCTIONS)


def function_logical_id_prefixes() -> dict[str, tuple[str, ...]]:
    """Return the validator-facing logical id prefixes by function group."""
    return {
        "api": (API_FUNCTION.logical_id,),
        "workflow": tuple(item.logical_id for item in WORKFLOW_FUNCTIONS),
    }


def workflow_function_authority(
    logical_id: str,
) -> RuntimeFunctionAuthority:
    """Return the canonical workflow function authority for one logical id."""
    for item in WORKFLOW_FUNCTIONS:
        if item.logical_id == logical_id:
            return item
    raise KeyError(logical_id)


def expected_runtime_reserved_concurrency(
    *,
    environment_name: str,
    account_concurrency_limit: int,
) -> tuple[int | None, int | None]:
    """Return expected API and workflow reservations for one deploy."""
    if low_quota_account_disables_reserved_concurrency(
        account_concurrency_limit
    ) and not is_production_environment(environment_name):
        return None, None
    return (
        default_api_reserved_concurrency(environment_name),
        default_workflow_reserved_concurrency(environment_name),
    )
