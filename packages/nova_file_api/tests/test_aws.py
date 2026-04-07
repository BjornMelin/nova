from __future__ import annotations

from botocore.config import Config

from nova_file_api.aws import aws_client_config, s3_client_config


def test_aws_client_config_uses_explicit_timeout_and_retry_policy() -> None:
    config = aws_client_config()

    assert isinstance(config, Config)
    assert config.connect_timeout == 5
    assert config.read_timeout == 30
    assert config.retries == {
        "mode": "standard",
        "total_max_attempts": 3,
    }
    assert config.s3 is None


def test_s3_client_config_preserves_policy_with_acceleration() -> None:
    default_config = Config()
    standard_config = s3_client_config(use_accelerate_endpoint=False)
    accelerate_config = s3_client_config(use_accelerate_endpoint=True)

    assert standard_config.connect_timeout == 5
    assert standard_config.read_timeout == default_config.read_timeout
    assert standard_config.retries == {
        "mode": "standard",
        "total_max_attempts": 3,
    }
    assert standard_config.s3 == {"use_accelerate_endpoint": False}

    assert accelerate_config.connect_timeout == 5
    assert accelerate_config.read_timeout == default_config.read_timeout
    assert accelerate_config.retries == {
        "mode": "standard",
        "total_max_attempts": 3,
    }
    assert accelerate_config.s3 == {"use_accelerate_endpoint": True}
