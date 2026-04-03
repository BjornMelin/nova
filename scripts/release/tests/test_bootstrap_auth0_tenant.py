"""Tests for bootstrap_auth0_tenant template rendering and reconciliation."""

from __future__ import annotations

from pathlib import Path

from scripts.release import bootstrap_auth0_tenant


def test_render_template_applies_mapping(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    tenant_dir = repo_root / "infra" / "auth0" / "tenant"
    mapping_dir = repo_root / "infra" / "auth0" / "mappings"
    tenant_dir.mkdir(parents=True)
    mapping_dir.mkdir(parents=True)
    (tenant_dir / "tenant.yaml").write_text(
        'tenant:\n  friendly_name: "Nova @@ENVIRONMENT_NAME@@"\n',
        encoding="utf-8",
    )
    mapping_path = mapping_dir / "dev.json"
    mapping_path.write_text(
        '{"ENVIRONMENT_NAME":"Development"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap_auth0_tenant, "_repo_root", lambda: repo_root)

    rendered = bootstrap_auth0_tenant._render_template(mapping_path)
    assert rendered["tenant"]["friendly_name"] == "Nova Development"


def test_ensure_client_grant_creates_when_missing() -> None:
    class _ClientGrants:
        def __init__(self) -> None:
            self.created: list[dict[str, object]] = []

        def create(self, **kwargs):
            self.created.append(kwargs)
            return {
                "id": "cg_123",
                "client_id": kwargs["client_id"],
                "audience": kwargs["audience"],
                "scope": kwargs["scope"],
            }

        def update(self, **kwargs):  # pragma: no cover - not used in this test
            raise AssertionError("update should not be called")

    client = type("Client", (), {"client_grants": _ClientGrants()})()
    existing_grants: list[dict[str, object]] = []

    result = bootstrap_auth0_tenant._ensure_client_grant(
        client=client,
        existing_grants=existing_grants,
        client_id="client_123",
        audience="https://api.example.com",
        scopes=["beta", "alpha", "beta"],
    )

    assert client.client_grants.created == [
        {
            "audience": "https://api.example.com",
            "client_id": "client_123",
            "scope": ["alpha", "beta"],
            "request_options": bootstrap_auth0_tenant._REQUEST_OPTIONS,
        }
    ]
    assert result["scope"] == ["alpha", "beta"]


def test_resource_server_write_payload_includes_web_token_lifetime() -> None:
    payload = bootstrap_auth0_tenant._resource_server_write_payload(
        {
            "name": "Nova API Development",
            "scopes": [{"value": "uploads:write"}],
            "signing_alg": "RS256",
            "allow_offline_access": True,
            "token_lifetime": 7200,
            "token_lifetime_for_web": 3600,
            "skip_consent_for_verifiable_first_party_clients": True,
            "subject_type_authorization": {"user_id": {"allow_any": False}},
        }
    )

    assert payload["token_lifetime_for_web"] == 3600


def test_bootstrap_tenant_reconciles_expected_resources(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
    rendered = {
        "tenant": {"friendly_name": "Nova Development"},
        "resourceServers": [
            {
                "name": "Nova API Development",
                "identifier": "https://nova-dev/api",
                "scopes": [{"value": "uploads:write"}],
                "signing_alg": "RS256",
            }
        ],
        "clients": [
            {"name": "nova-tenant-ops-dev", "app_type": "non_interactive"},
            {"name": "nova-web-dev", "app_type": "regular_web"},
        ],
    }
    monkeypatch.setattr(
        bootstrap_auth0_tenant,
        "_render_template",
        lambda path: rendered,
    )
    monkeypatch.setattr(
        bootstrap_auth0_tenant,
        "_repo_root",
        lambda: tmp_path,
    )

    class _TenantSettings:
        def update(self, **kwargs):
            return {"friendly_name": kwargs["friendly_name"]}

    class _Tenants:
        settings = _TenantSettings()

    class _ResourceServers:
        def list(self, **kwargs):
            return []

        def create(self, **kwargs):
            return {
                "id": "rs_123",
                "identifier": kwargs["identifier"],
                "name": kwargs["name"],
                "scopes": kwargs["scopes"],
            }

        def update(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("update should not be called")

    class _Clients:
        def list(self, **kwargs):
            return []

        def create(self, **kwargs):
            return {
                "name": kwargs["name"],
                "client_id": f"{kwargs['name']}-id",
                "app_type": kwargs["app_type"],
            }

        def update(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("update should not be called")

    class _ClientGrants:
        def __init__(self) -> None:
            self.created: list[dict[str, object]] = []

        def list(self, **kwargs):
            return []

        def create(self, **kwargs):
            self.created.append(kwargs)
            return {
                "id": f"grant-{len(self.created)}",
                "client_id": kwargs["client_id"],
                "audience": kwargs["audience"],
                "scope": kwargs["scope"],
            }

        def update(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("update should not be called")

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
        bootstrap_auth0_tenant,
        "_client",
        lambda **kwargs: fake_client,
    )

    report = bootstrap_auth0_tenant.bootstrap_tenant(
        env_file=env_file,
        report_path=tmp_path / "report.json",
    )

    assert report["tenant"]["friendly_name"] == "Nova Development"
    assert report["resource_server"]["identifier"] == "https://nova-dev/api"
    assert sorted(client["name"] for client in report["clients"]) == [
        "nova-tenant-ops-dev",
        "nova-web-dev",
    ]
    assert [grant["audience"] for grant in report["client_grants"]] == [
        "https://example.auth0.com/api/v2/",
        "https://nova-dev/api",
    ]


def test_bootstrap_updates_existing_resource_server_web_token_lifetime(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
    rendered = {
        "tenant": {"friendly_name": "Nova Development"},
        "resourceServers": [
            {
                "name": "Nova API Development",
                "identifier": "https://nova-dev/api",
                "scopes": [{"value": "uploads:write"}],
                "signing_alg": "RS256",
                "token_lifetime": 7200,
                "token_lifetime_for_web": 3600,
            }
        ],
        "clients": [
            {"name": "nova-tenant-ops-dev", "app_type": "non_interactive"},
            {"name": "nova-web-dev", "app_type": "regular_web"},
        ],
    }
    monkeypatch.setattr(
        bootstrap_auth0_tenant,
        "_render_template",
        lambda path: rendered,
    )
    monkeypatch.setattr(
        bootstrap_auth0_tenant,
        "_repo_root",
        lambda: tmp_path,
    )

    class _TenantSettings:
        def update(self, **kwargs):
            return {"friendly_name": kwargs["friendly_name"]}

    class _Tenants:
        settings = _TenantSettings()

    class _ResourceServers:
        def __init__(self) -> None:
            self.updated: list[dict[str, object]] = []

        def list(self, **kwargs):
            return [
                {
                    "id": "rs_existing",
                    "identifier": "https://nova-dev/api",
                    "name": "Nova API Development",
                    "scopes": [{"value": "uploads:write"}],
                }
            ]

        def create(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("create should not be called")

        def update(self, **kwargs):
            self.updated.append(kwargs)
            return {
                "id": kwargs["id"],
                "identifier": "https://nova-dev/api",
                "name": kwargs["name"],
                "scopes": kwargs["scopes"],
                "token_lifetime_for_web": kwargs["token_lifetime_for_web"],
            }

    class _Clients:
        def list(self, **kwargs):
            return [
                {"name": "nova-tenant-ops-dev", "client_id": "client_1"},
                {"name": "nova-web-dev", "client_id": "client_2"},
            ]

        def create(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("create should not be called")

        def update(self, **kwargs):
            return {
                "name": "nova-tenant-ops-dev"
                if kwargs["id"] == "client_1"
                else "nova-web-dev",
                "client_id": kwargs["id"],
            }

    class _ClientGrants:
        def list(self, **kwargs):
            return [
                {
                    "id": "grant-1",
                    "client_id": "client_1",
                    "audience": "https://example.auth0.com/api/v2/",
                    "scope": bootstrap_auth0_tenant._MANAGEMENT_API_SCOPES,
                },
                {
                    "id": "grant-2",
                    "client_id": "client_1",
                    "audience": "https://nova-dev/api",
                    "scope": ["uploads:write"],
                },
            ]

        def create(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("create should not be called")

        def update(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("update should not be called")

    resource_servers = _ResourceServers()
    fake_client = type(
        "ManagementClient",
        (),
        {
            "tenants": _Tenants(),
            "resource_servers": resource_servers,
            "clients": _Clients(),
            "client_grants": _ClientGrants(),
        },
    )()
    monkeypatch.setattr(
        bootstrap_auth0_tenant,
        "_client",
        lambda **kwargs: fake_client,
    )

    report = bootstrap_auth0_tenant.bootstrap_tenant(
        env_file=env_file,
        report_path=tmp_path / "report.json",
    )

    assert resource_servers.updated == [
        {
            "id": "rs_existing",
            "name": "Nova API Development",
            "scopes": [{"value": "uploads:write"}],
            "signing_alg": "RS256",
            "allow_offline_access": None,
            "token_lifetime": 7200,
            "token_lifetime_for_web": 3600,
            "skip_consent_for_verifiable_first_party_clients": None,
            "subject_type_authorization": None,
            "request_options": bootstrap_auth0_tenant._REQUEST_OPTIONS,
        }
    ]
    assert report["resource_server"]["token_lifetime_for_web"] == 3600
