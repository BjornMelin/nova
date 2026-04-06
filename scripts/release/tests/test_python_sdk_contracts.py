"""Contract checks for generated public Python SDK reference docs."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_SDK_ROOT = REPO_ROOT / "packages" / "nova_sdk_py" / "src" / "nova_sdk_py"


def _load_python_sdk_text(relative_path: str) -> str:
    return (PYTHON_SDK_ROOT / relative_path).read_text(encoding="utf-8")


def test_python_sdk_operation_docstrings_follow_openapi_summary() -> None:
    """Generated operation modules should expose spec-driven reference docs."""
    source = _load_python_sdk_text("api/transfers/initiate_upload.py")

    assert '"""' in source
    assert "Initiate a direct-to-S3 upload session" in source
    assert (
        "Resolve the effective transfer policy for the caller and return the"
        in source
    )
    assert "Args:" in source
    assert "client (AuthenticatedClient):" in source
    assert "Returns:" in source
    assert "Raises:" in source
    assert "Choose upload strategy and return presigned metadata." not in source


def test_python_sdk_model_docstrings_include_attribute_reference_sections() -> (
    None
):
    """Generated Python models should expose class-level attribute docs."""
    source = _load_python_sdk_text("models/export_resource.py")

    assert "Public export workflow resource." in source
    assert "Attributes:" in source
    assert (
        "export_id: Identifier of the caller-owned export workflow resource."
        in source
    )
    assert (
        "output: Completed output metadata when the export succeeds." in source
    )


def test_python_sdk_model_attributes_include_property_descriptions() -> None:
    """Generated attrs fields should retain per-attribute descriptions."""
    source = _load_python_sdk_text("models/initiate_upload_response.py")

    assert (
        '"""Suggested maximum number of concurrent client uploads."""' in source
    )
    assert (
        '"""Durable upload-session identifier used for resume flows."""'
        in source
    )
    assert (
        '"""Presigned single-part upload URL when the strategy is direct."""'
        in source
    )
