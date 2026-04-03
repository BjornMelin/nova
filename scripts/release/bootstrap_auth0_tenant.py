"""Bootstrap or reconcile the Nova Auth0 tenant resources for one overlay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

import yaml
from auth0.management import ManagementClient

from scripts.release.validate_auth0_contract import parse_env_file

_MANAGEMENT_API_SCOPES = [
    "read:clients",
    "create:clients",
    "update:clients",
    "delete:clients",
    "read:resource_servers",
    "create:resource_servers",
    "update:resource_servers",
    "delete:resource_servers",
    "read:tenant_settings",
    "update:tenant_settings",
    "read:client_grants",
    "create:client_grants",
    "update:client_grants",
    "delete:client_grants",
]
_REQUEST_OPTIONS: Any = {
    "max_retries": 3,
    "timeout_in_seconds": 20,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _dump_sdk_object(payload: Any) -> dict[str, Any]:
    """Normalize one SDK response object into a plain dictionary."""
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return cast(
            dict[str, Any],
            payload.model_dump(mode="python", exclude_none=True),
        )
    if hasattr(payload, "__dict__"):
        return {
            key: value
            for key, value in vars(payload).items()
            if not key.startswith("_")
        }
    raise TypeError(f"Unsupported SDK payload type: {type(payload)!r}")


def _render_template(
    mapping_path: Path,
    input_path: Path | None = None,
) -> dict[str, Any]:
    resolved_input_path = input_path or Path("infra/auth0/tenant/tenant.yaml")
    tenant_yaml_path = (
        resolved_input_path
        if resolved_input_path.is_absolute()
        else (_repo_root() / resolved_input_path).resolve()
    )
    tenant_yaml = tenant_yaml_path.read_text(encoding="utf-8")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    for key, value in mapping.items():
        tenant_yaml = tenant_yaml.replace(f"@@{key}@@", str(value))
    rendered = yaml.safe_load(tenant_yaml)
    if not isinstance(rendered, dict):
        raise TypeError("tenant template must render to a mapping")
    return cast(dict[str, Any], rendered)


def _find_by_name(
    items: list[dict[str, Any]],
    name: str,
) -> dict[str, Any] | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def _client_update_payload(client_payload: dict[str, Any]) -> dict[str, Any]:
    """Return a safe client PATCH payload for Auth0 Management API."""
    payload = {
        key: value for key, value in client_payload.items() if key != "app_type"
    }
    jwt_configuration = payload.get("jwt_configuration")
    if isinstance(jwt_configuration, dict):
        payload["jwt_configuration"] = {
            key: value
            for key, value in jwt_configuration.items()
            if key != "secret_encoded"
        }
    return payload


def _normalize_scopes(scopes: list[str]) -> list[str]:
    """Return a deterministic, duplicate-free scope list."""
    return sorted(set(scopes))


def _resource_server_write_payload(
    resource_server_payload: dict[str, Any],
) -> dict[str, Any]:
    """Return the shared create/update payload for one resource server."""
    return {
        "name": resource_server_payload.get("name"),
        "scopes": resource_server_payload.get("scopes"),
        "signing_alg": resource_server_payload.get("signing_alg"),
        "allow_offline_access": resource_server_payload.get(
            "allow_offline_access"
        ),
        "token_lifetime": resource_server_payload.get("token_lifetime"),
        "token_lifetime_for_web": resource_server_payload.get(
            "token_lifetime_for_web"
        ),
        "skip_consent_for_verifiable_first_party_clients": (
            resource_server_payload.get(
                "skip_consent_for_verifiable_first_party_clients"
            )
        ),
        "subject_type_authorization": resource_server_payload.get(
            "subject_type_authorization"
        ),
    }


def _client(
    *,
    domain: str,
    client_id: str,
    client_secret: str,
) -> ManagementClient:
    """Create one configured Auth0 management client."""
    return ManagementClient(
        domain=domain,
        client_id=client_id,
        client_secret=client_secret,
        timeout=20,
        client_info={"name": "nova-auth0-bootstrap", "version": "1.0.0"},
    )


def _ensure_client_grant(
    *,
    client: Any,
    existing_grants: list[dict[str, Any]],
    client_id: str,
    audience: str,
    scopes: list[str],
) -> dict[str, Any]:
    """Create or update one client grant to match the desired scope set."""
    desired_scopes = _normalize_scopes(scopes)
    existing = next(
        (
            grant
            for grant in existing_grants
            if grant.get("client_id") == client_id
            and grant.get("audience") == audience
        ),
        None,
    )
    if existing is None:
        created = _dump_sdk_object(
            client.client_grants.create(
                audience=audience,
                client_id=client_id,
                scope=desired_scopes,
                request_options=_REQUEST_OPTIONS,
            )
        )
        existing_grants.append(created)
        return created

    current_scopes = _normalize_scopes(existing.get("scope", []))
    if current_scopes == desired_scopes:
        return existing

    updated = _dump_sdk_object(
        client.client_grants.update(
            id=str(existing["id"]),
            scope=desired_scopes,
            request_options=_REQUEST_OPTIONS,
        )
    )
    existing.update(updated)
    return existing


def bootstrap_tenant(
    *,
    env_file: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Bootstrap or reconcile one Nova Auth0 tenant from local overlays.

    Args:
        env_file: Auth0 overlay env file with tenant credentials and mappings.
        report_path: Optional destination JSON report path.

    Returns:
        Structured report describing tenant, clients, and client grants.
    """
    env = parse_env_file(env_file)
    domain = env["AUTH0_DOMAIN"]
    client_id = env["AUTH0_CLIENT_ID"]
    client_secret = env["AUTH0_CLIENT_SECRET"]
    mapping_path = (_repo_root() / env["AUTH0_KEYWORD_MAPPINGS_FILE"]).resolve()
    input_file = env.get("AUTH0_INPUT_FILE")
    input_path = Path(input_file) if input_file else None
    rendered = _render_template(mapping_path, input_path=input_path)
    management_client = _client(
        domain=domain,
        client_id=client_id,
        client_secret=client_secret,
    )

    tenant_payload = rendered.get("tenant", {})
    if (
        "default_redirection_uri" in tenant_payload
        and not tenant_payload["default_redirection_uri"]
    ):
        tenant_payload = {
            key: value
            for key, value in tenant_payload.items()
            if key != "default_redirection_uri"
        }
    tenant_update_kwargs: dict[str, Any] = {
        "friendly_name": tenant_payload.get("friendly_name"),
        "support_email": tenant_payload.get("support_email"),
        "request_options": _REQUEST_OPTIONS,
    }
    if "default_redirection_uri" in tenant_payload:
        tenant_update_kwargs["default_redirection_uri"] = tenant_payload[
            "default_redirection_uri"
        ]
    tenant_result = _dump_sdk_object(
        management_client.tenants.settings.update(**tenant_update_kwargs)
    )

    existing_resource_servers = [
        _dump_sdk_object(item)
        for item in management_client.resource_servers.list(
            request_options=_REQUEST_OPTIONS
        )
    ]
    resource_server_payload = rendered["resourceServers"][0]
    resource_server_write_payload = _resource_server_write_payload(
        resource_server_payload
    )
    existing_resource_server = next(
        (
            server
            for server in existing_resource_servers
            if server.get("identifier") == resource_server_payload["identifier"]
        ),
        None,
    )
    if existing_resource_server is None:
        resource_server_result = _dump_sdk_object(
            management_client.resource_servers.create(
                identifier=str(resource_server_payload["identifier"]),
                **resource_server_write_payload,
                request_options=_REQUEST_OPTIONS,
            )
        )
    else:
        resource_server_result = _dump_sdk_object(
            management_client.resource_servers.update(
                id=str(existing_resource_server["id"]),
                **resource_server_write_payload,
                request_options=_REQUEST_OPTIONS,
            )
        )

    existing_clients = [
        _dump_sdk_object(item)
        for item in management_client.clients.list(
            request_options=_REQUEST_OPTIONS
        )
    ]
    client_results: list[dict[str, Any]] = []
    for client_payload in rendered["clients"]:
        existing_client = _find_by_name(
            existing_clients,
            str(client_payload["name"]),
        )
        if existing_client is None:
            client_result = _dump_sdk_object(
                management_client.clients.create(
                    name=str(client_payload["name"]),
                    description=client_payload.get("description"),
                    callbacks=client_payload.get("callbacks"),
                    allowed_logout_urls=client_payload.get(
                        "allowed_logout_urls"
                    ),
                    web_origins=client_payload.get("web_origins"),
                    allowed_origins=client_payload.get("allowed_origins"),
                    grant_types=client_payload.get("grant_types"),
                    app_type=client_payload.get("app_type"),
                    oidc_conformant=client_payload.get("oidc_conformant"),
                    jwt_configuration=client_payload.get("jwt_configuration"),
                    request_options=_REQUEST_OPTIONS,
                )
            )
        else:
            client_result = _dump_sdk_object(
                management_client.clients.update(
                    id=str(existing_client["client_id"]),
                    **_client_update_payload(client_payload),
                    request_options=_REQUEST_OPTIONS,
                )
            )
        client_results.append(client_result)

    tenant_ops_client_name = next(
        client["name"]
        for client in rendered["clients"]
        if client.get("app_type") == "non_interactive"
    )
    tenant_ops_client = next(
        client
        for client in client_results
        if client["name"] == tenant_ops_client_name
    )
    resource_server_identifier = str(resource_server_result["identifier"])
    resource_server_scopes = [
        str(scope["value"])
        for scope in resource_server_result.get("scopes", [])
        if isinstance(scope, dict) and "value" in scope
    ]
    existing_client_grants = [
        _dump_sdk_object(item)
        for item in management_client.client_grants.list(
            request_options=_REQUEST_OPTIONS
        )
    ]
    client_grant_results = [
        _ensure_client_grant(
            client=management_client,
            existing_grants=existing_client_grants,
            client_id=str(tenant_ops_client["client_id"]),
            audience=f"https://{domain}/api/v2/",
            scopes=_MANAGEMENT_API_SCOPES,
        ),
        _ensure_client_grant(
            client=management_client,
            existing_grants=existing_client_grants,
            client_id=str(tenant_ops_client["client_id"]),
            audience=resource_server_identifier,
            scopes=resource_server_scopes,
        ),
    ]

    report = {
        "tenant_domain": domain,
        "tenant": tenant_result,
        "resource_server": resource_server_result,
        "clients": client_results,
        "client_grants": client_grant_results,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    """Run the CLI entrypoint for Auth0 tenant bootstrap.

    Returns:
        Process exit code where 0 means success.
    """
    parser = argparse.ArgumentParser(
        description="Bootstrap Nova Auth0 resources for one tenant overlay."
    )
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()

    bootstrap_tenant(
        env_file=args.env_file.resolve(),
        report_path=args.report_path.resolve() if args.report_path else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
