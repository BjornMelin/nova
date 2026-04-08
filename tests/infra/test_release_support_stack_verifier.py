"""Contract tests for the release-support drift verifier."""

from __future__ import annotations

from argparse import Namespace

import pytest
from botocore.exceptions import ClientError

from .helpers import load_repo_module

verifier = load_repo_module(
    "scripts.release.verify_release_support_stack",
    "scripts/release/verify_release_support_stack.py",
)


def test_parse_args_reads_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_release_support_stack.py",
            "--account",
            "111111111111",
            "--dev-role-name",
            "nova-dev-cfn",
            "--hosted-zone-id",
            "Z1234567890EXAMPLE",
            "--prod-role-name",
            "nova-prod-cfn",
            "--region",
            "us-east-1",
            "--stack-name",
            "NovaReleaseSupportStack",
        ],
    )

    args = verifier.parse_args()

    assert args == Namespace(
        account="111111111111",
        dev_role_name="nova-dev-cfn",
        hosted_zone_id="Z1234567890EXAMPLE",
        prod_role_name="nova-prod-cfn",
        region="us-east-1",
        stack_name="NovaReleaseSupportStack",
    )


def test_deployed_template_decodes_yaml_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CloudFormationClient:
        def get_template(self, **kwargs: object) -> dict[str, str]:
            assert kwargs["StackName"] == "NovaReleaseSupportStack"
            return {
                "TemplateBody": "Resources:\n  Example:\n    Type: Test\n",
            }

    monkeypatch.setattr(
        verifier.boto3,
        "client",
        lambda service_name, region_name=None: _CloudFormationClient(),
    )

    args = Namespace(
        account="111111111111",
        dev_role_name="nova-dev-cfn",
        hosted_zone_id="Z1234567890EXAMPLE",
        prod_role_name="nova-prod-cfn",
        region="us-east-1",
        stack_name="NovaReleaseSupportStack",
    )

    assert verifier._deployed_template(args) == {
        "Resources": {
            "Example": {
                "Type": "Test",
            }
        }
    }


def test_diff_text_truncates_after_200_lines() -> None:
    expected = {f"k{i}": i for i in range(120)}
    actual = {f"a{i}": i for i in range(120)}

    diff_text = verifier._diff_text(expected=expected, actual=actual)

    assert "... diff truncated after 200 lines ..." in diff_text


def test_main_handles_drift_and_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(
        account="111111111111",
        dev_role_name="nova-dev-cfn",
        hosted_zone_id="Z1234567890EXAMPLE",
        prod_role_name="nova-prod-cfn",
        region="us-east-1",
        stack_name="NovaReleaseSupportStack",
    )
    monkeypatch.setattr(verifier, "parse_args", lambda: args)
    monkeypatch.setattr(
        verifier,
        "_expected_template",
        lambda parsed_args: {"version": 1, "stack": parsed_args.stack_name},
    )

    monkeypatch.setattr(
        verifier,
        "_deployed_template",
        lambda parsed_args: {"version": 1, "stack": parsed_args.stack_name},
    )
    assert verifier.main() == 0
    assert "matches the current repo template" in capsys.readouterr().out

    monkeypatch.setattr(
        verifier,
        "_deployed_template",
        lambda parsed_args: {"version": 2, "stack": parsed_args.stack_name},
    )
    assert verifier.main() == 1
    assert "drift detected" in capsys.readouterr().err


def test_main_handles_template_load_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(
        account="111111111111",
        dev_role_name="nova-dev-cfn",
        hosted_zone_id="Z1234567890EXAMPLE",
        prod_role_name="nova-prod-cfn",
        region="us-east-1",
        stack_name="NovaReleaseSupportStack",
    )
    monkeypatch.setattr(verifier, "parse_args", lambda: args)
    monkeypatch.setattr(
        verifier,
        "_expected_template",
        lambda parsed_args: {"version": 1, "stack": parsed_args.stack_name},
    )

    def _boom(parsed_args: Namespace) -> dict[str, object]:
        raise ClientError(
            {
                "Error": {
                    "Code": "ValidationError",
                    "Message": "stack not found",
                }
            },
            "GetTemplate",
        )

    monkeypatch.setattr(verifier, "_deployed_template", _boom)

    assert verifier.main() == 1
    assert (
        "Failed to load deployed release-support stack"
        in capsys.readouterr().err
    )
