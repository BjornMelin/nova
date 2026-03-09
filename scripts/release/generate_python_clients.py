#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate committed Python SDK package sources from canonical OpenAPI."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from nova_runtime_support import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ROOT = REPO_ROOT / "packages" / "contracts" / "openapi"
_IGNORED_PARTS = {"__pycache__"}
_IGNORED_PREFIXES = (".",)
_GENERATOR_TIMEOUT_SECONDS = 60
_FORMATTER_TIMEOUT_SECONDS = 60
_RELATIVE_IMPORT_RE = re.compile(
    r"^from (?P<dots>\.+)(?P<module>[a-zA-Z0-9_\.]*) import (?P<names>.+)$"
)
_HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
)


@dataclass(frozen=True)
class GenerationTarget:
    """Python SDK package synced from one committed OpenAPI document."""

    spec_path: Path
    output_path: Path
    package_name: str


TARGETS = (
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-file-api.openapi.json",
        output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_py_file"
        / "src"
        / "nova_sdk_py_file",
        package_name="nova_sdk_py_file",
    ),
    GenerationTarget(
        spec_path=OPENAPI_ROOT / "nova-auth-api.openapi.json",
        output_path=REPO_ROOT
        / "packages"
        / "nova_sdk_py_auth"
        / "src"
        / "nova_sdk_py_auth",
        package_name="nova_sdk_py_auth",
    ),
)


def _should_ignore(rel_path: Path) -> bool:
    return any(
        part in _IGNORED_PARTS or part.startswith(_IGNORED_PREFIXES)
        for part in rel_path.parts
    )


def _collect_file_map(root: Path) -> dict[Path, bytes]:
    file_map: dict[Path, bytes] = {}
    if not root.exists():
        return file_map

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root)
        if _should_ignore(rel_path):
            continue
        file_map[rel_path] = path.read_bytes()
    return file_map


def _remove_ignored_paths(root: Path) -> None:
    if not root.exists():
        return

    for path in sorted(root.rglob("*"), reverse=True):
        rel_path = path.relative_to(root)
        if not _should_ignore(rel_path):
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            continue
        path.unlink(missing_ok=True)


def _load_spec_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"OpenAPI spec must decode to an object: {path}")
    return payload


def _filter_internal_operations_for_public_sdk(
    spec: dict[str, Any],
) -> dict[str, Any]:
    filtered = copy.deepcopy(spec)
    paths = filtered.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI spec missing paths object")

    for path, path_item in list(paths.items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in list(path_item.items()):
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            if (
                operation.get(SDK_VISIBILITY_EXTENSION)
                == SDK_VISIBILITY_INTERNAL
            ):
                del path_item[method]
        if not any(method in _HTTP_METHODS for method in path_item):
            del paths[path]
    return filtered


def _write_temp_spec(*, spec: dict[str, Any], destination: Path) -> Path:
    destination.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def _generate_target(target: GenerationTarget, temp_root: Path) -> Path:
    destination = temp_root / target.package_name
    spec_path = _write_temp_spec(
        spec=_filter_internal_operations_for_public_sdk(
            _load_spec_json(target.spec_path)
        ),
        destination=temp_root / f"{target.package_name}.openapi.json",
    )
    command = [
        sys.executable,
        "-m",
        "openapi_python_client",
        "generate",
        "--path",
        str(spec_path),
        "--meta",
        "none",
        "--output-path",
        str(destination),
        "--overwrite",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=_GENERATOR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        raise RuntimeError(
            "openapi-python-client generation timed out for "
            f"{target.spec_path}:\nstdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            "openapi-python-client generation failed for "
            f"{target.spec_path}:\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return destination


def _run_ruff(*, args: list[str], root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", *args, str(root)],
        check=False,
        text=True,
        capture_output=True,
        timeout=_FORMATTER_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "ruff step failed for "
            f"{root} ({' '.join(args)}):\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _repair_missing_unset_imports(root: Path) -> None:
    # openapi-python-client occasionally emits `Unset` annotations without
    # importing `Unset`; patch generated files before lint/format so committed
    # SDK artifacts remain type-checkable and deterministic.
    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "Unset" not in content:
            continue
        updated = content
        updated = updated.replace(
            "types import UNSET, Response\n",
            "types import UNSET, Response, Unset\n",
        )
        updated = updated.replace(
            "types import UNSET, Response, Unset, Unset\n",
            "types import UNSET, Response, Unset\n",
        )
        updated = updated.replace(
            "types import UNSET, Unset, Unset\n",
            "types import UNSET, Unset\n",
        )
        if updated != content:
            path.write_text(updated, encoding="utf-8")


def _rewrite_relative_imports_to_absolute(root: Path) -> None:
    package_name = root.name
    for path in root.rglob("*.py"):
        rel_path = path.relative_to(root)
        depth = len(rel_path.parent.parts)
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        rewritten: list[str] = []
        for line in lines:
            match = _RELATIVE_IMPORT_RE.match(line)
            if match is None:
                rewritten.append(line)
                continue
            dot_count = len(match.group("dots"))
            if dot_count > depth + 1:
                rewritten.append(line)
                continue
            suffix = match.group("module")
            parent_parts = list(
                rel_path.parent.parts[: depth - (dot_count - 1)]
            )
            absolute_parts = [package_name, *parent_parts]
            if suffix:
                absolute_parts.extend(suffix.split("."))
            absolute_target = ".".join(part for part in absolute_parts if part)
            rewritten.append(
                f"from {absolute_target} import {match.group('names')}"
            )
            changed = True
        if changed:
            path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def _add_generated_ruff_noqa(root: Path) -> None:
    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if content.startswith("# ruff: noqa\n"):
            continue
        path.write_text(f"# ruff: noqa\n{content}", encoding="utf-8")


def _replace_text(
    content: str,
    *,
    old: str,
    new: str,
    path: str,
    required: bool = True,
) -> str:
    if old in content:
        return content.replace(old, new)
    if new in content:
        return content
    if required:
        raise RuntimeError(
            f"expected snippet not found in generated file: {path}"
        )
    return content


def _rewrite_file(
    root: Path,
    rel_path: str,
    transform: Callable[[str], str],
) -> None:
    path = root / rel_path
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    updated = transform(content)
    if updated != content:
        path.write_text(updated, encoding="utf-8")


def _replace_empty_docstring(content: str, *, doc: str) -> str:
    return content.replace('    """ """', f'    """{doc}"""')


def _docstring_transformer(doc: str) -> Callable[[str], str]:
    def transform(content: str) -> str:
        return _replace_empty_docstring(content, doc=doc)

    return transform


def _rewrite_generated_empty_docstrings(root: Path) -> None:
    for path in root.rglob("*.py"):
        rel_path = path.relative_to(root).as_posix()
        _rewrite_file(
            root,
            rel_path,
            _docstring_transformer("Generated API client symbol."),
        )


def _sanitize_unexpected_status_message(content: str) -> str:
    content = _replace_text(
        content,
        old=(
            "        super().__init__(\n"
            "            f\"Unexpected status code: {status_code}\\n\\nResponse content:\\n{content.decode(errors='ignore')}\"\n"
            "        )\n"
        ),
        new='        super().__init__(f"Unexpected status code: {status_code}")\n',
        path="errors.py",
        required=False,
    )
    return content.replace(
        "        super().__init__(\n"
        '            "Unexpected status code: "\n'
        '            f"{status_code}\\n\\nResponse content:\\n"\n'
        "            f\"{content.decode(errors='ignore')}\"\n"
        "        )\n",
        '        super().__init__(f"Unexpected status code: {status_code}")\n',
    )


def _patch_auth_sdk(root: Path) -> None:
    if not (root / "models" / "token_introspect_response.py").exists():
        return

    def patch_introspect_token(content: str) -> str:
        content = _replace_text(
            content,
            old="    if isinstance(body, TokenIntrospectFormRequest):\n",
            new="    elif isinstance(body, TokenIntrospectFormRequest):\n",
            path="api/token/introspect_token.py",
        )
        content = _replace_text(
            content,
            old=(
                "    Args:\n"
                "        body (TokenIntrospectRequest): Request payload for "
                "token introspection.\n"
                "        body (TokenIntrospectFormRequest): Request payload "
                "for token introspection.\n"
            ),
            new=(
                "    Args:\n"
                "        body (TokenIntrospectRequest | "
                "TokenIntrospectFormRequest | Unset): Request payload for "
                "token introspection.\n"
            ),
            path="api/token/introspect_token.py",
        )
        content = content.replace(
            "    Returns:\n        TokenIntrospectResponse\n",
            "    Returns:\n        TokenIntrospectResponse | None\n",
        )
        return content

    _rewrite_file(
        root,
        "api/token/introspect_token.py",
        patch_introspect_token,
    )

    def patch_health_ready(content: str) -> str:
        if "if response.status_code == 503:" in content:
            return content
        return _replace_text(
            content,
            old=(
                "    if response.status_code == 200:\n"
                "        response_200 = HealthResponse.from_dict(response.json())\n\n"
                "        return response_200\n\n"
                "    if client.raise_on_unexpected_status:\n"
            ),
            new=(
                "    if response.status_code == 200:\n"
                "        response_200 = HealthResponse.from_dict(response.json())\n\n"
                "        return response_200\n\n"
                "    if response.status_code == 503:\n"
                "        response_503_error = ErrorEnvelope.from_dict(response.json())\n\n"
                "        return response_503_error\n\n"
                "    if client.raise_on_unexpected_status:\n"
            ),
            path="api/health/health_ready.py",
            required=False,
        )

    _rewrite_file(root, "api/health/health_ready.py", patch_health_ready)

    def patch_client(content: str) -> str:
        content = _replace_text(
            content,
            old=(
                '    def with_headers(self, headers: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional headers"""\n'
                "        if self._client is not None:\n"
                "            self._client.headers.update(headers)\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.headers.update(headers)\n"
                "        return evolve(self, headers={**self._headers, **headers})\n"
            ),
            new=(
                '    def with_headers(self, headers: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional headers"""\n'
                "        return evolve(self, headers={**self._headers, **headers})\n"
            ),
            path="client.py",
        )
        content = _replace_text(
            content,
            old=(
                '    def with_cookies(self, cookies: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional cookies"""\n'
                "        if self._client is not None:\n"
                "            self._client.cookies.update(cookies)\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.cookies.update(cookies)\n"
                "        return evolve(self, cookies={**self._cookies, **cookies})\n"
            ),
            new=(
                '    def with_cookies(self, cookies: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional cookies"""\n'
                "        return evolve(self, cookies={**self._cookies, **cookies})\n"
            ),
            path="client.py",
        )
        content = _replace_text(
            content,
            old=(
                '    def with_timeout(self, timeout: httpx.Timeout) -> "Client":\n'
                '        """Get a new client matching this one with a new timeout configuration"""\n'
                "        if self._client is not None:\n"
                "            self._client.timeout = timeout\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.timeout = timeout\n"
                "        return evolve(self, timeout=timeout)\n"
            ),
            new=(
                '    def with_timeout(self, timeout: httpx.Timeout) -> "Client":\n'
                '        """Get a new client matching this one with a new timeout configuration"""\n'
                "        return evolve(self, timeout=timeout)\n"
            ),
            path="client.py",
        )
        content = _replace_text(
            content,
            old=(
                '    def with_headers(self, headers: dict[str, str]) -> "AuthenticatedClient":\n'
                '        """Get a new client matching this one with additional headers"""\n'
                "        if self._client is not None:\n"
                "            self._client.headers.update(headers)\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.headers.update(headers)\n"
                "        return evolve(self, headers={**self._headers, **headers})\n"
            ),
            new=(
                '    def with_headers(self, headers: dict[str, str]) -> "AuthenticatedClient":\n'
                '        """Get a new client matching this one with additional headers"""\n'
                "        return evolve(self, headers={**self._headers, **headers})\n"
            ),
            path="client.py",
        )
        content = _replace_text(
            content,
            old=(
                '    def with_cookies(self, cookies: dict[str, str]) -> "AuthenticatedClient":\n'
                '        """Get a new client matching this one with additional cookies"""\n'
                "        if self._client is not None:\n"
                "            self._client.cookies.update(cookies)\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.cookies.update(cookies)\n"
                "        return evolve(self, cookies={**self._cookies, **cookies})\n"
            ),
            new=(
                '    def with_cookies(self, cookies: dict[str, str]) -> "AuthenticatedClient":\n'
                '        """Get a new client matching this one with additional cookies"""\n'
                "        return evolve(self, cookies={**self._cookies, **cookies})\n"
            ),
            path="client.py",
        )
        content = _replace_text(
            content,
            old=(
                '    def with_timeout(self, timeout: httpx.Timeout) -> "AuthenticatedClient":\n'
                '        """Get a new client matching this one with a new timeout configuration"""\n'
                "        if self._client is not None:\n"
                "            self._client.timeout = timeout\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.timeout = timeout\n"
                "        return evolve(self, timeout=timeout)\n"
            ),
            new=(
                '    def with_timeout(self, timeout: httpx.Timeout) -> "AuthenticatedClient":\n'
                '        """Get a new client matching this one with a new timeout configuration"""\n'
                "        return evolve(self, timeout=timeout)\n"
            ),
            path="client.py",
        )
        content = _replace_text(
            content,
            old=(
                "            self._headers[self.auth_header_name] = (\n"
                '                f"{self.prefix} {self.token}" if self.prefix else self.token\n'
                "            )\n"
                "            self._client = httpx.Client(\n"
                "                base_url=self._base_url,\n"
                "                cookies=self._cookies,\n"
                "                headers=self._headers,\n"
            ),
            new=(
                "            headers = {**self._headers}\n"
                "            headers[self.auth_header_name] = (\n"
                '                f"{self.prefix} {self.token}" if self.prefix else self.token\n'
                "            )\n"
                "            self._client = httpx.Client(\n"
                "                base_url=self._base_url,\n"
                "                cookies=self._cookies,\n"
                "                headers=headers,\n"
            ),
            path="client.py",
            required=False,
        )
        return _replace_text(
            content,
            old=(
                "            self._headers[self.auth_header_name] = (\n"
                '                f"{self.prefix} {self.token}" if self.prefix else self.token\n'
                "            )\n"
                "            self._async_client = httpx.AsyncClient(\n"
                "                base_url=self._base_url,\n"
                "                cookies=self._cookies,\n"
                "                headers=self._headers,\n"
            ),
            new=(
                "            headers = {**self._headers}\n"
                "            headers[self.auth_header_name] = (\n"
                '                f"{self.prefix} {self.token}" if self.prefix else self.token\n'
                "            )\n"
                "            self._async_client = httpx.AsyncClient(\n"
                "                base_url=self._base_url,\n"
                "                cookies=self._cookies,\n"
                "                headers=headers,\n"
            ),
            path="client.py",
            required=False,
        )

    _rewrite_file(root, "client.py", patch_client)

    def patch_token_introspect_response(content: str) -> str:
        content = content.replace(", cast", "")
        content = _replace_text(
            content,
            old=(
                "    def to_dict(self) -> dict[str, Any]:\n"
                "        from ..models.principal import Principal\n"
            ),
            new=(
                "    def to_dict(self) -> dict[str, Any]:\n"
                '        """Serialize this model to a JSON-compatible dict."""\n'
                "        from ..models.principal import Principal\n"
            ),
            path="models/token_introspect_response.py",
        )
        content = _replace_text(
            content,
            old=(
                "    @classmethod\n"
                "    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:\n"
                "        from ..models.principal import Principal\n"
            ),
            new=(
                "    @classmethod\n"
                "    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:\n"
                '        """Build this model from a JSON-compatible mapping."""\n'
                "        from ..models.principal import Principal\n"
            ),
            path="models/token_introspect_response.py",
        )
        return _replace_text(
            content,
            old="            return cast(None | Principal | Unset, data)\n",
            new=(
                "            raise TypeError(\n"
                '                "principal must be an object, null, or UNSET"\n'
                "            )\n"
            ),
            path="models/token_introspect_response.py",
        )

    _rewrite_file(
        root,
        "models/token_introspect_response.py",
        patch_token_introspect_response,
    )

    def patch_principal(content: str) -> str:
        if "_parse_permissions" in content and "_parse_scopes" in content:
            return content
        content = content.replace(
            '        permissions = cast(list[str], d.pop("permissions", UNSET))\n\n',
            "        def _parse_permissions(data: object) -> list[str] | Unset:\n"
            "            if isinstance(data, Unset):\n"
            "                return data\n"
            "            if not isinstance(data, list):\n"
            '                raise TypeError("permissions must be a list when set")\n'
            "            return cast(list[str], data)\n\n"
            "        permissions = _parse_permissions(\n"
            '            d.pop("permissions", UNSET)\n'
            "        )\n\n",
        )
        content = content.replace(
            '        scopes = cast(list[str], d.pop("scopes", UNSET))\n',
            "        def _parse_scopes(data: object) -> list[str] | Unset:\n"
            "            if isinstance(data, Unset):\n"
            "                return data\n"
            "            if not isinstance(data, list):\n"
            '                raise TypeError("scopes must be a list when set")\n'
            "            return cast(list[str], data)\n\n"
            '        scopes = _parse_scopes(d.pop("scopes", UNSET))\n',
        )
        return content

    _rewrite_file(root, "models/principal.py", patch_principal)

    def patch_introspect_form_request(content: str) -> str:
        if "_parse_required_permissions" in content:
            return content
        content = content.replace(
            "        required_permissions = cast(\n"
            '            list[str], d.pop("required_permissions", UNSET)\n'
            "        )\n\n",
            "        def _parse_required_permissions(\n"
            "            data: object,\n"
            "        ) -> list[str] | Unset:\n"
            "            if isinstance(data, Unset):\n"
            "                return data\n"
            "            if not isinstance(data, list):\n"
            "                raise TypeError(\n"
            '                    "required_permissions must be a list when set"\n'
            "                )\n"
            "            return cast(list[str], data)\n\n"
            "        required_permissions = _parse_required_permissions(\n"
            '            d.pop("required_permissions", UNSET)\n'
            "        )\n\n",
        )
        content = content.replace(
            '        required_scopes = cast(list[str], d.pop("required_scopes", UNSET))\n',
            "        def _parse_required_scopes(data: object) -> list[str] | Unset:\n"
            "            if isinstance(data, Unset):\n"
            "                return data\n"
            "            if not isinstance(data, list):\n"
            "                raise TypeError(\n"
            '                    "required_scopes must be a list when set"\n'
            "                )\n"
            "            return cast(list[str], data)\n\n"
            "        required_scopes = _parse_required_scopes(\n"
            '            d.pop("required_scopes", UNSET)\n'
            "        )\n",
        )
        return content

    _rewrite_file(
        root,
        "models/token_introspect_form_request.py",
        patch_introspect_form_request,
    )

    def patch_token_introspect_request(content: str) -> str:
        content = content.replace(
            "            required_permissions = self.required_permissions\n",
            "            required_permissions = list(self.required_permissions)\n",
        )
        return content.replace(
            "            required_scopes = self.required_scopes\n",
            "            required_scopes = list(self.required_scopes)\n",
        )

    _rewrite_file(
        root,
        "models/token_introspect_request.py",
        patch_token_introspect_request,
    )

    def patch_types(content: str) -> str:
        content = content.replace(
            "from http import HTTPStatus\n",
            "",
        )
        return content.replace(
            "    status_code: HTTPStatus\n",
            "    status_code: int\n",
        )

    _rewrite_file(root, "types.py", patch_types)

    def patch_token_introspect_request_repr(content: str) -> str:
        if "_attrs_field" not in content:
            content = content.replace(
                "from attrs import define as _attrs_define\n",
                "from attrs import define as _attrs_define\n"
                "from attrs import field as _attrs_field\n",
            )
        return content.replace(
            "    access_token: str\n",
            "    access_token: str = _attrs_field(repr=False)\n",
        )

    _rewrite_file(
        root,
        "models/token_introspect_request.py",
        patch_token_introspect_request_repr,
    )

    _rewrite_generated_empty_docstrings(root)
    _rewrite_file(
        root,
        "models/token_introspect_response_claims.py",
        _docstring_transformer(
            "Container for arbitrary token introspection claims."
        ),
    )
    _rewrite_file(
        root,
        "models/token_verify_response_claims.py",
        _docstring_transformer(
            "Container for arbitrary token verification claims."
        ),
    )
    _rewrite_file(root, "errors.py", _sanitize_unexpected_status_message)


def _patch_file_sdk(root: Path) -> None:
    if not (root / "models" / "sign_parts_request.py").exists():
        return

    def patch_list_jobs(content: str) -> str:
        if "from nova_sdk_py_file.client import AuthenticatedClient" in content:
            return content
        content = content.replace(
            "from ... import errors\n",
            "from nova_sdk_py_file import errors\n",
        )
        content = content.replace(
            "from ...client import AuthenticatedClient, Client\n",
            "from nova_sdk_py_file.client import AuthenticatedClient\n"
            "from nova_sdk_py_file.client import Client\n",
        )
        content = content.replace(
            "from ...models.job_list_response import JobListResponse\n",
            "from nova_sdk_py_file.models.job_list_response import (\n"
            "    JobListResponse,\n"
            ")\n",
        )
        content = content.replace(
            "from ...types import UNSET, Response, Unset\n",
            "from nova_sdk_py_file.types import Response\n"
            "from nova_sdk_py_file.types import UNSET\n"
            "from nova_sdk_py_file.types import Unset\n",
        )
        if (
            "from nova_sdk_py_file.client import AuthenticatedClient"
            not in content
        ):
            raise RuntimeError(
                "expected import rewrite not applied for api/jobs/list_jobs.py"
            )
        return content

    _rewrite_file(root, "api/jobs/list_jobs.py", patch_list_jobs)

    _rewrite_file(root, "errors.py", _sanitize_unexpected_status_message)

    def patch_retry_job(content: str) -> str:
        if "if response.status_code == 503:" in content:
            return content
        return _replace_text(
            content,
            old=(
                "    if response.status_code == 422:\n"
                "        response_422 = ErrorEnvelope.from_dict(response.json())\n\n"
                "        return response_422\n\n"
                "    if client.raise_on_unexpected_status:\n"
            ),
            new=(
                "    if response.status_code == 422:\n"
                "        response_422 = ErrorEnvelope.from_dict(response.json())\n\n"
                "        return response_422\n\n"
                "    if response.status_code == 503:\n"
                "        response_503 = ErrorEnvelope.from_dict(response.json())\n\n"
                "        return response_503\n\n"
                "    if client.raise_on_unexpected_status:\n"
            ),
            path="api/jobs/retry_job.py",
            required=False,
        )

    _rewrite_file(root, "api/jobs/retry_job.py", patch_retry_job)

    def patch_types(content: str) -> str:
        content = content.replace(
            "from http import HTTPStatus\n",
            "",
        )
        return content.replace(
            "    status_code: HTTPStatus\n",
            "    status_code: int\n",
        )

    _rewrite_file(root, "types.py", patch_types)

    def patch_client(content: str) -> str:
        content = _replace_text(
            content,
            old=(
                '    def with_headers(self, headers: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional headers"""\n'
                "        if self._client is not None:\n"
                "            self._client.headers.update(headers)\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.headers.update(headers)\n"
                "        return evolve(self, headers={**self._headers, **headers})\n"
            ),
            new=(
                '    def with_headers(self, headers: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional headers"""\n'
                "        return evolve(self, headers={**self._headers, **headers})\n"
            ),
            path="client.py",
            required=False,
        )
        content = _replace_text(
            content,
            old=(
                '    def with_cookies(self, cookies: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional cookies"""\n'
                "        if self._client is not None:\n"
                "            self._client.cookies.update(cookies)\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.cookies.update(cookies)\n"
                "        return evolve(self, cookies={**self._cookies, **cookies})\n"
            ),
            new=(
                '    def with_cookies(self, cookies: dict[str, str]) -> "Client":\n'
                '        """Get a new client matching this one with additional cookies"""\n'
                "        return evolve(self, cookies={**self._cookies, **cookies})\n"
            ),
            path="client.py",
            required=False,
        )
        return _replace_text(
            content,
            old=(
                '    def with_timeout(self, timeout: httpx.Timeout) -> "Client":\n'
                '        """Get a new client matching this one with a new timeout configuration"""\n'
                "        if self._client is not None:\n"
                "            self._client.timeout = timeout\n"
                "        if self._async_client is not None:\n"
                "            self._async_client.timeout = timeout\n"
                "        return evolve(self, timeout=timeout)\n"
            ),
            new=(
                '    def with_timeout(self, timeout: httpx.Timeout) -> "Client":\n'
                '        """Get a new client matching this one with a new timeout configuration"""\n'
                "        return evolve(self, timeout=timeout)\n"
            ),
            path="client.py",
            required=False,
        )

    _rewrite_file(root, "client.py", patch_client)

    for path in (root / "api").rglob("*.py"):
        rel_path = path.relative_to(root).as_posix()
        _rewrite_file(
            root,
            rel_path,
            lambda content: content.replace(
                "status_code=HTTPStatus(response.status_code),\n",
                "status_code=response.status_code,\n",
            ).replace("from http import HTTPStatus\n", ""),
        )

    def patch_sign_parts_request(content: str) -> str:
        return _replace_text(
            content,
            old="        part_numbers = self.part_numbers\n",
            new="        part_numbers = list(self.part_numbers)\n",
            path="models/sign_parts_request.py",
        )

    _rewrite_file(
        root,
        "models/sign_parts_request.py",
        patch_sign_parts_request,
    )

    def patch_presign_download_response(content: str) -> str:
        content = content.replace(
            "from attrs import define as _attrs_define\n",
            "from attrs import define as _attrs_define\n"
            "from attrs import field as _attrs_field\n",
        )
        return content.replace(
            "    url: str\n", "    url: str = _attrs_field(repr=False)\n"
        )

    _rewrite_file(
        root,
        "models/presign_download_response.py",
        patch_presign_download_response,
    )

    def patch_metrics_summary_response(content: str) -> str:
        return (
            _replace_text(
                content,
                old=(
                    "if TYPE_CHECKING:\n"
                    "    from ..models.metrics_summary_response_activity import (\n"
                    "        MetricsSummaryResponseActivity,\n"
                    "    )\n"
                    "    from ..models.metrics_summary_response_counters import (\n"
                    "        MetricsSummaryResponseCounters,\n"
                    "    )\n"
                    "    from ..models.metrics_summary_response_latencies_ms import (\n"
                    "        MetricsSummaryResponseLatenciesMs,\n"
                    "    )\n"
                ),
                new=(
                    "if TYPE_CHECKING:\n"
                    "    from nova_sdk_py_file.models.metrics_summary_response_activity import (\n"
                    "        MetricsSummaryResponseActivity,\n"
                    "    )\n"
                    "    from nova_sdk_py_file.models.metrics_summary_response_counters import (\n"
                    "        MetricsSummaryResponseCounters,\n"
                    "    )\n"
                    "    from nova_sdk_py_file.models.metrics_summary_response_latencies_ms import (\n"
                    "        MetricsSummaryResponseLatenciesMs,\n"
                    "    )\n"
                ),
                path="models/metrics_summary_response.py",
            )
            .replace(
                "from ..models.metrics_summary_response_activity import (\n",
                "from nova_sdk_py_file.models.metrics_summary_response_activity import (\n",
            )
            .replace(
                "from ..models.metrics_summary_response_counters import (\n",
                "from nova_sdk_py_file.models.metrics_summary_response_counters import (\n",
            )
            .replace(
                "from ..models.metrics_summary_response_latencies_ms import (\n",
                "from nova_sdk_py_file.models.metrics_summary_response_latencies_ms import (\n",
            )
        )

    _rewrite_file(
        root,
        "models/metrics_summary_response.py",
        patch_metrics_summary_response,
    )

    def patch_complete_upload_response(content: str) -> str:
        content = _replace_text(
            content,
            old="        etag (None | str | Unset):\n        version_id (None | str | Unset):\n",
            new=(
                "        etag (None | str | Unset): Entity tag for the completed object.\n"
                "        version_id (None | str | Unset): Version identifier when bucket versioning is enabled.\n"
            ),
            path="models/complete_upload_response.py",
            required=False,
        )
        content = _replace_text(
            content,
            old=(
                "        def _parse_etag(data: object) -> None | str | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(None | str | Unset, data)\n\n"
                '        etag = _parse_etag(d.pop("etag", UNSET))\n\n'
                "        def _parse_version_id(data: object) -> None | str | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(None | str | Unset, data)\n\n"
                '        version_id = _parse_version_id(d.pop("version_id", UNSET))\n'
            ),
            new=(
                "        def _parse_optional_string(data: object) -> None | str | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(None | str | Unset, data)\n\n"
                '        etag = _parse_optional_string(d.pop("etag", UNSET))\n'
                "        version_id = _parse_optional_string(\n"
                '            d.pop("version_id", UNSET)\n'
                "        )\n"
            ),
            path="models/complete_upload_response.py",
            required=False,
        )
        return content

    _rewrite_file(
        root,
        "models/complete_upload_response.py",
        patch_complete_upload_response,
    )

    def patch_initiate_upload_response(content: str) -> str:
        return _replace_text(
            content,
            old=(
                "        def _parse_part_size_bytes(data: object) -> int | None | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(int | None | Unset, data)\n\n"
                "        part_size_bytes = _parse_part_size_bytes(\n"
                '            d.pop("part_size_bytes", UNSET)\n'
                "        )\n\n"
                "        def _parse_upload_id(data: object) -> None | str | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(None | str | Unset, data)\n\n"
                '        upload_id = _parse_upload_id(d.pop("upload_id", UNSET))\n\n'
                "        def _parse_url(data: object) -> None | str | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(None | str | Unset, data)\n\n"
                '        url = _parse_url(d.pop("url", UNSET))\n'
            ),
            new=(
                "        def _parse_optional_int(data: object) -> int | None | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(int | None | Unset, data)\n\n"
                "        def _parse_optional_string(data: object) -> None | str | Unset:\n"
                "            if data is None:\n"
                "                return data\n"
                "            if isinstance(data, Unset):\n"
                "                return data\n"
                "            return cast(None | str | Unset, data)\n\n"
                "        part_size_bytes = _parse_optional_int(\n"
                '            d.pop("part_size_bytes", UNSET)\n'
                "        )\n"
                "        upload_id = _parse_optional_string(\n"
                '            d.pop("upload_id", UNSET)\n'
                "        )\n"
                '        url = _parse_optional_string(d.pop("url", UNSET))\n'
            ),
            path="models/initiate_upload_response.py",
            required=False,
        )

    _rewrite_file(
        root,
        "models/initiate_upload_response.py",
        patch_initiate_upload_response,
    )

    for rel_path in (
        "models/completed_part.py",
        "models/health_response.py",
        "models/job_event_data.py",
        "models/job_result_update_request.py",
    ):
        _rewrite_file(
            root,
            rel_path,
            lambda content: content.replace(
                "    def to_dict(self) -> dict[str, Any]:\n",
                "    def to_dict(self) -> dict[str, Any]:\n"
                '        """Serialize this model to a JSON-compatible dict."""\n',
            ).replace(
                "    @classmethod\n"
                "    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:\n",
                "    @classmethod\n"
                "    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:\n"
                '        """Build this model from a JSON-compatible mapping."""\n',
            ),
        )

    for rel_path, doc in (
        (
            "models/capability_descriptor_details.py",
            "Additional capability metadata map.",
        ),
        (
            "models/enqueue_job_request_payload.py",
            "Typed payload wrapper for enqueue-job requests.",
        ),
        (
            "models/job_record_payload.py",
            "Additional job payload fields returned by the API.",
        ),
        (
            "models/job_record_result_type_0.py",
            "Additional result metadata for job records.",
        ),
        (
            "models/readiness_response_checks.py",
            "Readiness dependency check status map.",
        ),
        (
            "models/metrics_summary_response_activity.py",
            "Low-cardinality activity metrics map.",
        ),
        (
            "models/metrics_summary_response_latencies_ms.py",
            "Latency metrics map with millisecond values.",
        ),
        (
            "models/job_event_data.py",
            "Event payload map for asynchronous job events.",
        ),
    ):
        _rewrite_file(
            root,
            rel_path,
            _docstring_transformer(doc),
        )

    _rewrite_file(
        root,
        "models/metrics_summary_response_activity.py",
        lambda content: content.replace(
            "        metrics_summary_response_activity.additional_properties = d\n",
            "        metrics_summary_response_activity.additional_properties = {\n"
            "            key: int(value) for key, value in d.items()\n"
            "        }\n",
        ),
    )
    _rewrite_file(
        root,
        "models/metrics_summary_response_latencies_ms.py",
        lambda content: content.replace(
            "        metrics_summary_response_latencies_ms.additional_properties = d\n",
            "        metrics_summary_response_latencies_ms.additional_properties = {\n"
            "            key: float(value) for key, value in d.items()\n"
            "        }\n",
        ),
    )


def _apply_repo_python_sdk_patches(root: Path) -> None:
    _patch_auth_sdk(root)
    _patch_file_sdk(root)


def _normalize_generated_tree(root: Path) -> None:
    _repair_missing_unset_imports(root)
    _rewrite_relative_imports_to_absolute(root)
    _apply_repo_python_sdk_patches(root)
    _add_generated_ruff_noqa(root)
    _run_ruff(args=["check", "--select", "I", "--fix"], root=root)
    _run_ruff(args=["format"], root=root)


def _sync_generated_tree(source_root: Path, destination_root: Path) -> None:
    _remove_ignored_paths(destination_root)
    source_files = _collect_file_map(source_root)
    destination_files = _collect_file_map(destination_root)

    for rel_path in sorted(destination_files.keys() - source_files.keys()):
        (destination_root / rel_path).unlink()

    for rel_path, content in source_files.items():
        destination = destination_root / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        current_content = (
            destination.read_bytes() if destination.exists() else None
        )
        if current_content != content:
            destination.write_bytes(content)

    for path in sorted(destination_root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def _write_or_check(target: GenerationTarget, *, check: bool) -> list[str]:
    issues: list[str] = []
    with TemporaryDirectory() as temp_dir:
        generated_root = _generate_target(
            target=target,
            temp_root=Path(temp_dir),
        )
        _normalize_generated_tree(generated_root)
        generated_files = _collect_file_map(generated_root)
        current_files = _collect_file_map(target.output_path)

        if check:
            if generated_files != current_files:
                issues.append(
                    "stale generated python client artifact: "
                    f"{target.output_path}"
                )
            return issues

        target.output_path.mkdir(parents=True, exist_ok=True)
        _sync_generated_tree(generated_root, target.output_path)
    return issues


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for committed Python SDK generation.

    Returns:
        argparse.Namespace: Parsed CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate committed Python SDKs from OpenAPI.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed Python SDK artifacts are stale.",
    )
    return parser.parse_args()


def main() -> int:
    """Generate committed Python SDK sources or fail on drift.

    Returns:
        int: Process exit code (0 on success, 1 on drift/failure).
    """
    args = parse_args()
    issues: list[str] = []
    for target in TARGETS:
        issues.extend(_write_or_check(target, check=args.check))

    if issues:
        for issue in issues:
            print(issue)
        return 1

    message = (
        "generated python client artifacts are current"
        if args.check
        else "generated python client artifacts updated"
    )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
