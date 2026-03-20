"""Frozen OpenAPI operation identifiers for the public file API contract."""

from typing import Final

METRICS_SUMMARY_OPERATION_ID: Final = "metrics_summary"
INITIATE_UPLOAD_OPERATION_ID: Final = "initiate_upload"
SIGN_UPLOAD_PARTS_OPERATION_ID: Final = "sign_upload_parts"
INTROSPECT_UPLOAD_OPERATION_ID: Final = "introspect_upload"
COMPLETE_UPLOAD_OPERATION_ID: Final = "complete_upload"
ABORT_UPLOAD_OPERATION_ID: Final = "abort_upload"
PRESIGN_DOWNLOAD_OPERATION_ID: Final = "presign_download"
CREATE_JOB_OPERATION_ID: Final = "create_job"
GET_JOB_STATUS_OPERATION_ID: Final = "get_job_status"
CANCEL_JOB_OPERATION_ID: Final = "cancel_job"
LIST_JOBS_OPERATION_ID: Final = "list_jobs"
RETRY_JOB_OPERATION_ID: Final = "retry_job"
LIST_JOB_EVENTS_OPERATION_ID: Final = "list_job_events"
GET_CAPABILITIES_OPERATION_ID: Final = "get_capabilities"
PLAN_RESOURCES_OPERATION_ID: Final = "plan_resources"
GET_RELEASE_INFO_OPERATION_ID: Final = "get_release_info"
HEALTH_LIVE_OPERATION_ID: Final = "health_live"
HEALTH_READY_OPERATION_ID: Final = "health_ready"

OPERATION_ID_BY_PATH_AND_METHOD = {
    "/metrics/summary": {"get": METRICS_SUMMARY_OPERATION_ID},
    "/v1/transfers/uploads/initiate": {"post": INITIATE_UPLOAD_OPERATION_ID},
    "/v1/transfers/uploads/sign-parts": {
        "post": SIGN_UPLOAD_PARTS_OPERATION_ID
    },
    "/v1/transfers/uploads/introspect": {
        "post": INTROSPECT_UPLOAD_OPERATION_ID
    },
    "/v1/transfers/uploads/complete": {"post": COMPLETE_UPLOAD_OPERATION_ID},
    "/v1/transfers/uploads/abort": {"post": ABORT_UPLOAD_OPERATION_ID},
    "/v1/transfers/downloads/presign": {"post": PRESIGN_DOWNLOAD_OPERATION_ID},
    "/v1/jobs": {
        "get": LIST_JOBS_OPERATION_ID,
        "post": CREATE_JOB_OPERATION_ID,
    },
    "/v1/jobs/{job_id}": {"get": GET_JOB_STATUS_OPERATION_ID},
    "/v1/jobs/{job_id}/cancel": {"post": CANCEL_JOB_OPERATION_ID},
    "/v1/jobs/{job_id}/retry": {"post": RETRY_JOB_OPERATION_ID},
    "/v1/jobs/{job_id}/events": {"get": LIST_JOB_EVENTS_OPERATION_ID},
    "/v1/capabilities": {"get": GET_CAPABILITIES_OPERATION_ID},
    "/v1/resources/plan": {"post": PLAN_RESOURCES_OPERATION_ID},
    "/v1/releases/info": {"get": GET_RELEASE_INFO_OPERATION_ID},
    "/v1/health/live": {"get": HEALTH_LIVE_OPERATION_ID},
    "/v1/health/ready": {"get": HEALTH_READY_OPERATION_ID},
}
