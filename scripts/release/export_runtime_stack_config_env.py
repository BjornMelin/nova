#!/usr/bin/env python3
"""Emit shell exports for one runtime stack config document in SSM."""

from __future__ import annotations

import argparse
import json
import shlex
from typing import Any

import boto3

REQUIRED_KEYS = {
    "api_domain_name": "API_DOMAIN_NAME",
    "certificate_arn": "CERTIFICATE_ARN",
    "hosted_zone_id": "HOSTED_ZONE_ID",
    "hosted_zone_name": "HOSTED_ZONE_NAME",
    "jwt_issuer": "JWT_ISSUER",
    "jwt_audience": "JWT_AUDIENCE",
    "jwt_jwks_url": "JWT_JWKS_URL",
}
OPTIONAL_KEYS = {
    "allowed_origins": "STACK_ALLOWED_ORIGINS",
    "environment": "ENVIRONMENT",
}


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameter-name", required=True)
    return parser.parse_args()


def _load_config(parameter_name: str) -> dict[str, Any]:
    client = boto3.client("ssm")
    response = client.get_parameter(Name=parameter_name)
    raw_value = response["Parameter"]["Value"]
    payload = json.loads(raw_value)
    if not isinstance(payload, dict):
        raise TypeError(
            "runtime stack config parameter must decode to an object"
        )
    return payload


def main() -> int:
    """Load the runtime config document and print shell exports."""
    args = parse_args()
    payload = _load_config(args.parameter_name)

    for key in REQUIRED_KEYS:
        value = str(payload.get(key, "")).strip()
        if not value:
            raise ValueError(
                f"runtime stack config missing required key: {key}"
            )

    exports: dict[str, str] = {}
    for key, env_name in REQUIRED_KEYS.items():
        exports[env_name] = str(payload[key]).strip()
    for key, env_name in OPTIONAL_KEYS.items():
        exports[env_name] = str(payload.get(key, "")).strip()

    for env_name, value in sorted(exports.items()):
        print(f"export {env_name}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
