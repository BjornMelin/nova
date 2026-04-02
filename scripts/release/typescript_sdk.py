#!/usr/bin/env python3
"""TypeScript SDK generation helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release.sdk_common import (
    REPO_ROOT,
    GenerationTarget,
    _build_public_openapi_spec,
)

OPENAPI_TS_CLI = REPO_ROOT / "node_modules" / ".bin" / "openapi-ts"
OPENAPI_TS_CONFIG = REPO_ROOT / "openapi-ts.config.ts"
_LEGACY_TS_ARTIFACTS = (
    Path("src") / "client.ts",
    Path("src") / "errors.ts",
    Path("src") / "operations.ts",
    Path("src") / "types.ts",
    Path("src") / "generated",
)
_UPSTREAM_GET_PARSE_AS_SIGNATURE = (
    "export const getParseAs = (contentType: string | null): "
    "Exclude<Config['parseAs'], 'auto'> => {"
)
_COMPAT_GET_PARSE_AS_SIGNATURE = (
    "export const getParseAs = (contentType: string | null): "
    "Exclude<Config['parseAs'], 'auto'> | undefined => {"
)


def _apply_typescript_upstream_compatibility_fixes(root: Path) -> None:
    """Apply narrow compatibility fixes for current upstream TS output.

    Args:
        root: Root directory containing generated client files.

    Raises:
        RuntimeError: Raised when the expected upstream ``getParseAs``
            signature is missing from the generated output.
    """
    utils_path = root / "client" / "utils.gen.ts"
    if not utils_path.exists():
        return

    text = utils_path.read_text(encoding="utf-8")
    if _UPSTREAM_GET_PARSE_AS_SIGNATURE not in text:
        raise RuntimeError(
            "unexpected generated TypeScript SDK output: "
            "missing upstream getParseAs signature "
            f"{_UPSTREAM_GET_PARSE_AS_SIGNATURE!r} in {utils_path}"
        )

    updated = text.replace(
        _UPSTREAM_GET_PARSE_AS_SIGNATURE,
        _COMPAT_GET_PARSE_AS_SIGNATURE,
        1,
    )
    if updated != text:
        utils_path.write_text(updated, encoding="utf-8")


def _run_openapi_ts(
    *,
    input_spec_path: Path,
    output_path: Path,
) -> None:
    """Run the @hey-api/openapi-ts generator for the provided OpenAPI spec.

    Args:
        input_spec_path: Path to the generated public OpenAPI JSON file.
        output_path: Path where the TypeScript SDK output directory should be
            written.

    Raises:
        RuntimeError: Raised when the `openapi-ts` CLI binary is missing at
            ``OPENAPI_TS_CLI``.
        RuntimeError: Raised when the committed
            ``OPENAPI_TS_CONFIG`` file is missing.
        RuntimeError: Raised when the command invocation fails because
            `npm` is unavailable or not on ``PATH`` (wrapped
            `FileNotFoundError`).
        RuntimeError: Raised when generation exceeds the 120-second timeout
            (`subprocess.TimeoutExpired`) and includes captured stdout/stderr
            details.
        RuntimeError: Raised when the command exits non-zero and includes
            captured stdout/stderr details in the message.
    """
    if not OPENAPI_TS_CLI.exists():
        raise RuntimeError(
            "@hey-api/openapi-ts generation failed: missing repo-installed "
            f"CLI at {OPENAPI_TS_CLI}; run `npm ci` from repo root"
        )
    if not OPENAPI_TS_CONFIG.exists():
        raise RuntimeError(
            f"missing committed openapi-ts config at {OPENAPI_TS_CONFIG}"
        )

    command = ["npm", "run", "openapi-ts"]
    env = os.environ | {
        "NOVA_OPENAPI_TS_INPUT": str(input_spec_path),
        "NOVA_OPENAPI_TS_OUTPUT": str(output_path),
    }
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=120,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "@hey-api/openapi-ts generation failed: unable to invoke "
            f"command {' '.join(command)}; ensure Node/npm are installed "
            "and that `npm` is available on PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.strip()
            if isinstance(exc.stdout, str)
            else str(exc.stdout or "").strip()
        )
        stderr = (
            exc.stderr.strip()
            if isinstance(exc.stderr, str)
            else str(exc.stderr or "").strip()
        )
        details = stderr or stdout or "no output captured"
        raise RuntimeError(
            "@hey-api/openapi-ts generation timed out after 120s for "
            f"{input_spec_path} using command {' '.join(command)}: {details}"
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "no output captured"
        raise RuntimeError(
            "@hey-api/openapi-ts generation command failed for "
            f"{input_spec_path}: {details}"
        )


def _typescript_generated_files(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _check_typescript_generated_output(
    package_root: Path,
    *,
    expected_root: Path,
) -> list[str]:
    issues: list[str] = []
    actual_root = package_root / "src" / "client"
    if not actual_root.exists():
        issues.append(f"missing generated SDK directory: {actual_root}")
        return issues

    expected_files = _typescript_generated_files(expected_root)
    actual_files = _typescript_generated_files(actual_root)
    missing = sorted(set(expected_files) - set(actual_files))
    extra = sorted(set(actual_files) - set(expected_files))
    stale = sorted(
        path
        for path in expected_files
        if path in actual_files and actual_files[path] != expected_files[path]
    )
    if missing:
        issues.append(
            "missing expected generated SDK artifacts in "
            f"{actual_root}: {', '.join(missing)}"
        )
    if extra:
        issues.append(
            "unexpected generated SDK artifacts in "
            f"{actual_root}: {', '.join(extra)}"
        )
    issues.extend(
        f"stale generated client artifact: {actual_root / rel_path}"
        for rel_path in stale
    )

    for legacy_path in _LEGACY_TS_ARTIFACTS:
        absolute_path = package_root / legacy_path
        if absolute_path.exists():
            issues.append(
                "obsolete TypeScript SDK artifact still present: "
                f"{absolute_path}"
            )
    return issues


def _remove_legacy_typescript_artifacts(package_root: Path) -> None:
    for legacy_path in _LEGACY_TS_ARTIFACTS:
        absolute_path = package_root / legacy_path
        if absolute_path.is_dir():
            shutil.rmtree(absolute_path)
        elif absolute_path.exists():
            absolute_path.unlink()


def generate_or_check_typescript_sdk(
    target: GenerationTarget,
    *,
    spec: dict[str, Any],
    check: bool,
) -> list[str]:
    """Generate or verify the committed TypeScript SDK tree.

    Args:
        target: Generation target containing the TypeScript package root.
        spec: OpenAPI specification object, serialized and reduced to the public
            spec before SDK generation.
        check: If ``True``, compare generated output with committed artifacts
            and return mismatches; if ``False``, replace committed SDK output.

    Returns:
        A list of mismatched file/path entries when ``check`` is ``True``;
            otherwise an empty list.

    Raises:
        OSError: Raised by ``tempfile`` or file-system write/read operations.
        (TypeError, ValueError): Raised on JSON serialization or decoding
            failures.
        RuntimeError: Raised from ``_run_openapi_ts`` if generation
            prerequisites or command execution fail.
        OSError: Raised by ``shutil`` operations when copying/removing
            artifacts.
    """
    public_spec = _build_public_openapi_spec(spec)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        input_spec_path = tmp_root / "nova-file-api.public.openapi.json"
        output_path = tmp_root / "client"
        input_spec_path.write_text(
            json.dumps(public_spec, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _run_openapi_ts(
            input_spec_path=input_spec_path, output_path=output_path
        )
        _apply_typescript_upstream_compatibility_fixes(output_path)

        if check:
            return _check_typescript_generated_output(
                target.ts_package_root,
                expected_root=output_path,
            )

        package_root = target.ts_package_root
        generated_root = package_root / "src" / "client"
        shutil.rmtree(generated_root, ignore_errors=True)
        generated_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(output_path, generated_root)
        _remove_legacy_typescript_artifacts(package_root)
        shutil.rmtree(package_root / "dist", ignore_errors=True)
    return []
