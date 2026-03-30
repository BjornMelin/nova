from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release import build_api_lambda_asset as module


def test_build_asset_invokes_expected_uv_commands_and_installs_built_wheels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_dir = tmp_path / "asset"
    output_dir.mkdir(parents=True, exist_ok=True)
    pycache_dir = output_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "stale.pyc").write_bytes(b"cache")

    captured_commands: list[tuple[str, ...]] = []

    def _fake_run(*args: str) -> None:
        captured_commands.append(args)
        if args[:3] == ("uv", "build", "--package"):
            package_name = args[3]
            out_dir = Path(args[-1])
            wheel_path = out_dir / f"{package_name}-0.1.0-py3-none-any.whl"
            wheel_path.write_bytes(b"wheel")

    monkeypatch.setattr(module, "_run", _fake_run)

    module._build_asset(output_dir=output_dir)

    assert len(captured_commands) == 5
    assert captured_commands[0][:5] == (
        "uv",
        "export",
        "--frozen",
        "--package",
        "nova-file-api",
    )
    assert captured_commands[1][:3] == ("uv", "pip", "install")
    assert captured_commands[1][3] == "--target"
    assert captured_commands[1][4] == str(output_dir)
    assert captured_commands[2][:4] == (
        "uv",
        "build",
        "--package",
        "nova-runtime-support",
    )
    assert captured_commands[3][:4] == (
        "uv",
        "build",
        "--package",
        "nova-file-api",
    )

    final_install = captured_commands[4]
    assert final_install[:3] == ("uv", "pip", "install")
    assert "--no-deps" in final_install
    wheel_args = [value for value in final_install if value.endswith(".whl")]
    assert len(wheel_args) == 2
    assert wheel_args == sorted(wheel_args)
    assert "nova-file-api-0.1.0-py3-none-any.whl" in wheel_args[0]
    assert "nova-runtime-support-0.1.0-py3-none-any.whl" in wheel_args[1]
    assert not pycache_dir.exists()
