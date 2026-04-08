#!/usr/bin/env python3
"""Fail closed when the deployed release-support stack drifts from source."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

import boto3
import yaml
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "infra" / "nova_cdk" / "src"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", required=True)
    parser.add_argument("--dev-role-name", required=True)
    parser.add_argument("--hosted-zone-id", required=True)
    parser.add_argument("--prod-role-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--stack-name", required=True)
    return parser.parse_args()


def _load_release_support_stack_class() -> type[Any]:
    """Import the release-support stack class from the repo package."""
    package_root_text = str(PACKAGE_ROOT)
    if package_root_text not in sys.path:
        sys.path.insert(0, package_root_text)
    from nova_cdk.release_support_stack import NovaReleaseSupportStack

    return NovaReleaseSupportStack


def _expected_template(args: argparse.Namespace) -> dict[str, Any]:
    """Return the synthesized support-stack template for the current repo."""
    stack_cls = _load_release_support_stack_class()
    app = App(
        context={
            "dev_runtime_cfn_execution_role_name": args.dev_role_name,
            "hosted_zone_id": args.hosted_zone_id,
            "prod_runtime_cfn_execution_role_name": args.prod_role_name,
        }
    )
    stack = stack_cls(
        app,
        args.stack_name,
        env=Environment(account=args.account, region=args.region),
    )
    return dict(Template.from_stack(stack).to_json())


def _deployed_template(args: argparse.Namespace) -> dict[str, Any]:
    """Load the current support-stack template from CloudFormation."""
    client = boto3.client("cloudformation", region_name=args.region)
    response = client.get_template(
        StackName=args.stack_name,
        TemplateStage="Original",
    )
    body = response["TemplateBody"]
    payload = yaml.safe_load(body) if isinstance(body, str) else body
    if not isinstance(payload, dict):
        raise TypeError(
            "deployed support-stack template did not decode to an object"
        )
    return payload


def _diff_text(expected: dict[str, Any], actual: dict[str, Any]) -> str:
    """Return a bounded unified diff for two template dictionaries."""
    expected_lines = json.dumps(expected, indent=2, sort_keys=True).splitlines()
    actual_lines = json.dumps(actual, indent=2, sort_keys=True).splitlines()
    diff_lines = list(
        difflib.unified_diff(
            actual_lines,
            expected_lines,
            fromfile="deployed/NovaReleaseSupportStack",
            tofile="repo/NovaReleaseSupportStack",
            lineterm="",
        )
    )
    if len(diff_lines) <= 200:
        return "\n".join(diff_lines)
    return "\n".join(
        [
            *diff_lines[:200],
            "... diff truncated after 200 lines ...",
        ]
    )


def main() -> int:
    """Compare the deployed support-stack template to the current source."""
    args = parse_args()
    expected = _expected_template(args)
    actual = _deployed_template(args)
    if actual == expected:
        print(
            "Release-support stack matches the current repo template:",
            args.stack_name,
        )
        return 0

    print(
        "Release-support stack drift detected. Redeploy the support stack "
        "before continuing the release.",
        file=sys.stderr,
    )
    print(
        _diff_text(expected=expected, actual=actual),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
