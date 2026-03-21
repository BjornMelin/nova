"""Flask integration tests for the Dash bridge adapter."""

from __future__ import annotations

import nova_dash_bridge.flask_integration as flask_integration
from flask import Flask
from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_file_api.public import Principal


def _auth_policy() -> AuthPolicy:
    def resolve_principal(authorization_header: str | None) -> Principal:
        if authorization_header is None:
            raise ValueError("missing bearer token")
        return Principal(
            subject="user-1",
            scope_id="scope-1",
        )

    return AuthPolicy(principal_resolver=resolve_principal)


def test_create_file_transfer_blueprint_adds_bearer_challenge_on_401() -> None:
    app = Flask(__name__)
    flask_integration.register_file_transfer_blueprint(
        app,
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
    )

    with app.test_client() as client:
        response = client.post(
            "/v1/transfers/uploads/initiate",
            json={
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 1,
            },
        )

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "missing bearer token"
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def test_create_file_transfer_blueprint_rejects_cookie_only_auth() -> None:
    """File transfer routes should reject cookie-only authentication."""
    app = Flask(__name__)
    flask_integration.register_file_transfer_blueprint(
        app,
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
    )

    with app.test_client() as client:
        client.set_cookie("pca-nova-auth", "Bearer token-123")
        response = client.post(
            "/v1/transfers/uploads/initiate",
            json={
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 1,
            },
        )

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "missing bearer token"
