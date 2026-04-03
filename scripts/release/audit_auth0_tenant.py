"""Audit one Nova Auth0 tenant against the repo template and local overlay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.release.bootstrap_auth0_tenant import (
    _REQUEST_OPTIONS,
    _client,
    _dump_sdk_object,
    _normalize_scopes,
    _render_template,
)
from scripts.release.validate_auth0_contract import parse_env_file


def _resource_server_scope_values(
    resource_server: dict[str, Any] | None,
) -> list[str]:
    """Return the normalized scope names for one resource server."""
    if resource_server is None:
        return []
    return _normalize_scopes(
        [
            str(scope["value"])
            for scope in resource_server.get("scopes", [])
            if isinstance(scope, dict) and "value" in scope
        ]
    )


def _client_grant_scopes(client_grant: dict[str, Any] | None) -> list[str]:
    """Return the normalized scopes for one client grant."""
    if client_grant is None:
        return []
    return _normalize_scopes(
        [str(scope) for scope in client_grant.get("scope", [])]
    )


def _build_checks(
    *,
    tenant_friendly_name: str | None,
    expected_tenant_friendly_name: str | None,
    matched_resource_server: dict[str, Any] | None,
    expected_resource_server: dict[str, Any],
    matched_clients: list[dict[str, Any]],
    expected_client_names: list[str],
    nova_api_grant: dict[str, Any] | None,
) -> dict[str, bool]:
    """Return the drift checks for one live Auth0 tenant."""
    expected_resource_server_scopes = _normalize_scopes(
        [
            str(scope["value"])
            for scope in expected_resource_server.get("scopes", [])
        ]
    )
    return {
        "tenant_friendly_name_matches": (
            tenant_friendly_name == expected_tenant_friendly_name
        ),
        "resource_server_present": matched_resource_server is not None,
        "resource_server_name_matches": (
            matched_resource_server is not None
            and matched_resource_server.get("name")
            == expected_resource_server["name"]
        ),
        "resource_server_scopes_match": (
            _resource_server_scope_values(matched_resource_server)
            == expected_resource_server_scopes
        ),
        "all_expected_clients_present": sorted(
            client.get("name") for client in matched_clients
        )
        == sorted(expected_client_names),
        "tenant_ops_nova_api_grant_present": nova_api_grant is not None,
        "tenant_ops_nova_api_grant_scopes_match": (
            _client_grant_scopes(nova_api_grant)
            == expected_resource_server_scopes
        ),
    }


def _summarize_checks(checks: dict[str, bool]) -> dict[str, Any]:
    """Return the ordered audit summary from evaluated checks."""
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "drift_detected": bool(failed_checks),
        "failed_checks": failed_checks,
    }


def audit_tenant(
    *,
    env_file: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Collect a reproducible tenant status report for one local overlay."""
    env = parse_env_file(env_file)
    mapping_path = (
        Path(__file__).resolve().parents[2] / env["AUTH0_KEYWORD_MAPPINGS_FILE"]
    ).resolve()
    rendered = _render_template(mapping_path)
    domain = env["AUTH0_DOMAIN"]
    management_client = _client(
        domain=domain,
        client_id=env["AUTH0_CLIENT_ID"],
        client_secret=env["AUTH0_CLIENT_SECRET"],
    )

    tenants = _dump_sdk_object(
        management_client.tenants.settings.get(request_options=_REQUEST_OPTIONS)
    )
    resource_servers = [
        _dump_sdk_object(item)
        for item in management_client.resource_servers.list(
            request_options=_REQUEST_OPTIONS
        )
    ]
    clients = [
        _dump_sdk_object(item)
        for item in management_client.clients.list(
            request_options=_REQUEST_OPTIONS
        )
    ]
    client_grants = [
        _dump_sdk_object(item)
        for item in management_client.client_grants.list(
            request_options=_REQUEST_OPTIONS
        )
    ]

    expected_resource_server = rendered["resourceServers"][0]
    expected_client_names = [client["name"] for client in rendered["clients"]]
    matched_resource_server = next(
        (
            server
            for server in resource_servers
            if server.get("identifier")
            == expected_resource_server["identifier"]
        ),
        None,
    )
    matched_clients = [
        client
        for client in clients
        if client.get("name") in expected_client_names
    ]
    expected_tenant_ops_name = next(
        client["name"]
        for client in rendered["clients"]
        if client.get("app_type") == "non_interactive"
    )
    tenant_ops_client_id = next(
        (
            str(client["client_id"])
            for client in matched_clients
            if client.get("name") == expected_tenant_ops_name
        ),
        None,
    )
    relevant_grants = [
        grant
        for grant in client_grants
        if grant.get("client_id") == tenant_ops_client_id
        and grant.get("audience") == expected_resource_server["identifier"]
    ]
    nova_api_grant = relevant_grants[0] if relevant_grants else None
    checks = _build_checks(
        tenant_friendly_name=tenants.get("friendly_name"),
        expected_tenant_friendly_name=rendered.get("tenant", {}).get(
            "friendly_name"
        ),
        matched_resource_server=matched_resource_server,
        expected_resource_server=expected_resource_server,
        matched_clients=matched_clients,
        expected_client_names=expected_client_names,
        nova_api_grant=nova_api_grant,
    )
    summary = _summarize_checks(checks)

    report = {
        "tenant_domain": domain,
        "tenant_friendly_name": tenants.get("friendly_name"),
        "expected": {
            "tenant_friendly_name": rendered.get("tenant", {}).get(
                "friendly_name"
            ),
            "resource_server_identifier": expected_resource_server[
                "identifier"
            ],
            "resource_server_name": expected_resource_server["name"],
            "resource_server_scopes": [
                scope["value"]
                for scope in expected_resource_server.get("scopes", [])
            ],
            "client_names": expected_client_names,
            "tenant_ops_client_name": expected_tenant_ops_name,
        },
        "actual": {
            "resource_server": matched_resource_server,
            "clients": matched_clients,
            "client_grants": relevant_grants,
        },
        "checks": checks,
        "summary": summary,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    """Run the CLI entrypoint for Auth0 tenant audit."""
    parser = argparse.ArgumentParser(
        description="Audit one Nova Auth0 tenant from a local overlay."
    )
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()

    report = audit_tenant(
        env_file=args.env_file.resolve(),
        report_path=args.report_path.resolve() if args.report_path else None,
    )
    return 1 if report["summary"]["drift_detected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
