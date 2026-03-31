"""Canonical runtime-config contract metadata for Nova release tooling."""

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
        "docs/release/runtime-config-contract.generated.md"
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
class TemplateEnvContract:
    """Environment or secret value expected in a deployed runtime template."""

    name: str
    source: str
    condition: str
    value: str | None = None
    secret: bool = False


EXTRA_RUNTIME_ENV_VARS = ("AWS_DEFAULT_REGION", "NOVA_RUNTIME_PROFILE")


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

    if origin is type(None):
        return "None"

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
    """Return the runtime settings contract derived from ``Settings``.

    Returns:
        tuple[RuntimeSettingContract, ...]: Sorted runtime setting contract
            entries derived from the canonical ``Settings`` model.

    Raises:
        None.
    """
    contracts = []
    for field_name, field in Settings.model_fields.items():
        env_var = _env_var_name(field_name, field)
        required_when = None
        if env_var == "IDEMPOTENCY_DYNAMODB_TABLE":
            required_when = (
                "when API idempotency enabled and JOBS_RUNTIME_MODE!=worker"
            )
        elif env_var == "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN":
            required_when = (
                "when JOBS_QUEUE_BACKEND=stepfunctions and JOBS_ENABLED=true"
            )
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
        "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        "FileTransferMultipartThresholdBytes",
    ),
    EnvJsonOverrideContract(
        "FILE_TRANSFER_PART_SIZE_BYTES", "FileTransferPartSizeBytes"
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
)


SERVICE_TEMPLATE_ENV: tuple[TemplateEnvContract, ...] = (
    TemplateEnvContract("AWS_DEFAULT_REGION", "stack parameter", "always"),
    TemplateEnvContract("ENVIRONMENT", "task parameter", "always"),
    TemplateEnvContract("NOVA_RUNTIME_PROFILE", "task parameter", "always"),
    TemplateEnvContract("OIDC_ISSUER", "task parameter", "always"),
    TemplateEnvContract("OIDC_AUDIENCE", "task parameter", "always"),
    TemplateEnvContract("OIDC_JWKS_URL", "task parameter", "always"),
    TemplateEnvContract("OIDC_REQUIRED_SCOPES", "task parameter", "always"),
    TemplateEnvContract(
        "OIDC_REQUIRED_PERMISSIONS", "task parameter", "always"
    ),
    TemplateEnvContract("OIDC_CLOCK_SKEW_SECONDS", "task parameter", "always"),
    TemplateEnvContract(
        "BLOCKING_IO_THREAD_TOKENS", "task parameter", "always"
    ),
    TemplateEnvContract("FILE_TRANSFER_ENABLED", "stack-derived", "always"),
    TemplateEnvContract("JOBS_ENABLED", "stack-derived", "always"),
    TemplateEnvContract("JOBS_QUEUE_BACKEND", "stack-derived", "always"),
    TemplateEnvContract("JOBS_REPOSITORY_BACKEND", "stack-derived", "always"),
    TemplateEnvContract("JOBS_RUNTIME_MODE", "literal", "always"),
    TemplateEnvContract("ACTIVITY_STORE_BACKEND", "stack-derived", "always"),
    TemplateEnvContract("CACHE_LOCAL_TTL_SECONDS", "task parameter", "always"),
    TemplateEnvContract("CACHE_LOCAL_MAX_ENTRIES", "task parameter", "always"),
    TemplateEnvContract("CACHE_KEY_PREFIX", "task parameter", "always"),
    TemplateEnvContract("CACHE_KEY_SCHEMA_VERSION", "task parameter", "always"),
    TemplateEnvContract(
        "AUTH_JWT_CACHE_MAX_TTL_SECONDS", "task parameter", "always"
    ),
    TemplateEnvContract("IDEMPOTENCY_ENABLED", "task parameter", "always"),
    TemplateEnvContract("IDEMPOTENCY_TTL_SECONDS", "task parameter", "always"),
    TemplateEnvContract(
        "IDEMPOTENCY_DYNAMODB_TABLE",
        "stack output",
        "when API idempotency enabled",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
        "task parameter",
        "always",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
        "task parameter",
        "always",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        "task parameter",
        "always",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_PART_SIZE_BYTES", "task parameter", "always"
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_MAX_CONCURRENCY", "task parameter", "always"
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
        "task parameter",
        "always",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_MAX_UPLOAD_BYTES", "task parameter", "always"
    ),
    TemplateEnvContract(
        "JOBS_SQS_QUEUE_URL", "stack output", "when async enabled"
    ),
    TemplateEnvContract(
        "JOBS_DYNAMODB_TABLE", "stack output", "when async enabled"
    ),
    TemplateEnvContract(
        "ACTIVITY_ROLLUPS_TABLE", "stack output", "when async enabled"
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_BUCKET", "stack parameter", "when file transfer enabled"
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_UPLOAD_PREFIX",
        "stack parameter",
        "when file transfer enabled",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_EXPORT_PREFIX",
        "stack parameter",
        "when file transfer enabled",
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_TMP_PREFIX",
        "stack parameter",
        "when file transfer enabled",
    ),
)


WORKER_TEMPLATE_ENV: tuple[TemplateEnvContract, ...] = (
    TemplateEnvContract("ENVIRONMENT", "stack parameter", "always"),
    TemplateEnvContract("AWS_DEFAULT_REGION", "stack parameter", "always"),
    TemplateEnvContract("JOBS_ENABLED", "literal", "always", value="true"),
    TemplateEnvContract(
        "JOBS_RUNTIME_MODE",
        "literal",
        "always",
        value="worker",
    ),
    TemplateEnvContract(
        "JOBS_QUEUE_BACKEND",
        "literal",
        "always",
        value="sqs",
    ),
    TemplateEnvContract("JOBS_SQS_QUEUE_URL", "stack parameter", "always"),
    TemplateEnvContract(
        "JOBS_REPOSITORY_BACKEND",
        "literal",
        "always",
        value="dynamodb",
    ),
    TemplateEnvContract("JOBS_DYNAMODB_TABLE", "stack parameter", "always"),
    TemplateEnvContract(
        "ACTIVITY_STORE_BACKEND",
        "literal",
        "always",
        value="dynamodb",
    ),
    TemplateEnvContract("ACTIVITY_ROLLUPS_TABLE", "stack parameter", "always"),
    TemplateEnvContract(
        "JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS", "stack parameter", "always"
    ),
    TemplateEnvContract("FILE_TRANSFER_BUCKET", "stack parameter", "always"),
    TemplateEnvContract(
        "FILE_TRANSFER_UPLOAD_PREFIX", "stack parameter", "always"
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_EXPORT_PREFIX", "stack parameter", "always"
    ),
    TemplateEnvContract(
        "FILE_TRANSFER_TMP_PREFIX", "stack parameter", "always"
    ),
)


FORBIDDEN_ENV_VARS = ("ENV", "ENV_DICT", "AUTH_APP_SECRET")
FORBIDDEN_ENV_JSON_KEYS = (
    "IDEMPOTENCY_MODE",
    "IDEMPOTENCY_DYNAMODB_TABLE",
)
FORBIDDEN_SERVICE_PARAMETERS = (
    "EnvVars",
    "UseLegacyEnvDict",
    "TaskRole",
    "UseLegacyTaskRolePolicy",
    "GenerateAppSecretKey",
    "AppSecretEnvVarName",
    "TaskExecutionSecretArns",
    "TaskExecutionSsmParameterArns",
)
WORKER_COMMAND = "nova-file-worker"
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


_assert_known_runtime_env(contract.name for contract in SERVICE_TEMPLATE_ENV)
_assert_known_runtime_env(contract.name for contract in WORKER_TEMPLATE_ENV)
_assert_known_runtime_env(override.env_var for override in ENV_JSON_OVERRIDES)
_assert_non_secret_runtime_env(
    override.env_var for override in ENV_JSON_OVERRIDES
)


def build_contract_payload() -> dict[str, Any]:
    """Build the full runtime-config contract payload.

    Returns:
        dict[str, Any]: Canonical runtime-config contract payload for JSON and
            Markdown renderers.

    Raises:
        None.
    """
    settings_contracts = runtime_setting_contracts()
    return {
        "schema_version": 1,
        "settings_source": "packages/nova_file_api/src/nova_file_api/config.py",
        "extra_runtime_env_vars": list(EXTRA_RUNTIME_ENV_VARS),
        "settings": [asdict(contract) for contract in settings_contracts],
        "env_vars_json": {
            "supported_overrides": [
                asdict(override) for override in ENV_JSON_OVERRIDES
            ],
            "forbidden_keys": list(FORBIDDEN_ENV_JSON_KEYS),
        },
        "service_template": {
            "env": [
                asdict(contract)
                for contract in SERVICE_TEMPLATE_ENV
                if not contract.secret
            ],
            "secrets": [
                asdict(contract)
                for contract in SERVICE_TEMPLATE_ENV
                if contract.secret
            ],
            "forbidden_env_vars": list(FORBIDDEN_ENV_VARS),
            "forbidden_parameters": list(FORBIDDEN_SERVICE_PARAMETERS),
        },
        "worker_template": {
            "command": WORKER_COMMAND,
            "env": [
                asdict(contract)
                for contract in WORKER_TEMPLATE_ENV
                if not contract.secret
            ],
            "secrets": [
                asdict(contract)
                for contract in WORKER_TEMPLATE_ENV
                if contract.secret
            ],
            "forbidden_env_vars": [
                "FILE_TRANSFER_API_BASE_URL",
                "FILE_TRANSFER_JOBS_QUEUE_URL",
                "FILE_TRANSFER_JOBS_REGION",
                "APP_SYNC_PROCESSING_MAX_BYTES",
                "JOBS_ALLOW_INSECURE_MISSING_WORKER_TOKEN_NONPROD",
                "JOBS_API_BASE_URL",
                "JOBS_WORKER_UPDATE_TOKEN",
            ],
        },
    }


def contract_json_path() -> Path:
    """Return the canonical generated JSON artifact path.

    Returns:
        Path: Repository-relative path to the generated JSON artifact.

    Raises:
        None.
    """
    return REPO_ROOT / CONTRACT_JSON_PATH


def contract_markdown_path() -> Path:
    """Return the canonical generated Markdown artifact path.

    Returns:
        Path: Repository-relative path to the generated Markdown artifact.

    Raises:
        None.
    """
    return REPO_ROOT / CONTRACT_MARKDOWN_PATH


def render_contract_json() -> str:
    """Render the canonical contract JSON artifact.

    Returns:
        str: Serialized contract payload with stable indentation.

    Raises:
        None.
    """
    return json.dumps(build_contract_payload(), indent=2, sort_keys=True) + "\n"


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _join_backticked(values: Iterable[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def _render_settings_table(settings: list[dict[str, Any]]) -> str:
    rows = [
        "| Env Var | Field | Type | Required | Required When | Secret | "
        "Default |",
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


def _render_template_table(entries: list[dict[str, Any]]) -> str:
    rows = [
        "| Name | Source | Condition | Secret |",
        "| --- | --- | --- | --- |",
    ]
    rows.extend(
        (
            "| {name} | {source} | {condition} | {secret} |".format(
                name=_md_cell(entry["name"]),
                source=_md_cell(entry["source"]),
                condition=_md_cell(entry["condition"]),
                secret="yes" if entry["secret"] else "no",
            )
        )
        for entry in entries
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


def render_contract_markdown() -> str:
    """Render the generated operator-facing Markdown summary.

    Returns:
        str: Operator-facing Markdown summary for the runtime-config contract.

    Raises:
        None.
    """
    payload = build_contract_payload()
    service_env = payload["service_template"]["env"]
    service_secrets = payload["service_template"]["secrets"]
    worker_env = payload["worker_template"]["env"]
    worker_secrets = payload["worker_template"]["secrets"]
    env_json = payload["env_vars_json"]["supported_overrides"]

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
        "- `scripts/release/runtime_config_contract.py` "
        "(curated deploy/template metadata)",
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
        _render_env_json_table(env_json),
        "",
        "Forbidden ENV_VARS_JSON keys:",
        _join_backticked(payload["env_vars_json"]["forbidden_keys"]),
        "",
        "## Service template environment contract",
        "",
        _render_template_table(service_env + service_secrets),
        "",
        "Forbidden service env vars:",
        _join_backticked(payload["service_template"]["forbidden_env_vars"]),
        "",
        "Forbidden service parameters:",
        _join_backticked(payload["service_template"]["forbidden_parameters"]),
        "",
        "## Worker template environment contract",
        "",
        _render_template_table(worker_env + worker_secrets),
        "",
        "Worker command:",
        f"`{payload['worker_template']['command']}`",
        "",
        "Forbidden worker env vars:",
        _join_backticked(payload["worker_template"]["forbidden_env_vars"]),
        "",
        "Generated extra runtime env vars that are intentionally outside "
        "`Settings`:",
        _join_backticked(payload["extra_runtime_env_vars"]),
        "",
    ]
    return "\n".join(sections)
