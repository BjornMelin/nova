"""Contract checks for public TypeScript SDK package manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[3]
TS_PACKAGE_DIR = "nova_sdk_ts"
ROOT_PACKAGE_JSON = REPO_ROOT / "package.json"
ROOT_PACKAGE_LOCK = REPO_ROOT / "package-lock.json"


def _load_package_json(package_dir_name: str) -> dict[str, object]:
    package_path = REPO_ROOT / "packages" / package_dir_name / "package.json"
    return cast(
        dict[str, object],
        json.loads(package_path.read_text(encoding="utf-8")),
    )


def _load_root_package_json() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(ROOT_PACKAGE_JSON.read_text(encoding="utf-8")),
    )


def _load_package_lock() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(ROOT_PACKAGE_LOCK.read_text(encoding="utf-8")),
    )


def _load_source_text(package_dir_name: str, file_name: str) -> str:
    source_path = REPO_ROOT / "packages" / package_dir_name / "src" / file_name
    return source_path.read_text(encoding="utf-8")


def test_public_sdk_packages_use_subpath_only_exports() -> None:
    """Public TS SDK packages must expose explicit subpaths only."""
    package_data = _load_package_json(TS_PACKAGE_DIR)
    assert package_data.get("name") == "@nova/sdk"
    assert "main" not in package_data
    assert "module" not in package_data
    assert "types" not in package_data
    exports = package_data.get("exports")
    assert isinstance(exports, dict)
    assert "." not in exports
    assert set(exports) == {"./client", "./sdk", "./types"}


def test_typescript_sdk_source_manifests_remain_private() -> None:
    """Source TS SDK manifests stay private until staged publish preparation."""
    package_data = _load_package_json(TS_PACKAGE_DIR)
    assert package_data.get("private") is True


def test_typescript_workspace_keeps_generator_and_compiler_contract() -> None:
    """The npm workspace should advance the generator but keep TS 5.9.3."""
    root_package = _load_root_package_json()
    root_dev_dependencies = cast(
        dict[str, str],
        root_package.get("devDependencies", {}),
    )
    sdk_package = _load_package_json(TS_PACKAGE_DIR)
    contracts_package = _load_package_json("contracts/typescript")

    assert root_dev_dependencies["@hey-api/openapi-ts"] == "0.95.0"
    assert (
        cast(dict[str, str], sdk_package["devDependencies"])["typescript"]
        == "5.9.3"
    )
    assert (
        cast(dict[str, str], contracts_package["devDependencies"])["typescript"]
        == "5.9.3"
    )
    assert (
        cast(dict[str, str], sdk_package["devDependencies"])["@types/node"]
        == "24.12.2"
    )
    assert (
        cast(dict[str, str], contracts_package["devDependencies"])[
            "@types/node"
        ]
        == "24.12.2"
    )


def test_package_lock_keeps_single_typescript_5_line() -> None:
    """The lockfile must not retain the deferred TypeScript 6 nested install."""
    package_lock = _load_package_lock()
    packages = cast(dict[str, object], package_lock.get("packages", {}))
    root_typescript = cast(
        dict[str, object], packages["node_modules/typescript"]
    )

    assert root_typescript["version"] == "5.9.3"
    assert "packages/nova_sdk_ts/node_modules/typescript" not in packages


def test_public_sdk_package_is_runtime_lean() -> None:
    """Public TS SDK package must stay free of the deleted runtime stack."""
    package_data = _load_package_json(TS_PACKAGE_DIR)
    dependencies = package_data.get("dependencies", {})
    assert isinstance(dependencies, dict)
    dependency_map = cast(dict[str, object], dependencies)
    assert "zod" not in dependency_map
    assert "@nova/sdk-fetch" not in dependency_map
    assert "openapi-fetch" not in dependency_map
    assert "@hey-api/client-fetch" not in dependency_map


def test_public_sdk_types_omit_raw_model_aliases() -> None:
    """Public TS SDK types must not expose raw OpenAPI-wide aliases."""
    banned_exports = (
        "export type Components =",
        "export type Paths =",
        "export type Operations =",
        "export type OperationId =",
    )

    source = _load_source_text(TS_PACKAGE_DIR, "client/types.gen.ts")
    for banned_export in banned_exports:
        assert banned_export not in source


def test_public_sdk_types_include_exports_first_shapes() -> None:
    """Public TS SDK types should reflect the active exports-first contract."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/types.gen.ts")
    assert "export type CreateExportRequest =" in source
    assert "export type ExportListResponse =" in source
    assert "export type ExportResource =" in source


def test_public_sdk_types_exclude_wrapper_specific_aliases() -> None:
    """Public file SDK types must not expose deleted transport-wrapper types."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/types.gen.ts")
    assert "export type RequestOptions =" not in source
    assert "export type Result =" not in source
    assert re.search(r"\b\w+RequestOptions\b", source) is None
    assert re.search(r"\b\w+Result\b", source) is None


def test_public_sdk_uses_only_explicit_public_entrypoints() -> None:
    """Public TS entrypoints stay on explicit subpaths, not root barrels."""
    package_root = REPO_ROOT / "packages" / TS_PACKAGE_DIR / "src"
    assert not (package_root / "index.ts").exists()
    assert not (package_root / "client" / "index.ts").exists()
    assert (package_root / "client" / "client" / "index.ts").exists()


def test_public_sdk_internal_index_is_not_a_public_entrypoint() -> None:
    """The internal generator index remains a private scaffold only."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/client/index.ts")

    assert source.startswith(
        "// This file is auto-generated by @hey-api/openapi-ts"
    )
    assert "./client/index.js" not in _load_source_text(
        TS_PACKAGE_DIR,
        "client/types.gen.ts",
    )


def test_public_sdk_top_level_modules_use_esm_specifiers() -> None:
    """Top-level generated modules must use explicit ESM import specifiers."""
    client_source = _load_source_text(TS_PACKAGE_DIR, "client/client.gen.ts")
    sdk_source = _load_source_text(TS_PACKAGE_DIR, "client/sdk.gen.ts")

    assert "./client/index.js" in client_source
    assert "./types.gen.js" in client_source
    assert "./client.gen.js" in sdk_source
    assert "./client/index.js" in sdk_source
    assert "./types.gen.js" in sdk_source


def test_public_sdk_exposes_exports_first_operations() -> None:
    """SDK module must expose the current public export operations."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/sdk.gen.ts")
    assert "export const listExports" in source
    assert "export const getExport" in source
    assert "export const createExport" in source
    assert "export const cancelExport" in source


def test_public_sdk_operation_docblocks_include_returns_tags() -> None:
    """Generated SDK docblocks should remain sentence-style TSDoc."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/sdk.gen.ts")

    assert "Expose the current transfer policy envelope." in source
    assert (
        "@returns The response from the "
        "`getTransferCapabilities` operation." in source
    )
    assert "@returns The response from the `listExports` operation." in source


def test_public_sdk_operation_docblocks_exclude_python_docstring_sections() -> (
    None
):
    """Public TSDoc must not echo server Google-style docstring sections."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/sdk.gen.ts")
    assert "Args:" not in source
    assert "Returns:" not in source
    assert "Raises:" not in source
    assert "Yields:" not in source


def test_public_sdk_types_include_sentence_style_alias_docblocks() -> None:
    """Generated exported type aliases should carry sentence-style docblocks."""
    source = _load_source_text(TS_PACKAGE_DIR, "client/types.gen.ts")

    assert (
        "/**\n"
        " * Request data for the `GetTransferCapabilities` operation.\n"
        " */\n"
        "export type GetTransferCapabilitiesData ="
    ) in source
    assert (
        "/**\n"
        " * Error responses for the `GetTransferCapabilities` operation.\n"
        " */\n"
        "export type GetTransferCapabilitiesErrors ="
    ) in source
    assert (
        "/**\n"
        " * Error union for the `GetTransferCapabilities` operation.\n"
        " */\n"
        "export type GetTransferCapabilitiesError ="
    ) in source
    assert (
        "/**\n"
        " * Validation error envelope returned for invalid request payloads.\n"
        " */\n"
        "export type HttpValidationError ="
    ) in source
    assert (
        "/**\n"
        " * One request-validation issue with location, message, and "
        "error type.\n"
        " */\n"
        "export type ValidationError ="
    ) in source
