"""Flask integration helpers for canonical file transfer APIs/assets."""
# mypy: disable-error-code="untyped-decorator"

from __future__ import annotations

import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import validation_error
from nova_dash_bridge.http_adapter_core import (
    coerce_error_response,
    execute_operation,
)
from nova_dash_bridge.s3_client import SupportsCreateS3Client
from nova_dash_bridge.service import FileTransferService

LOGGER = logging.getLogger(__name__)
_CANONICAL_TRANSFERS_PREFIX = "/v1/transfers"


def _request_id() -> str | None:
    value = request.headers.get("X-Request-Id")
    return value if isinstance(value, str) else None


def create_file_transfer_blueprint(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Blueprint:
    """Create a Flask blueprint for canonical file transfer endpoints."""
    service = FileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )
    blueprint = Blueprint(
        "nova_dash_bridge_api",
        __name__,
        url_prefix=_CANONICAL_TRANSFERS_PREFIX,
    )

    def run_operation(operation_name: str) -> tuple[Any, int]:
        try:
            try:
                raw_payload = request.get_json(force=True, silent=False)
            except Exception as exc:
                raise validation_error(
                    "request body must be valid JSON"
                ) from exc
            response = execute_operation(
                service=service,
                operation_name=operation_name,
                raw_payload=raw_payload,
            )
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:  # noqa: BLE001
            status_code, content = coerce_error_response(
                exc=exc,
                request_id=_request_id(),
                logger=LOGGER,
                log_event="flask_file_transfer_request_failed",
            )
            return jsonify(content), status_code

    @blueprint.post("/uploads/initiate")
    def initiate_upload() -> tuple[Any, int]:
        return run_operation("initiate_upload")

    @blueprint.post("/uploads/sign-parts")
    def sign_parts() -> tuple[Any, int]:
        return run_operation("sign_parts")

    @blueprint.post("/uploads/complete")
    def complete_upload() -> tuple[Any, int]:
        return run_operation("complete_upload")

    @blueprint.post("/uploads/abort")
    def abort_upload() -> tuple[Any, int]:
        return run_operation("abort_upload")

    @blueprint.post("/downloads/presign")
    def presign_download() -> tuple[Any, int]:
        return run_operation("presign_download")

    return blueprint


def register_file_transfer_blueprint(
    flask_app: Flask,
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Blueprint:
    """Create and register the canonical file transfer API blueprint."""
    blueprint = create_file_transfer_blueprint(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )
    flask_app.register_blueprint(blueprint)
    return blueprint


def create_file_transfer_assets_blueprint(
    *,
    assets_url_prefix: str = "/_assets/nova_dash_bridge",
) -> Blueprint:
    """Create blueprint for packaged static uploader assets."""
    package_root = Path(__file__).resolve().parent
    static_folder = str(package_root / "assets")
    return Blueprint(
        "nova_dash_bridge_assets",
        __name__,
        static_folder=static_folder,
        static_url_path=assets_url_prefix,
    )


def register_file_transfer_assets(
    flask_app: Flask,
    *,
    assets_url_prefix: str = "/_assets/nova_dash_bridge",
) -> Blueprint:
    """Register static assets blueprint for uploader JavaScript/CSS."""
    blueprint = create_file_transfer_assets_blueprint(
        assets_url_prefix=assets_url_prefix
    )
    flask_app.register_blueprint(blueprint)
    LOGGER.info(
        "file_transfer.assets_registered",
        extra={"assets_url_prefix": assets_url_prefix},
    )
    return blueprint
