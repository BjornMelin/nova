#!/usr/bin/env bash
set -euo pipefail

echo "Verifying canonical route references and literals..."
REQUIRED_LITERALS=(
  "/v1/transfers/uploads/initiate"
  "/v1/transfers/uploads/sign-parts"
  "/v1/transfers/uploads/complete"
  "/v1/transfers/uploads/abort"
  "/v1/transfers/downloads/presign"
  "/v1/exports"
  "/v1/exports/{export_id}"
  "/v1/exports/{export_id}/cancel"
  "/v1/capabilities"
  "/v1/resources/plan"
  "/v1/releases/info"
  "/v1/health/live"
  "/v1/health/ready"
  "/metrics/summary"
)
ROUTE_LITERAL_PATTERN="/v1/exports/\\{export_id\\}/cancel"
ROUTE_LITERAL_PATTERN_ALT="/exports/\\{export_id\\}/cancel"
RUNTIME_PATHS=(
  "packages/nova_file_api/src"
  "packages/nova_dash_bridge/src"
)
RG_PATH_EXCLUDES=(
  --glob '!**/tests/**'
  --glob '!**/fixtures/**'
)

if command -v rg >/dev/null 2>&1; then
  echo "Using rg to validate route references."
  for literal in "${REQUIRED_LITERALS[@]}"; do
    found_literal=0
    literal_candidates=("$literal")
    if [[ "$literal" == /v1/transfers/* ]]; then
      literal_candidates+=("${literal#/v1/transfers}")
    fi
    if [[ "$literal" == /v1/* ]]; then
      literal_candidates+=("${literal#/v1}")
    fi
    for candidate in "${literal_candidates[@]}"; do
      if rg -n -F "${RG_PATH_EXCLUDES[@]}" "$candidate" "${RUNTIME_PATHS[@]}" >/dev/null; then
        found_literal=1
        break
      fi
    done
    if [[ "$found_literal" -ne 1 ]]; then
      echo "::error::Required canonical route literal not found: $literal"
      exit 1
    fi
  done
  rg -n "${RG_PATH_EXCLUDES[@]}" "($ROUTE_LITERAL_PATTERN|$ROUTE_LITERAL_PATTERN_ALT)" "${RUNTIME_PATHS[@]}" || {
    echo "::error::Required regex route literal not found: $ROUTE_LITERAL_PATTERN"
    exit 1
  }
  if rg -n "/api/|/healthz|/readyz" "${RUNTIME_PATHS[@]}"; then
    echo "::error::Forbidden legacy runtime route references detected."
    exit 1
  fi
else
  echo "Using grep to validate route references."
  for literal in "${REQUIRED_LITERALS[@]}"; do
    found_literal=0
    literal_candidates=("$literal")
    if [[ "$literal" == /v1/transfers/* ]]; then
      literal_candidates+=("${literal#/v1/transfers}")
    fi
    if [[ "$literal" == /v1/* ]]; then
      literal_candidates+=("${literal#/v1}")
    fi
    for candidate in "${literal_candidates[@]}"; do
      if grep -RIn --fixed-strings \
        --exclude-dir=tests \
        --exclude-dir=fixtures \
        "$candidate" "${RUNTIME_PATHS[@]}" >/dev/null; then
        found_literal=1
        break
      fi
    done
    if [[ "$found_literal" -ne 1 ]]; then
      echo "::error::Required canonical route literal not found: $literal"
      exit 1
    fi
  done
  grep -RInE \
    --exclude-dir=tests \
    --exclude-dir=fixtures \
    "($ROUTE_LITERAL_PATTERN|$ROUTE_LITERAL_PATTERN_ALT)" "${RUNTIME_PATHS[@]}" || {
      echo "::error::Required regex route literal not found: $ROUTE_LITERAL_PATTERN"
      exit 1
    }
  if grep -RInE "/api/|/healthz|/readyz" "${RUNTIME_PATHS[@]}"; then
    echo "::error::Forbidden legacy runtime route references detected."
    exit 1
  fi
fi

uv run python - <<'PY'
from __future__ import annotations

import ast
import sys
from pathlib import Path

runtime_roots = [
    Path("packages/nova_file_api/src/nova_file_api"),
]
files: list[Path] = []
for runtime_root in runtime_roots:
    routes_dir = runtime_root / "routes"
    app_file = runtime_root / "app.py"
    if not app_file.is_file():
        print(f"::error::missing runtime app module: {app_file}")
        sys.exit(1)
    if not routes_dir.is_dir():
        print(f"::error::missing runtime routes directory: {routes_dir}")
        sys.exit(1)
    files.extend([app_file, *sorted(routes_dir.glob("*.py"))])
methods = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
    "api_route",
}
violations: list[str] = []

for file in files:
    content = file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file))
    prefixes: dict[str, str] = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        if not isinstance(value.func, ast.Name):
            continue
        if value.func.id != "APIRouter":
            continue
        for keyword in value.keywords:
            if (
                keyword.arg == "prefix"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                prefixes[target.id] = keyword.value.value

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in methods:
                continue
            if not isinstance(func.value, ast.Name):
                continue

            route_path: str | None = None
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                first_arg = decorator.args[0]
                if isinstance(first_arg.value, str):
                    route_path = first_arg.value
            if not route_path:
                for keyword in decorator.keywords:
                    if (
                        keyword is not None
                        and keyword.arg == "path"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        route_path = keyword.value.value
                        break

            if not route_path:
                continue

            prefix = prefixes.get(func.value.id, "")
            full_path = f"{prefix}{route_path}" if prefix else route_path
            if full_path != "/metrics/summary" and not full_path.startswith("/v1/"):
                violations.append(
                    f"{file}:{node.name}:{func.value.id}:{route_path} -> {full_path}"
                )

if violations:
    print("::error::Route decorator policy violation detected:")
    for violation in violations:
        print(violation)
    sys.exit(1)
PY

uv run python - <<'PY'
from __future__ import annotations

import sys

from nova_file_api.app import create_app
from nova_file_api.config import Settings


def validate_openapi_paths(schema: dict, app_label: str) -> None:
    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        print(f"::error::{app_label} OpenAPI paths payload is not a mapping.")
        sys.exit(1)

    invalid_paths = [
        path for path in paths if path != "/metrics/summary" and not path.startswith("/v1/")
    ]
    if invalid_paths:
        print(f"::error::{app_label} OpenAPI path policy violation detected:")
        for path in sorted(invalid_paths):
            print(path)
        sys.exit(1)

    operation_ids: set[str] = set()
    duplicates: set[str] = set()
    for path_methods in paths.values():
        if not isinstance(path_methods, dict):
            continue
        for operation in path_methods.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str):
                continue
            if operation_id in operation_ids:
                duplicates.add(operation_id)
            operation_ids.add(operation_id)

    if duplicates:
        print(f"::error::{app_label} Duplicate OpenAPI operationId values detected:")
        for operation_id in sorted(duplicates):
            print(operation_id)
        sys.exit(1)


validate_openapi_paths(
    create_app(
        settings=Settings.model_validate({"IDEMPOTENCY_ENABLED": False})
    ).openapi(),
    "nova_file_api",
)
PY
uv run python scripts/contracts/export_openapi.py --check
echo "Canonical route policy guard check passed."
