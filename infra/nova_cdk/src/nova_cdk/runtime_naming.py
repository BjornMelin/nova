"""Stable naming and tag authority for Nova runtime infrastructure."""

from __future__ import annotations

from .concurrency import is_production_environment

APPCONFIG_MANAGED_BY_TAG_KEY = "NovaManagedBy"
APPCONFIG_MANAGED_BY_TAG_VALUE = "nova-runtime-stack"
APPCONFIG_ENVIRONMENT_TAG_KEY = "NovaDeploymentEnvironment"
RESOURCE_OWNER_TAG_KEY = "Owner"
RESOURCE_OWNER_TAG_VALUE = "NOVA"
RESOURCE_ENVIRONMENT_TAG_KEY = "NovaDeploymentEnvironment"


def stage_name_for_environment(deployment_environment: str) -> str:
    """Normalize environment values into a stable API Gateway stage name."""
    if is_production_environment(deployment_environment):
        return "prod"
    return deployment_environment


def export_name_prefix(deployment_environment: str) -> str:
    """Return the environment-scoped CloudFormation export prefix."""
    if is_production_environment(deployment_environment):
        return "NovaProd"
    if deployment_environment == "dev":
        return "NovaDev"
    normalized = "".join(
        part.capitalize()
        for part in deployment_environment.replace("_", "-").split("-")
        if part
    )
    return f"Nova{normalized or 'Env'}"


def appconfig_resource_tags(
    deployment_environment: str,
) -> list[dict[str, str]]:
    """Return stable tags for runtime-managed AppConfig resources."""
    return [
        {
            "key": APPCONFIG_MANAGED_BY_TAG_KEY,
            "value": APPCONFIG_MANAGED_BY_TAG_VALUE,
        },
        {
            "key": APPCONFIG_ENVIRONMENT_TAG_KEY,
            "value": deployment_environment,
        },
    ]


def runtime_alarm_name(
    *,
    deployment_environment: str,
    suffix: str,
) -> str:
    """Return one stable CloudWatch alarm name."""
    return f"nova-{deployment_environment}-{suffix}"


def runtime_alarm_names(deployment_environment: str) -> dict[str, str]:
    """Return the CloudWatch alarm names used by the runtime stack."""
    return {
        "api_lambda_errors": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="api-lambda-errors",
        ),
        "api_lambda_throttles": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="api-lambda-throttles",
        ),
        "api_gateway_5xx": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="api-gateway-5xx",
        ),
        "api_latency": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="api-gateway-latency",
        ),
        "workflow_task_throttles": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="workflow-task-throttles",
        ),
        "export_workflow_failures": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="export-workflow-failures",
        ),
        "export_workflow_timeouts": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="export-workflow-timeouts",
        ),
        "exports_table_throttles": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="exports-table-throttles",
        ),
        "upload_sessions_table_throttles": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="upload-sessions-table-throttles",
        ),
        "transfer_usage_table_throttles": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="transfer-usage-table-throttles",
        ),
        "upload_sessions_stale": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="upload-sessions-stale",
        ),
        "export_copy_worker_dlq": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="export-copy-worker-dlq",
        ),
        "export_copy_worker_queue_age": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="export-copy-worker-queue-age",
        ),
        "stale_multipart_upload_bytes": runtime_alarm_name(
            deployment_environment=deployment_environment,
            suffix="stale-multipart-upload-bytes",
        ),
    }


def export_copy_worker_queue_name(deployment_environment: str) -> str:
    """Return the stable queued export-copy worker queue name."""
    return f"nova-export-copy-worker-{deployment_environment}"


def export_copy_worker_dlq_name(deployment_environment: str) -> str:
    """Return the stable queued export-copy worker DLQ name."""
    return f"nova-export-copy-worker-dlq-{deployment_environment}"


def observability_dashboard_name(deployment_environment: str) -> str:
    """Return the stable CloudWatch dashboard name."""
    return f"nova-runtime-observability-{deployment_environment}"


def transfer_spend_budget_name(deployment_environment: str) -> str:
    """Return the stable transfer budget name."""
    return f"nova-transfer-{deployment_environment}"
