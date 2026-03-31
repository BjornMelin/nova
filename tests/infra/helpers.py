"""Shared test helpers for infrastructure contract tests."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(rel_path: str) -> str:
    """Read a repository-relative file path.

    Args:
        rel_path: Repository-relative path to read.

    Returns:
        The file contents as UTF-8 text.
    """
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def load_repo_module(module_name: str, rel_path: str) -> ModuleType:
    """Load a repository module from a repository-relative file path.

    Args:
        module_name: Repository module name to assign.
        rel_path: Repository-relative file path to load.

    Returns:
        The loaded module object.

    Raises:
        FileNotFoundError: If the path does not exist.
        ImportError: If the module cannot be loaded or executed.
    """
    module_path = REPO_ROOT / rel_path
    if not module_path.is_file():
        raise FileNotFoundError(f"Expected module file to exist: {module_path}")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def load_repo_package_module(
    module_name: str,
    package_root_rel_path: str,
) -> ModuleType:
    """Import a repository package module after adding its root to ``sys.path``.

    Args:
        module_name: Importable package module path.
        package_root_rel_path: Repository-relative package root directory.

    Returns:
        The imported module object.

    Raises:
        FileNotFoundError: If the package root does not exist.
    """
    package_root = REPO_ROOT / package_root_rel_path
    if not package_root.is_dir():
        raise FileNotFoundError(
            f"Expected package root to exist: {package_root}"
        )
    package_root_text = str(package_root)
    if package_root_text not in sys.path:
        sys.path.insert(0, package_root_text)
    return importlib.import_module(module_name)


def section_text(text: str, start_marker: str, end_marker: str) -> str:
    """Extract a substring from a template between two literal markers.

    Args:
        text: Full file or block content to search.
        start_marker: Substring marking the inclusive start of the section.
        end_marker: Substring searched for after ``start_marker``; the returned
            slice ends before this marker.

    Returns:
        The substring of ``text`` from ``start_marker`` through the character
        before the first ``end_marker`` after ``start_marker``.

    Raises:
        AssertionError: If ``start_marker`` or ``end_marker`` is not found at
            the expected positions (enforced via assertions below).
    """
    start = text.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"
    end = text.find(end_marker, start)
    assert end != -1, f"Missing section terminator: {end_marker}"
    return text[start:end]


def runtime_stack_context_for_region(region: str) -> dict[str, str]:
    """Return the minimum valid runtime-stack context for one AWS region.

    Args:
        region: AWS region used to synthesize the runtime stack.

    Returns:
        The minimum valid runtime-stack context for one region.
    """
    return {
        "api_domain_name": "api.dev.example.com",
        "api_lambda_artifact_bucket": (
            "nova-ci-artifacts-111111111111-us-east-1"
        ),
        "api_lambda_artifact_key": (
            "runtime/nova-file-api/"
            "01234567-89ab-cdef-0123-456789abcdef/"
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/"
            "nova-file-api-lambda.zip"
        ),
        "api_lambda_artifact_sha256": (
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "certificate_arn": (
            f"arn:aws:acm:{region}:111111111111:"
            "certificate/12345678-1234-1234-1234-123456789012"
        ),
        "hosted_zone_id": "Z1234567890EXAMPLE",
        "hosted_zone_name": "example.com",
        "jwt_audience": "api://nova",
        "jwt_issuer": "https://issuer.example.com/",
        "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
    }


def runtime_stack_template_json(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
    stack_name: str = "RuntimeContractStack",
) -> dict[str, Any]:
    """Return the synthesized runtime stack template JSON.

    Args:
        context: Optional CDK context override for stack synthesis.
        region: AWS region used to synthesize the runtime stack.
        stack_name: Logical stack name to use during synthesis.

    Returns:
        The synthesized runtime stack template rendered as JSON.
    """
    runtime_stack_module = load_repo_package_module(
        "nova_cdk.runtime_stack",
        "infra/nova_cdk/src",
    )
    nova_runtime_stack = runtime_stack_module.NovaRuntimeStack
    app = App(context=context or runtime_stack_context_for_region(region))
    stack = nova_runtime_stack(
        app,
        stack_name,
        env=Environment(account="111111111111", region=region),
    )
    return cast(dict[str, Any], Template.from_stack(stack).to_json())


def resources_of_type(
    resources: dict[str, Any],
    type_name: str,
) -> dict[str, dict[str, Any]]:
    """Return all CloudFormation resources for one type.

    Args:
        resources: Synthesized CloudFormation resources keyed by logical id.
        type_name: CloudFormation resource type to select.

    Returns:
        The subset of resources whose ``Type`` matches ``type_name``.
    """
    return {
        logical_id: resource
        for logical_id, resource in resources.items()
        if resource["Type"] == type_name
    }
