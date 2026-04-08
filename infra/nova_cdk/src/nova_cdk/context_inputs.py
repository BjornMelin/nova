"""Shared CDK context and environment input parsing helpers."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from constructs import Construct


def parse_string_list(raw: object | None, *, key: str) -> list[str]:
    """Normalize a string/list input into a non-empty string list."""
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
    """Return one optional context or environment value."""
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
    """Return one required non-blank context or environment value."""
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
    """Return one validated numeric context or environment value."""
    raw = optional_context_or_env_value(scope, env_var=env_var, key=key)
    if raw is None:
        return default
    if isinstance(raw, str):
        value_text = raw.strip()
        if not value_text:
            return default
        value: int | float = (
            float(value_text) if allow_float else int(value_text)
        )
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
    """Return one required lowercase SHA-256 digest from context or env."""
    value = required_context_or_env_value(scope, env_var=env_var, key=key)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{key} must be a lowercase 64-character SHA-256.")
    return value


def parse_bool_flag(
    raw: Any,
    *,
    key: str,
) -> bool:
    """Return one normalized boolean flag value."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{key} must be a boolean value.")
