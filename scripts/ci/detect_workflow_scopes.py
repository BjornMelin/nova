"""Classify changed files into GitHub Actions workflow scopes."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RUNTIME_PREFIXES = (
    "packages/nova_file_api/",
    "packages/nova_dash_bridge/",
    "packages/nova_runtime_support/",
)
RUNTIME_EXACT = {
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    ".github/actions/setup-python-uv/action.yml",
}
CONFORMANCE_GENERATOR_EXACT = {
    "scripts/release/generate_clients.py",
    "scripts/release/generate_python_clients.py",
}
GENERATED_CLIENTS_PREFIXES = (
    *RUNTIME_PREFIXES,
    "packages/contracts/",
    "scripts/contracts/",
)
GENERATED_CLIENTS_EXACT = {
    "package.json",
    "package-lock.json",
    ".npmrc",
    ".github/workflows/ci.yml",
} | CONFORMANCE_GENERATOR_EXACT
DASH_CONFORMANCE_PREFIXES = (
    "packages/nova_dash_bridge/",
    "packages/contracts/fixtures/",
    "scripts/conformance/",
    "scripts/release/tests/",
)
DASH_CONFORMANCE_EXACT = {
    ".github/workflows/ci.yml",
} | CONFORMANCE_GENERATOR_EXACT
SHINY_CONFORMANCE_PREFIXES = (
    "packages/nova_sdk_r_file/",
    "packages/contracts/fixtures/",
    "scripts/conformance/",
    "scripts/release/tests/",
)
SHINY_CONFORMANCE_EXACT = {
    ".github/workflows/ci.yml",
} | CONFORMANCE_GENERATOR_EXACT
TYPESCRIPT_CONFORMANCE_PREFIXES = (
    "packages/contracts/fixtures/",
    "packages/contracts/typescript/",
    "packages/nova_sdk_fetch/",
    "packages/nova_sdk_file/",
    "scripts/conformance/",
    "scripts/release/tests/",
)
TYPESCRIPT_CONFORMANCE_EXACT = {
    "package.json",
    "package-lock.json",
    ".npmrc",
    ".github/workflows/ci.yml",
} | CONFORMANCE_GENERATOR_EXACT
CFN_PREFIXES = (
    "scripts/ci/",
    "infra/",
    "buildspecs/",
    ".github/workflows/",
    ".github/actions/",
    "tests/infra/",
    "scripts/release/",
    "scripts/contracts/",
    "docs/architecture/",
    "docs/runbooks/",
    "docs/standards/",
    "docs/contracts/",
    "docs/release/",
)
CFN_AUTHORITY_DOC_EXACT = {
    "docs/PRD.md",
}
CFN_EXACT = {
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/plan/PLAN.md",
} | CFN_AUTHORITY_DOC_EXACT
DOC_ONLY_PREFIXES = ("docs/",)
DOC_ONLY_EXACT = {"AGENTS.md", "README.md"}


class _ReleaseCommonModule(Protocol):
    def list_changed_files(
        self,
        repo_root: Path,
        *,
        head_commit: str,
        base_commit: str | None,
    ) -> list[str]: ...

    def load_workspace_units(self, repo_root: Path) -> dict[str, Any]: ...

    def detect_changed_unit_ids(
        self,
        changed_files: list[str],
        units: dict[str, Any],
    ) -> set[str]: ...


def _common_module() -> _ReleaseCommonModule:
    return cast(
        _ReleaseCommonModule,
        importlib.import_module("scripts.release.common"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify changed files into workflow execution scopes "
            "for GitHub Actions."
        )
    )
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", default="")
    parser.add_argument(
        "--github-output", default=os.environ.get("GITHUB_OUTPUT", "")
    )
    return parser.parse_args()


def _normalize_base_sha(raw: str) -> str | None:
    value = raw.strip()
    if not value or set(value) == {"0"}:
        return None
    return value


def _matches(path: str, *, prefixes: tuple[str, ...], exact: set[str]) -> bool:
    if path in exact:
        return True
    return any(path.startswith(prefix) for prefix in prefixes)


def _is_doc_like(path: str) -> bool:
    if path.endswith(".md"):
        return True
    if path in DOC_ONLY_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in DOC_ONLY_PREFIXES)


def _load_changed_files(
    event_name: str, head_sha: str, base_sha: str | None
) -> list[str]:
    common = _common_module()
    if event_name == "workflow_dispatch":
        base_sha = None
    return common.list_changed_files(
        REPO_ROOT,
        head_commit=head_sha,
        base_commit=base_sha,
    )


def _build_outputs(changed_files: list[str]) -> dict[str, str]:
    common = _common_module()
    units = common.load_workspace_units(REPO_ROOT)
    affected_units = sorted(
        common.detect_changed_unit_ids(changed_files, units)
    )
    docs_only = bool(changed_files) and all(
        _is_doc_like(path) for path in changed_files
    )

    run_runtime_ci = any(
        _matches(path, prefixes=RUNTIME_PREFIXES, exact=RUNTIME_EXACT)
        for path in changed_files
    )
    run_generated_clients = any(
        _matches(
            path,
            prefixes=GENERATED_CLIENTS_PREFIXES,
            exact=GENERATED_CLIENTS_EXACT,
        )
        for path in changed_files
    )
    run_dash_conformance = any(
        _matches(
            path,
            prefixes=DASH_CONFORMANCE_PREFIXES,
            exact=DASH_CONFORMANCE_EXACT,
        )
        for path in changed_files
    )
    run_shiny_conformance = any(
        _matches(
            path,
            prefixes=SHINY_CONFORMANCE_PREFIXES,
            exact=SHINY_CONFORMANCE_EXACT,
        )
        for path in changed_files
    )
    run_typescript_conformance = any(
        _matches(
            path,
            prefixes=TYPESCRIPT_CONFORMANCE_PREFIXES,
            exact=TYPESCRIPT_CONFORMANCE_EXACT,
        )
        for path in changed_files
    )
    run_cfn = any(
        _matches(path, prefixes=CFN_PREFIXES, exact=CFN_EXACT)
        for path in changed_files
    )

    return {
        "changed_files_json": json.dumps(changed_files),
        "affected_units_json": json.dumps(affected_units),
        "docs_only": str(docs_only).lower(),
        "run_runtime_ci": str(run_runtime_ci).lower(),
        "run_generated_clients": str(run_generated_clients).lower(),
        "run_dash_conformance": str(run_dash_conformance).lower(),
        "run_shiny_conformance": str(run_shiny_conformance).lower(),
        "run_typescript_conformance": str(run_typescript_conformance).lower(),
        "run_cfn": str(run_cfn).lower(),
    }


def _write_outputs(outputs: dict[str, str], github_output: str) -> None:
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    else:
        json.dump(outputs, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


def main() -> int:
    """Run the classifier and emit GitHub Actions step outputs.

    Returns:
        int: 0 for success, non-zero for failure.
    """
    args = _parse_args()
    base_sha = _normalize_base_sha(args.base_sha)
    changed_files = _load_changed_files(
        args.event_name, args.head_sha, base_sha
    )
    outputs = _build_outputs(changed_files)
    _write_outputs(outputs, args.github_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
