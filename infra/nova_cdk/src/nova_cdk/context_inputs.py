"""Shared CDK context and environment input parsing helpers."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from constructs import Construct


def parse_string_list(raw: object | None, *, key: str) -> list[str]:
    """Normalize a string/list input into a non-empty string list.

    Args:
        raw: Raw context or environment input to normalize.
        key: Configuration key used in error messages.

    Returns:
        A list of stripped strings, or an empty list for blank input.

    Raises:
        TypeError: If the input cannot be interpreted as a string list.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return []
        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise TypeError(f"{key} JSON input is malformed.") from exc
            if not isinstance(parsed, list):
                raise TypeError(f"{key} JSON input must decode to a list.")
            return parse_string_list(parsed, key=key)
        return [
            item
            for item in (candidate.strip() for candidate in value.split(","))
            if item
        ]
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    raise TypeError(f"{key} must be a string or a list of strings.")


def optional_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> object | None:
    """Return one optional context or environment value.

    Args:
        scope: CDK construct used to read context values.
        env_var: Environment variable name to check after context lookup.
        key: Context key used to read the construct metadata.

    Returns:
        The raw context or environment value, or ``None`` when unset.
    """
    raw: object | None = scope.node.try_get_context(key)
    if raw is None:
        raw = os.environ.get(env_var)
    return raw


def required_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> str:
    """Return one required non-blank context or environment value.

    Args:
        scope: CDK construct used to read context values.
        env_var: Environment variable name to check after context lookup.
        key: Context key used to read the construct metadata.

    Returns:
        A stripped, non-empty string value.

    Raises:
        ValueError: If neither context nor environment provides a value.
    """
    raw = optional_context_or_env_value(scope, env_var=env_var, key=key)
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            return value
    raise ValueError(f"Missing required value for {key}.")


def numeric_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
    default: int | float,
    allow_float: bool = False,
    minimum: int | float = 1,
) -> int | float:
    """Return one validated numeric context or environment value.

    Args:
        scope: CDK construct used to read context values.
        env_var: Environment variable name to check after context lookup.
        key: Context key used to read the construct metadata.
        default: Fallback value when the input is unset or blank.
        allow_float: Whether floating-point values are allowed.
        minimum: Smallest allowed numeric value.

    Returns:
        The validated numeric value, coerced to ``int`` or ``float``.

    Raises:
        TypeError: If the input is neither string nor numeric.
        ValueError: If the input is not numeric or is below ``minimum``.
    """
    raw = optional_context_or_env_value(scope, env_var=env_var, key=key)
    if raw is None:
        return default
    if isinstance(raw, str):
        value_text = raw.strip()
        if not value_text:
            return default
        try:
            value: int | float = (
                float(value_text) if allow_float else int(value_text)
            )
        except ValueError as exc:
            raise ValueError(
                f"{key} must be a numeric value, got {value_text!r}."
            ) from exc
    elif isinstance(raw, (int, float)):
        value = float(raw) if allow_float else int(raw)
    else:
        raise TypeError(f"{key} must be numeric.")
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}.")
    return value


def sha256_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> str:
    """Return one required lowercase SHA-256 digest from context or env.

    Args:
        scope: CDK construct used to read context values.
        env_var: Environment variable name to check after context lookup.
        key: Context key used to read the construct metadata.

    Returns:
        A lowercase 64-character SHA-256 digest.

    Raises:
        ValueError: If the digest is missing or malformed.
    """
    value = required_context_or_env_value(scope, env_var=env_var, key=key)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{key} must be a lowercase 64-character SHA-256.")
    return value


def parse_bool_flag(
    raw: Any,
    *,
    key: str,
) -> bool:
    """Return one normalized boolean flag value.

    Args:
        raw: Raw value to normalize.
        key: Configuration key used in error messages.

    Returns:
        ``True`` or ``False`` for accepted boolean inputs.

    Raises:
        ValueError: If the input is not a recognized boolean value.
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{key} must be a boolean value.")
