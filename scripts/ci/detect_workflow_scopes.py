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
    "packages/nova_auth_api/",
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
CONFORMANCE_REQUIRED_PREFIXES = (
    *RUNTIME_PREFIXES,
    "packages/contracts/",
    "packages/nova_sdk_auth/",
    "packages/nova_sdk_fetch/",
    "packages/nova_sdk_file/",
    "packages/nova_sdk_r_auth/",
    "packages/nova_sdk_r_file/",
    "scripts/conformance/",
    "scripts/contracts/",
    "scripts/release/tests/",
)
CONFORMANCE_REQUIRED_EXACT = {
    "package.json",
    "package-lock.json",
    ".npmrc",
    ".github/workflows/conformance-clients.yml",
    ".github/actions/setup-python-uv/action.yml",
} | CONFORMANCE_GENERATOR_EXACT
CONFORMANCE_OPTIONAL_PREFIXES = (
    *RUNTIME_PREFIXES,
    "packages/contracts/typescript/",
    "packages/nova_sdk_auth/",
    "packages/nova_sdk_fetch/",
    "packages/nova_sdk_file/",
    "scripts/conformance/",
)
CONFORMANCE_OPTIONAL_EXACT = {
    "package.json",
    "package-lock.json",
    ".npmrc",
    ".github/workflows/conformance-clients.yml",
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
    run_conformance_required = any(
        _matches(
            path,
            prefixes=CONFORMANCE_REQUIRED_PREFIXES,
            exact=CONFORMANCE_REQUIRED_EXACT,
        )
        for path in changed_files
    )
    run_conformance_optional = any(
        _matches(
            path,
            prefixes=CONFORMANCE_OPTIONAL_PREFIXES,
            exact=CONFORMANCE_OPTIONAL_EXACT,
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
        "run_conformance_required": str(run_conformance_required).lower(),
        "run_conformance_optional": str(run_conformance_optional).lower(),
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
