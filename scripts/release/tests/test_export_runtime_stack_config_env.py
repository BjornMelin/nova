# mypy: disable-error-code=no-untyped-def

"""Tests for runtime stack config env export helper."""

from __future__ import annotations

import io

from scripts.release import export_runtime_stack_config_env


def test_main_emits_optional_enable_waf(monkeypatch) -> None:
    monkeypatch.setattr(
        export_runtime_stack_config_env,
        "parse_args",
        lambda: type("Args", (), {"parameter_name": "/nova/runtime/dev"})(),
    )
    monkeypatch.setattr(
        export_runtime_stack_config_env,
        "_load_config",
        lambda parameter_name: {
            "api_domain_name": "api.dev.example.com",
            "certificate_arn": (
                "arn:aws:acm:us-east-1:111111111111:certificate/example"
            ),
            "hosted_zone_id": "Z1234567890EXAMPLE",
            "hosted_zone_name": "example.com",
            "jwt_issuer": "https://issuer.example.com/",
            "jwt_audience": "api://nova",
            "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
            "allowed_origins": ["*"],
            "enable_waf": False,
            "environment": "dev",
        },
    )
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    result = export_runtime_stack_config_env.main()

    assert result == 0
    output = stdout.getvalue()
    assert "export ENABLE_WAF=False" in output
    assert "export STACK_ALLOWED_ORIGINS=" in output
