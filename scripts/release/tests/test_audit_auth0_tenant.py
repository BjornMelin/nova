"""Tests for Auth0 tenant audit reporting."""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.release import audit_auth0_tenant


def _write_env_file(tmp_path: Path) -> Path:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "AUTH0_DOMAIN=example.auth0.com",
                "AUTH0_CLIENT_ID=client_id",
                "AUTH0_CLIENT_SECRET=client_secret",
                "AUTH0_ALLOW_DELETE=false",
                'AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients","clientGrants"]',
                "AUTH0_INPUT_FILE=infra/auth0/tenant/tenant.yaml",
                "AUTH0_KEYWORD_MAPPINGS_FILE=infra/auth0/mappings/dev.json",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return env_file


def _rendered_tenant() -> dict[str, object]:
    return {
        "tenant": {"friendly_name": "Nova Development"},
        "resourceServers": [
            {
                "name": "Nova API Development",
                "identifier": "https://nova-dev/api",
                "scopes": [{"value": "uploads:write"}],
            }
        ],
        "clients": [
            {"name": "nova-tenant-ops-dev", "app_type": "non_interactive"},
            {"name": "nova-web-dev", "app_type": "regular_web"},
        ],
    }


def _install_fake_management_client(
    monkeypatch,
    *,
    nova_api_grant: dict[str, object] | None,
    tenant_friendly_name: str = "Nova Development",
    resource_server_name: str = "Nova API Development",
) -> None:
    rendered = _rendered_tenant()

    monkeypatch.setattr(
        audit_auth0_tenant,
        "_render_template",
        lambda path: rendered,
    )

    class _TenantSettings:
        def get(self, **kwargs):
            return {"friendly_name": tenant_friendly_name}

    class _Tenants:
        settings = _TenantSettings()

    class _ResourceServers:
        def list(self, **kwargs):
            return [
                {
                    "name": resource_server_name,
                    "identifier": "https://nova-dev/api",
                    "scopes": [{"value": "uploads:write"}],
                }
            ]

    class _Clients:
        def list(self, **kwargs):
            return [
                {"name": "nova-tenant-ops-dev", "client_id": "client_1"},
                {"name": "nova-web-dev", "client_id": "client_2"},
            ]

    class _ClientGrants:
        def list(self, **kwargs):
            management_api_grant = {
                "client_id": "client_1",
                "audience": "https://example.auth0.com/api/v2/",
                "scope": ["read:clients"],
            }
            grants = [management_api_grant]
            if nova_api_grant is not None:
                grants.append(nova_api_grant)
            return grants

    fake_client = type(
        "ManagementClient",
        (),
        {
            "tenants": _Tenants(),
            "resource_servers": _ResourceServers(),
            "clients": _Clients(),
            "client_grants": _ClientGrants(),
        },
    )()
    monkeypatch.setattr(
        audit_auth0_tenant,
        "_client",
        lambda **kwargs: fake_client,
    )


def test_audit_tenant_writes_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = _write_env_file(tmp_path)
    _install_fake_management_client(
        monkeypatch,
        nova_api_grant={
            "client_id": "client_1",
            "audience": "https://nova-dev/api",
            "scope": ["uploads:write"],
        },
    )

    report = audit_auth0_tenant.audit_tenant(
        env_file=env_file,
        report_path=tmp_path / "report.json",
    )

    assert report["checks"]["tenant_friendly_name_matches"] is True
    assert report["checks"]["resource_server_present"] is True
    assert report["checks"]["resource_server_name_matches"] is True
    assert report["checks"]["resource_server_scopes_match"] is True
    assert report["checks"]["all_expected_clients_present"] is True
    assert report["checks"]["tenant_ops_nova_api_grant_present"] is True
    assert report["checks"]["tenant_ops_nova_api_grant_scopes_match"] is True
    assert report["summary"] == {
        "drift_detected": False,
        "failed_checks": [],
    }


def test_audit_tenant_rejects_management_api_only_grant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = _write_env_file(tmp_path)
    _install_fake_management_client(monkeypatch, nova_api_grant=None)

    report = audit_auth0_tenant.audit_tenant(
        env_file=env_file,
        report_path=tmp_path / "report.json",
    )

    assert report["checks"]["tenant_ops_nova_api_grant_present"] is False
    assert report["checks"]["tenant_ops_nova_api_grant_scopes_match"] is False
    assert report["summary"]["drift_detected"] is True
    assert report["summary"]["failed_checks"] == [
        "tenant_ops_nova_api_grant_present",
        "tenant_ops_nova_api_grant_scopes_match",
    ]


def test_main_returns_nonzero_when_audit_detects_drift(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = _write_env_file(tmp_path)
    _install_fake_management_client(
        monkeypatch,
        nova_api_grant={
            "client_id": "client_1",
            "audience": "https://nova-dev/api",
            "scope": ["uploads:write"],
        },
        tenant_friendly_name="Drifted Tenant",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_auth0_tenant.py",
            "--env-file",
            str(env_file),
            "--report-path",
            str(tmp_path / "report.json"),
        ],
    )

    assert audit_auth0_tenant.main() == 1
