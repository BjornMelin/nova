"""Generated OpenAPI client smoke tests."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import httpx
import pytest

_SUBPROCESS_TIMEOUT_SECONDS = 30
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPENAPI_ROOT = _REPO_ROOT / "packages" / "contracts" / "openapi"
_PYTHON_SDK_SRC = _REPO_ROOT / "packages" / "nova_sdk_py_file" / "src"

if str(_PYTHON_SDK_SRC) not in sys.path:
    sys.path.insert(0, str(_PYTHON_SDK_SRC))

_client_module = import_module("nova_sdk_py_file.client")
_errors_module = import_module("nova_sdk_py_file.errors")
_models_module = import_module("nova_sdk_py_file.models")
_release_info_module = import_module(
    "nova_sdk_py_file.api.platform.get_release_info"
)

AuthenticatedClient = _client_module.AuthenticatedClient
Client = _client_module.Client
UnexpectedStatus = _errors_module.UnexpectedStatus


def _generate_client_smoke(*, schema_path: Path, tmp_path: Path) -> None:
    if importlib.util.find_spec("openapi_python_client") is None:
        pytest.skip("openapi_python_client dependency is not installed")

    output_path = tmp_path / schema_path.stem

    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "openapi_python_client",
                "generate",
                "--path",
                str(schema_path),
                "--meta",
                "none",
                "--output-path",
                str(output_path),
                "--overwrite",
            ],
            check=False,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "openapi client generation timed out after "
            f"{_SUBPROCESS_TIMEOUT_SECONDS}s: {exc}"
        )
    assert generate.returncode == 0, (
        "openapi client generation failed:\n"
        f"stdout:\n{generate.stdout}\n"
        f"stderr:\n{generate.stderr}"
    )

    init_files = list(output_path.rglob("__init__.py"))
    assert init_files, "generated client package is missing __init__.py files"

    try:
        compile_result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(output_path)],
            check=False,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "generated client compile smoke timed out after "
            f"{_SUBPROCESS_TIMEOUT_SECONDS}s: {exc}"
        )
    assert compile_result.returncode == 0, (
        "generated client compile smoke failed:\n"
        f"stdout:\n{compile_result.stdout}\n"
        f"stderr:\n{compile_result.stderr}"
    )


def test_file_openapi_generated_client_smoke(tmp_path: Path) -> None:
    """Generate a Python client from the canonical file API OpenAPI artifact."""
    _generate_client_smoke(
        schema_path=_OPENAPI_ROOT / "nova-file-api.openapi.json",
        tmp_path=tmp_path,
    )


def test_generated_client_builder_helpers_are_immutable() -> None:
    """Client builder helpers should return a new configuration."""
    client = Client(base_url="https://nova.example.com")

    materialized = client.get_httpx_client()
    updated = (
        client.with_headers({"X-Test": "1"})
        .with_cookies({"c": "v"})
        .with_timeout(httpx.Timeout(5.0))
    )

    assert updated is not client
    assert "X-Test" not in client._headers
    assert "X-Test" in updated._headers
    assert "c" not in client._cookies
    assert updated._cookies["c"] == "v"
    assert client._timeout is None
    assert updated._timeout == httpx.Timeout(5.0)
    assert client._client is materialized
    assert updated._client is None


def test_authenticated_client_does_not_mutate_headers_when_materialized() -> (
    None
):
    """Auth header injection must not leak into stored header defaults."""
    client = AuthenticatedClient(
        base_url="https://nova.example.com",
        token="secret-token",
        headers={"X-Test": "1"},
    )

    httpx_client = client.get_httpx_client()

    assert client.auth_header_name not in client._headers
    assert (
        httpx_client.headers[client.auth_header_name] == "Bearer secret-token"
    )
    assert httpx_client.headers["X-Test"] == "1"


def test_unexpected_status_message_excludes_response_body() -> None:
    """UnexpectedStatus stringification should not leak response content."""
    error = UnexpectedStatus(status_code=418, content=b"very secret body")

    assert str(error) == "Unexpected status code: 418"
    assert "very secret body" not in str(error)


def test_generated_wrappers_preserve_raw_unexpected_status_codes() -> None:
    """Generated wrappers should preserve non-IANA status codes."""
    response = httpx.Response(
        status_code=499,
        content=b"gateway aborted request",
        request=httpx.Request(
            "GET", "https://nova.example.com/v1/releases/info"
        ),
    )

    detailed = _release_info_module._build_response(
        client=Client(
            base_url="https://nova.example.com",
            raise_on_unexpected_status=False,
        ),
        response=response,
    )

    assert detailed.status_code == 499
    assert isinstance(detailed.status_code, int)
    assert detailed.parsed is None


def test_generated_wrappers_raise_unexpected_status_for_raw_codes() -> None:
    """Unexpected non-IANA codes should raise the documented SDK error."""
    response = httpx.Response(
        status_code=499,
        content=b"gateway aborted request",
        request=httpx.Request(
            "GET", "https://nova.example.com/v1/releases/info"
        ),
    )

    with pytest.raises(UnexpectedStatus, match="Unexpected status code: 499"):
        _release_info_module._build_response(
            client=Client(
                base_url="https://nova.example.com",
                raise_on_unexpected_status=True,
            ),
            response=response,
        )


def test_python_sdk_exports_the_canonical_export_output_model() -> None:
    """The committed SDK should expose the explicit export output shape."""
    assert hasattr(_models_module, "ExportOutput")
    assert not any(name.startswith("Enqueue") for name in dir(_models_module))
