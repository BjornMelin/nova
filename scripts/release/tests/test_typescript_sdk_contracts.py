"""Contract checks for public TypeScript SDK package manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_package_json(package_dir_name: str) -> dict[str, object]:
    package_path = REPO_ROOT / "packages" / package_dir_name / "package.json"
    return cast(
        dict[str, object],
        json.loads(package_path.read_text(encoding="utf-8")),
    )


def _load_source_text(package_dir_name: str, file_name: str) -> str:
    source_path = REPO_ROOT / "packages" / package_dir_name / "src" / file_name
    return source_path.read_text(encoding="utf-8")


def test_public_sdk_packages_use_subpath_only_exports() -> None:
    """Public TS SDK packages must expose explicit subpaths only."""
    for package_dir_name in ("nova_sdk_auth", "nova_sdk_file"):
        package_data = _load_package_json(package_dir_name)
        exports = package_data.get("exports")
        assert isinstance(exports, dict)
        assert "." not in exports
        assert set(exports) == {
            "./client",
            "./errors",
            "./operations",
            "./types",
        }


def test_public_sdk_packages_remain_validation_free() -> None:
    """Public TS SDK packages must not bundle Zod or validator dependencies."""
    for package_dir_name in ("nova_sdk_auth", "nova_sdk_file"):
        package_data = _load_package_json(package_dir_name)
        dependencies = package_data.get("dependencies", {})
        assert isinstance(dependencies, dict)
        assert "zod" not in dependencies
        assert "@nova/sdk-fetch" in dependencies


def test_public_sdk_types_omit_raw_model_aliases() -> None:
    """Public TS SDK types must not expose raw OpenAPI-wide aliases."""
    banned_exports = (
        "export type Components =",
        "export type Paths =",
        "export type Operations =",
        "export type OperationId =",
    )

    for package_dir_name in ("nova_sdk_auth", "nova_sdk_file"):
        source = _load_source_text(package_dir_name, "types.ts")
        for banned_export in banned_exports:
            assert banned_export not in source


def test_public_sdk_types_exclude_internal_job_result_aliases() -> None:
    """Public file SDK types must exclude worker-only job result aliases."""
    source = _load_source_text("nova_sdk_file", "types.ts")
    assert "export type JobResultUpdateRequest" not in source
    assert "export type JobResultUpdateResponse" not in source
