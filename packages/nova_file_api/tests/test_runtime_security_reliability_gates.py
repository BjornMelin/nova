from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

_SERVICE_DOCKERFILES = (
    REPO_ROOT / "apps" / "nova_file_api_service" / "Dockerfile",
    REPO_ROOT / "apps" / "nova_auth_api_service" / "Dockerfile",
)
_ASYNC_TEMPLATE = (
    REPO_ROOT / "infra" / "runtime" / "file_transfer" / "async.yml"
)


def test_service_dockerfiles_enforce_proxy_headers_and_single_process() -> None:
    for dockerfile in _SERVICE_DOCKERFILES:
        content = dockerfile.read_text(encoding="utf-8")

        assert '"uvicorn"' in content
        assert "--proxy-headers" in content
        assert "--forwarded-allow-ips=*" in content
        assert "--workers" not in content
        assert "gunicorn" not in content.lower()


def test_async_template_enforces_dlq_redrive_and_retention_safety() -> None:
    content = _ASYNC_TEMPLATE.read_text(encoding="utf-8")

    assert "JobsDeadLetterQueue:" in content
    assert "MessageRetentionPeriod: 1209600" in content
    assert "JobsMessageRetentionSeconds:" in content
    assert "MaxValue: 1209599" in content

    assert "RedrivePolicy:" in content
    assert "deadLetterTargetArn: !GetAtt JobsDeadLetterQueue.Arn" in content
    assert "maxReceiveCount: !Ref JobsMaxReceiveCount" in content
