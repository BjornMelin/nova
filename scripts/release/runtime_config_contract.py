"""Canonical runtime and deploy contract metadata for Nova release tooling."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, get_args, get_origin

from pydantic import SecretStr
from pydantic.fields import FieldInfo

from nova_file_api.config import Settings

try:
    from scripts.release.release_paths import RUNTIME_CONFIG_GENERATED_MD_PATH
except ModuleNotFoundError:  # pragma: no cover - test harness fallback
    RUNTIME_CONFIG_GENERATED_MD_PATH = (
        "docs/contracts/runtime-config-contract.generated.md"
    )

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RuntimeSettingContract:
    """Single runtime setting derived from the canonical Settings model."""

    field_name: str
    env_var: str
    type_label: str
    default_repr: str
    required: bool
    secret: bool
    required_when: str | None = None


@dataclass(frozen=True)
class EnvJsonOverrideContract:
    """Supported non-secret runtime override accepted through ENV_VARS_JSON."""

    env_var: str
    cloudformation_parameter: str


@dataclass(frozen=True)
class DeployInputContract:
    """Context or environment input consumed by infra or workflows."""

    name: str
    source: str
    required: bool
    description: str


@dataclass(frozen=True)
class RuntimeEnvContract:
    """Environment variable expected in a deployed Lambda runtime."""

    name: str
    source: str
    condition: str
    value: str | None = None


EXTRA_RUNTIME_ENV_VARS = (
    "API_RELEASE_ARTIFACT_SHA256",
    "AWS_DEFAULT_REGION",
)


def _env_var_name(field_name: str, field: FieldInfo) -> str:
    validation_alias = field.validation_alias
    if isinstance(validation_alias, str) and validation_alias.strip():
        return validation_alias.strip()
    raise ValueError(
        "Runtime setting "
        f"{field_name} must declare an explicit non-empty string "
        "validation_alias"
    )


def _annotation_contains(annotation: Any, target: type[object]) -> bool:
    if annotation is target:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(
        _annotation_contains(arg, target) for arg in get_args(annotation)
    )


def _type_label(annotation: Any) -> str:
    if annotation is Any:
        return "Any"
    if annotation is type(None):
        return "None"

    origin = get_origin(annotation)
    if origin is None:
        if hasattr(annotation, "__name__"):
            return str(annotation.__name__)
        return str(annotation).replace("typing.", "")

    if origin in {list, tuple, set, frozenset}:
        inner = ", ".join(_type_label(arg) for arg in get_args(annotation))
        return f"{origin.__name__}[{inner}]"

    if origin is dict:
        inner = ", ".join(_type_label(arg) for arg in get_args(annotation))
        return f"dict[{inner}]"

    args = [_type_label(arg) for arg in get_args(annotation)]
    if len(args) == 2 and "None" in args:
        non_none = next(arg for arg in args if arg != "None")
        return f"{non_none} | None"
    return " | ".join(args)


def _default_repr(field: FieldInfo) -> str:
    if field.default_factory is not None:
        return "<factory>"
    if field.is_required():
        return "<required>"
    value = field.get_default(call_default_factory=True)
    if isinstance(value, SecretStr):
        return "<secret>"
    return repr(value)


def runtime_setting_contracts() -> tuple[RuntimeSettingContract, ...]:
    """Return the runtime settings contract derived from ``Settings``."""
    contracts = []
    for field_name, field in Settings.model_fields.items():
        env_var = _env_var_name(field_name, field)
        required_when = None
        if env_var == "IDEMPOTENCY_DYNAMODB_TABLE":
            required_when = "when IDEMPOTENCY_ENABLED=true in the API Lambda"
        elif env_var == "EXPORT_WORKFLOW_STATE_MACHINE_ARN":
            required_when = "when EXPORTS_ENABLED=true in the API Lambda"
        contracts.append(
            RuntimeSettingContract(
                field_name=field_name,
                env_var=env_var,
                type_label=_type_label(field.annotation),
                default_repr=_default_repr(field),
                required=field.is_required(),
                secret=_annotation_contains(field.annotation, SecretStr),
                required_when=required_when,
            )
        )
    return tuple(sorted(contracts, key=lambda contract: contract.env_var))


ENV_JSON_OVERRIDES: tuple[EnvJsonOverrideContract, ...] = (
    EnvJsonOverrideContract("OIDC_ISSUER", "OidcIssuer"),
    EnvJsonOverrideContract("OIDC_AUDIENCE", "OidcAudience"),
    EnvJsonOverrideContract("OIDC_JWKS_URL", "OidcJwksUrl"),
    EnvJsonOverrideContract("OIDC_REQUIRED_SCOPES", "OidcRequiredScopes"),
    EnvJsonOverrideContract(
        "OIDC_REQUIRED_PERMISSIONS", "OidcRequiredPermissions"
    ),
    EnvJsonOverrideContract("OIDC_CLOCK_SKEW_SECONDS", "OidcClockSkewSeconds"),
    EnvJsonOverrideContract(
        "BLOCKING_IO_THREAD_TOKENS", "BlockingIoThreadTokens"
    ),
    EnvJsonOverrideContract("CACHE_LOCAL_TTL_SECONDS", "CacheLocalTtlSeconds"),
    EnvJsonOverrideContract("CACHE_LOCAL_MAX_ENTRIES", "CacheLocalMaxEntries"),
    EnvJsonOverrideContract("CACHE_KEY_PREFIX", "CacheKeyPrefix"),
    EnvJsonOverrideContract(
        "CACHE_KEY_SCHEMA_VERSION", "CacheKeySchemaVersion"
    ),
    EnvJsonOverrideContract(
        "AUTH_JWT_CACHE_MAX_TTL_SECONDS", "AuthJwtCacheMaxTtlSeconds"
    ),
    EnvJsonOverrideContract("IDEMPOTENCY_ENABLED", "IdempotencyEnabled"),
    EnvJsonOverrideContract("IDEMPOTENCY_TTL_SECONDS", "IdempotencyTtlSeconds"),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
        "FileTransferPresignUploadTtlSeconds",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
        "FileTransferPresignDownloadTtlSeconds",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY",
        "FileTransferExportCopyMaxConcurrency",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES",
        "FileTransferExportCopyPartSizeBytes",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_EXPORT_PREFIX", "FileTransferExportPrefix"
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        "FileTransferMultipartThresholdBytes",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_PART_SIZE_BYTES", "FileTransferPartSizeBytes"
    ),
    EnvJsonOverrideContract("FILE_TRANSFER_POLICY_ID", "FileTransferPolicyId"),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_POLICY_VERSION", "FileTransferPolicyVersion"
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_MAX_CONCURRENCY", "FileTransferMaxConcurrency"
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
        "FileTransferUseAccelerateEndpoint",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_MAX_UPLOAD_BYTES", "FileTransferMaxUploadBytes"
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_RESUMABLE_WINDOW_SECONDS",
        "FileTransferResumableWindowSeconds",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_TARGET_UPLOAD_PART_COUNT",
        "FileTransferTargetUploadPartCount",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_UPLOAD_PREFIX", "FileTransferUploadPrefix"
    ),
)

DEPLOY_INPUTS: tuple[DeployInputContract, ...] = (
    DeployInputContract(
        "API_LAMBDA_ARTIFACT_BUCKET",
        "release execution manifest",
        True,
        "S3 bucket containing the immutable API Lambda zip.",
    ),
    DeployInputContract(
        "API_LAMBDA_ARTIFACT_KEY",
        "release execution manifest",
        True,
        "S3 key for the immutable API Lambda zip.",
    ),
    DeployInputContract(
        "API_LAMBDA_ARTIFACT_SHA256",
        "release execution manifest",
        True,
        "SHA256 digest for the immutable API Lambda zip.",
    ),
    DeployInputContract(
        "WORKFLOW_LAMBDA_ARTIFACT_BUCKET",
        "release execution manifest",
        True,
        "S3 bucket containing the immutable workflow Lambda zip.",
    ),
    DeployInputContract(
        "WORKFLOW_LAMBDA_ARTIFACT_KEY",
        "release execution manifest",
        True,
        "S3 key for the immutable workflow Lambda zip.",
    ),
    DeployInputContract(
        "WORKFLOW_LAMBDA_ARTIFACT_SHA256",
        "release execution manifest",
        True,
        "SHA256 digest for the immutable workflow Lambda zip.",
    ),
    DeployInputContract(
        "runtime_stack_id",
        "release control-plane environment input",
        True,
        "CloudFormation stack id to deploy in the current environment.",
    ),
    DeployInputContract(
        "api_domain_name",
        "CDK context / runtime deploy input",
        True,
        "Canonical public custom domain for the Regional REST API.",
    ),
    DeployInputContract(
        "certificate_arn",
        "CDK context / runtime deploy input",
        True,
        "Regional ACM certificate used by the API custom domain.",
    ),
    DeployInputContract(
        "hosted_zone_id",
        "CDK context / runtime deploy input",
        True,
        "Route 53 hosted zone id that owns the API alias record.",
    ),
    DeployInputContract(
        "hosted_zone_name",
        "CDK context / runtime deploy input",
        True,
        "Route 53 hosted zone name that owns the API alias record.",
    ),
    DeployInputContract(
        "jwt_issuer",
        "CDK context / runtime deploy input",
        True,
        "OIDC issuer URL injected into the API Lambda.",
    ),
    DeployInputContract(
        "jwt_audience",
        "CDK context / runtime deploy input",
        True,
        "OIDC audience injected into the API Lambda.",
    ),
    DeployInputContract(
        "jwt_jwks_url",
        "CDK context / runtime deploy input",
        True,
        "OIDC JWKS URL injected into the API Lambda.",
    ),
    DeployInputContract(
        "allowed_origins",
        "CDK context / runtime deploy input",
        False,
        "Optional browser origin allowlist serialized into ALLOWED_ORIGINS.",
    ),
    DeployInputContract(
        "enable_waf",
        "CDK context / runtime deploy input",
        False,
        "Optional toggle for the Regional WAF. Defaults to true in prod "
        "and false elsewhere.",
    ),
    DeployInputContract(
        "enable_reserved_concurrency",
        "CDK context / runtime deploy input",
        False,
        "Optional toggle for non-production reserved concurrency.",
    ),
)

API_LAMBDA_ENV: tuple[RuntimeEnvContract, ...] = (
    RuntimeEnvContract("FILE_TRANSFER_BUCKET", "stack resource", "always"),
    RuntimeEnvContract(
        "FILE_TRANSFER_UPLOAD_PREFIX", "literal", "always", "uploads/"
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_EXPORT_PREFIX", "literal", "always", "exports/"
    ),
    RuntimeEnvContract("FILE_TRANSFER_TMP_PREFIX", "literal", "always", "tmp/"),
    RuntimeEnvContract("EXPORTS_ENABLED", "literal", "always", "true"),
    RuntimeEnvContract("EXPORTS_DYNAMODB_TABLE", "stack resource", "always"),
    RuntimeEnvContract("ALLOWED_ORIGINS", "CDK deploy input", "always"),
    RuntimeEnvContract(
        "ACTIVITY_STORE_BACKEND", "literal", "always", "dynamodb"
    ),
    RuntimeEnvContract("ACTIVITY_ROLLUPS_TABLE", "stack resource", "always"),
    RuntimeEnvContract("OIDC_ISSUER", "CDK deploy input", "always"),
    RuntimeEnvContract("OIDC_AUDIENCE", "CDK deploy input", "always"),
    RuntimeEnvContract("OIDC_JWKS_URL", "CDK deploy input", "always"),
    RuntimeEnvContract(
        "FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
        "literal",
        "always",
        "1800",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
        "literal",
        "always",
        "900",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY",
        "literal",
        "always",
        "8",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES",
        "literal",
        "always",
        str(2 * 1024 * 1024 * 1024),
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_MAX_CONCURRENCY", "literal", "always", "4"
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_ACTIVE_MULTIPART_UPLOAD_LIMIT",
        "literal",
        "always",
        "200",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_DAILY_INGRESS_BUDGET_BYTES",
        "literal",
        "always",
        str(1024 * 1024 * 1024 * 1024),
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_MAX_UPLOAD_BYTES",
        "literal",
        "always",
        str(536_870_912_000),
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        "literal",
        "always",
        str(100 * 1024 * 1024),
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_PART_SIZE_BYTES",
        "literal",
        "always",
        str(128 * 1024 * 1024),
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_POLICY_ID", "literal", "always", "default"
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_POLICY_VERSION",
        "literal",
        "always",
        "2026-04-03",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION",
        "stack resource",
        "always",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT",
        "stack resource",
        "always",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_POLICY_APPCONFIG_POLL_INTERVAL_SECONDS",
        "literal",
        "always",
        "60",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE",
        "stack resource",
        "always",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_RESUMABLE_WINDOW_SECONDS",
        "literal",
        "always",
        str(7 * 24 * 60 * 60),
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_TARGET_UPLOAD_PART_COUNT",
        "literal",
        "always",
        "2000",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE",
        "stack resource",
        "always",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_USAGE_TABLE",
        "stack resource",
        "always",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
        "literal",
        "always",
        "false",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_SIGN_REQUESTS_PER_UPLOAD_LIMIT",
        "literal",
        "always",
        "512",
    ),
    RuntimeEnvContract("IDEMPOTENCY_ENABLED", "literal", "always", "true"),
    RuntimeEnvContract(
        "IDEMPOTENCY_DYNAMODB_TABLE", "stack resource", "always"
    ),
    RuntimeEnvContract(
        "EXPORT_WORKFLOW_STATE_MACHINE_ARN",
        "stack resource",
        "always",
    ),
    RuntimeEnvContract(
        "API_RELEASE_ARTIFACT_SHA256",
        "release execution manifest",
        "always",
    ),
)

WORKFLOW_TASK_ENV: tuple[RuntimeEnvContract, ...] = (
    RuntimeEnvContract("FILE_TRANSFER_BUCKET", "stack resource", "always"),
    RuntimeEnvContract(
        "FILE_TRANSFER_UPLOAD_PREFIX", "literal", "always", "uploads/"
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_EXPORT_PREFIX", "literal", "always", "exports/"
    ),
    RuntimeEnvContract("FILE_TRANSFER_TMP_PREFIX", "literal", "always", "tmp/"),
    RuntimeEnvContract(
        "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY",
        "literal",
        "always",
        "8",
    ),
    RuntimeEnvContract(
        "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES",
        "literal",
        "always",
        str(2 * 1024 * 1024 * 1024),
    ),
    RuntimeEnvContract("EXPORTS_ENABLED", "literal", "always", "true"),
    RuntimeEnvContract("EXPORTS_DYNAMODB_TABLE", "stack resource", "always"),
    RuntimeEnvContract("IDEMPOTENCY_ENABLED", "literal", "always", "false"),
)

FORBIDDEN_ENV_JSON_KEYS = ("IDEMPOTENCY_MODE", "IDEMPOTENCY_DYNAMODB_TABLE")
API_LAMBDA_FORBIDDEN_ENV_VARS = (
    "ENV",
    "ENV_DICT",
    "AUTH_APP_SECRET",
    "NOVA_RUNTIME_PROFILE",
)
WORKFLOW_TASK_FORBIDDEN_ENV_VARS = (
    "ACTIVITY_STORE_BACKEND",
    "ACTIVITY_ROLLUPS_TABLE",
    "ALLOWED_ORIGINS",
    "API_RELEASE_ARTIFACT_SHA256",
    "EXPORT_WORKFLOW_STATE_MACHINE_ARN",
    "IDEMPOTENCY_DYNAMODB_TABLE",
    "NOVA_RUNTIME_PROFILE",
    "OIDC_AUDIENCE",
    "OIDC_ISSUER",
    "OIDC_JWKS_URL",
)
CONTRACT_JSON_PATH = "packages/contracts/fixtures/runtime_config_contract.json"
CONTRACT_MARKDOWN_PATH = RUNTIME_CONFIG_GENERATED_MD_PATH


def _assert_known_runtime_env(env_vars: Iterable[str]) -> None:
    known = {contract.env_var for contract in runtime_setting_contracts()}
    extras = set(EXTRA_RUNTIME_ENV_VARS)
    unknown = sorted(set(env_vars) - known - extras)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown runtime contract env vars: {joined}")


def _assert_non_secret_runtime_env(env_vars: Iterable[str]) -> None:
    contracts = {
        contract.env_var: contract for contract in runtime_setting_contracts()
    }
    secret_env_vars = sorted(
        env_var
        for env_var in set(env_vars)
        if (contract := contracts.get(env_var)) is not None and contract.secret
    )
    if secret_env_vars:
        joined = ", ".join(secret_env_vars)
        raise ValueError(
            f"Secret runtime contract env vars are not allowed here: {joined}"
        )


_assert_known_runtime_env(contract.name for contract in API_LAMBDA_ENV)
_assert_known_runtime_env(contract.name for contract in WORKFLOW_TASK_ENV)
_assert_known_runtime_env(override.env_var for override in ENV_JSON_OVERRIDES)
_assert_non_secret_runtime_env(
    override.env_var for override in ENV_JSON_OVERRIDES
)


def build_contract_payload() -> dict[str, Any]:
    """Build the full runtime-config contract payload."""
    return {
        "schema_version": 2,
        "settings_source": "packages/nova_file_api/src/nova_file_api/config.py",
        "extra_runtime_env_vars": list(EXTRA_RUNTIME_ENV_VARS),
        "settings": [
            asdict(contract) for contract in runtime_setting_contracts()
        ],
        "env_vars_json": {
            "supported_overrides": [
                asdict(override) for override in ENV_JSON_OVERRIDES
            ],
            "forbidden_keys": list(FORBIDDEN_ENV_JSON_KEYS),
        },
        "deploy_inputs": [asdict(item) for item in DEPLOY_INPUTS],
        "api_lambda_environment": {
            "env": [asdict(contract) for contract in API_LAMBDA_ENV],
            "forbidden_env_vars": list(API_LAMBDA_FORBIDDEN_ENV_VARS),
        },
        "workflow_task_environment": {
            "handlers": [
                "nova_workflows.handlers.validate_export_handler",
                "nova_workflows.handlers.copy_export_handler",
                "nova_workflows.handlers.finalize_export_handler",
                "nova_workflows.handlers.fail_export_handler",
            ],
            "env": [asdict(contract) for contract in WORKFLOW_TASK_ENV],
            "forbidden_env_vars": list(WORKFLOW_TASK_FORBIDDEN_ENV_VARS),
        },
    }


def contract_json_path() -> Path:
    """Return the canonical generated JSON artifact path."""
    return REPO_ROOT / CONTRACT_JSON_PATH


def contract_markdown_path() -> Path:
    """Return the canonical generated Markdown artifact path."""
    return REPO_ROOT / CONTRACT_MARKDOWN_PATH


def render_contract_json() -> str:
    """Render the canonical contract JSON artifact."""
    return json.dumps(build_contract_payload(), indent=2, sort_keys=True) + "\n"


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _join_backticked(values: Iterable[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def _render_settings_table(settings: list[dict[str, Any]]) -> str:
    rows = [
        (
            "| Env Var | Field | Type | Required | Required When | Secret | "
            "Default |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows.extend(
        (
            "| {env_var} | {field_name} | {type_label} | {required} | "
            "{required_when} | {secret} | `{default_repr}` |".format(
                env_var=setting["env_var"],
                field_name=setting["field_name"],
                type_label=_md_cell(setting["type_label"]),
                required="yes" if setting["required"] else "no",
                required_when=_md_cell(setting.get("required_when") or "-"),
                secret="yes" if setting["secret"] else "no",
                default_repr=_md_cell(setting["default_repr"]),
            )
        )
        for setting in settings
    )
    return "\n".join(rows)


def _render_env_json_table(entries: list[dict[str, Any]]) -> str:
    rows = [
        "| ENV_VARS_JSON key | CloudFormation parameter |",
        "| --- | --- |",
    ]
    rows.extend(
        (
            "| {env_var} | {cloudformation_parameter} |".format(
                env_var=_md_cell(entry["env_var"]),
                cloudformation_parameter=_md_cell(
                    entry["cloudformation_parameter"]
                ),
            )
        )
        for entry in entries
    )
    return "\n".join(rows)


def _render_deploy_inputs_table(entries: list[dict[str, Any]]) -> str:
    rows = [
        "| Input | Source | Required | Description |",
        "| --- | --- | --- | --- |",
    ]
    rows.extend(
        (
            "| {name} | {source} | {required} | {description} |".format(
                name=_md_cell(entry["name"]),
                source=_md_cell(entry["source"]),
                required="yes" if entry["required"] else "no",
                description=_md_cell(entry["description"]),
            )
        )
        for entry in entries
    )
    return "\n".join(rows)


def _render_env_table(entries: list[dict[str, Any]]) -> str:
    rows = [
        "| Name | Source | Condition | Value |",
        "| --- | --- | --- | --- |",
    ]
    rows.extend(
        (
            "| {name} | {source} | {condition} | {value} |".format(
                name=_md_cell(entry["name"]),
                source=_md_cell(entry["source"]),
                condition=_md_cell(entry["condition"]),
                value=_md_cell(entry.get("value") or "-"),
            )
        )
        for entry in entries
    )
    return "\n".join(rows)


def render_contract_markdown() -> str:
    """Render the generated operator-facing Markdown summary."""
    payload = build_contract_payload()
    sections = [
        "# Runtime Config Contract",
        "",
        "Status: Generated",
        "Owner: nova runtime architecture",
        "",
        "This file is generated by "
        "`scripts/release/generate_runtime_config_contract.py`. "
        "Do not edit it by hand.",
        "",
        "Canonical sources:",
        "- `packages/nova_file_api/src/nova_file_api/config.py` (`Settings`)",
        "- `infra/nova_cdk/src/nova_cdk/runtime_stack.py` "
        "(deployed Lambda environment wiring)",
        "- `scripts/release/runtime_config_contract.py` "
        "(curated deploy/runtime metadata)",
        "- Runtime env vars are derived only from explicit "
        "`Settings` `validation_alias` values; `alias` and implicit uppercase "
        "fallbacks are invalid",
        "",
        "## Canonical runtime settings",
        "",
        _render_settings_table(payload["settings"]),
        "",
        "## Generated ENV_VARS_JSON support matrix",
        "",
        _render_env_json_table(payload["env_vars_json"]["supported_overrides"]),
        "",
        "Forbidden ENV_VARS_JSON keys:",
        _join_backticked(payload["env_vars_json"]["forbidden_keys"]),
        "",
        "## Runtime deploy inputs",
        "",
        _render_deploy_inputs_table(payload["deploy_inputs"]),
        "",
        "## API Lambda environment contract",
        "",
        _render_env_table(payload["api_lambda_environment"]["env"]),
        "",
        "Forbidden API Lambda env vars:",
        _join_backticked(
            payload["api_lambda_environment"]["forbidden_env_vars"]
        ),
        "",
        "## Workflow task Lambda environment contract",
        "",
        "Task handlers:",
        _join_backticked(payload["workflow_task_environment"]["handlers"]),
        "",
        _render_env_table(payload["workflow_task_environment"]["env"]),
        "",
        "Forbidden workflow task env vars:",
        _join_backticked(
            payload["workflow_task_environment"]["forbidden_env_vars"]
        ),
        "",
        "Generated extra runtime env vars intentionally outside `Settings`:",
        _join_backticked(payload["extra_runtime_env_vars"]),
        "",
    ]
    return "\n".join(sections)
