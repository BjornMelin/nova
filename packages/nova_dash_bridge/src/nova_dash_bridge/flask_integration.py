"""Flask integration helpers for file transfer APIs/assets."""
# mypy: disable-error-code="untyped-decorator"

from __future__ import annotations

import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any

from flask import Blueprint, Flask, jsonify, request
from pydantic import ValidationError

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import FileTransferError, validation_error
from nova_dash_bridge.s3_client import SupportsCreateS3Client
from nova_dash_bridge.service import (
    FileTransferService,
    coerce_file_transfer_error,
)
from nova_file_api.public import (
    AbortUploadRequest,
    CompleteUploadRequest,
    InitiateUploadRequest,
    PresignDownloadRequest,
    SignPartsRequest,
    UploadIntrospectionRequest,
)
from nova_runtime_support.http import canonical_error_content

LOGGER = logging.getLogger(__name__)
FlaskResponse = tuple[Any, int] | tuple[Any, int, dict[str, str]]


def _request_id() -> str | None:
    value = request.headers.get("X-Request-Id")
    return value if isinstance(value, str) else None


def _authorization_header() -> str | None:
    value = request.headers.get("Authorization")
    return value if isinstance(value, str) else None


def _error_headers(exc: FileTransferError) -> dict[str, str]:
    headers = dict(getattr(exc, "headers", {}))
    if int(exc.status_code) == 401 and "WWW-Authenticate" not in headers:
        headers["WWW-Authenticate"] = (
            'Bearer error="invalid_token", '
            'error_description="missing bearer token"'
        )
    return headers


def _error_response(exc: FileTransferError) -> tuple[Any, int, dict[str, str]]:
    payload = canonical_error_content(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        request_id=_request_id(),
    )
    return (
        jsonify(payload),
        int(exc.status_code),
        _error_headers(exc),
    )


def _parse_payload(model: type[Any]) -> Any:
    try:
        incoming = request.get_json(force=True, silent=False)
        if incoming is None:
            raise validation_error("request body must not be null")
        return model.model_validate(incoming)
    except ValidationError as exc:
        raise validation_error(
            "invalid request payload", details={"errors": exc.errors()}
        ) from exc
    except Exception as exc:
        raise validation_error("request body must be valid JSON") from exc


def create_file_transfer_blueprint(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy,
    s3_client_factory: SupportsCreateS3Client | None = None,
    url_prefix: str = "/v1/transfers",
) -> Blueprint:
    """Create a Flask blueprint for file transfer endpoints."""
    service = FileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )
    blueprint = Blueprint(
        "nova_dash_bridge_api",
        __name__,
        url_prefix=url_prefix,
    )

    def _principal() -> Any:
        return service.resolve_principal(_authorization_header())

    @blueprint.post("/uploads/initiate")
    def initiate_upload() -> FlaskResponse:
        try:
            payload = _parse_payload(InitiateUploadRequest)
            response = service.initiate_upload(payload, principal=_principal())
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:
            err = coerce_file_transfer_error(exc)
            return _error_response(err)

    @blueprint.post("/uploads/sign-parts")
    def sign_parts() -> FlaskResponse:
        try:
            payload = _parse_payload(SignPartsRequest)
            response = service.sign_parts(payload, principal=_principal())
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:
            err = coerce_file_transfer_error(exc)
            return _error_response(err)

    @blueprint.post("/uploads/introspect")
    def introspect_upload() -> FlaskResponse:
        try:
            payload = _parse_payload(UploadIntrospectionRequest)
            response = service.introspect_upload(
                payload,
                principal=_principal(),
            )
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:
            err = coerce_file_transfer_error(exc)
            return _error_response(err)

    @blueprint.post("/uploads/complete")
    def complete_upload() -> FlaskResponse:
        try:
            payload = _parse_payload(CompleteUploadRequest)
            response = service.complete_upload(payload, principal=_principal())
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:
            err = coerce_file_transfer_error(exc)
            return _error_response(err)

    @blueprint.post("/uploads/abort")
    def abort_upload() -> FlaskResponse:
        try:
            payload = _parse_payload(AbortUploadRequest)
            response = service.abort_upload(payload, principal=_principal())
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:
            err = coerce_file_transfer_error(exc)
            return _error_response(err)

    @blueprint.post("/downloads/presign")
    def presign_download() -> FlaskResponse:
        try:
            payload = _parse_payload(PresignDownloadRequest)
            response = service.presign_download(payload, principal=_principal())
            return jsonify(response.model_dump()), HTTPStatus.OK
        except Exception as exc:
            err = coerce_file_transfer_error(exc)
            return _error_response(err)

    return blueprint


def register_file_transfer_blueprint(
    flask_app: Flask,
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy,
    s3_client_factory: SupportsCreateS3Client | None = None,
    url_prefix: str = "/v1/transfers",
) -> Blueprint:
    """Create and register file transfer API blueprint."""
    blueprint = create_file_transfer_blueprint(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
        url_prefix=url_prefix,
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
