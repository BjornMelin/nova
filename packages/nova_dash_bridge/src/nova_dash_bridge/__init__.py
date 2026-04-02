"""Top-level package for browser and Dash helpers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ._version import __version__

if TYPE_CHECKING:
    from .dash_integration import (
        BearerAuthHeader,
        FileTransferAssets,
        S3FileUploader,
    )

_OPTIONAL_EXPORTS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "BearerAuthHeader": (
        "nova_dash_bridge.dash_integration",
        ("dash",),
        "dash",
    ),
    "FileTransferAssets": (
        "nova_dash_bridge.dash_integration",
        ("dash",),
        "dash",
    ),
    "S3FileUploader": (
        "nova_dash_bridge.dash_integration",
        ("dash",),
        "dash",
    ),
}


def __getattr__(name: str) -> Any:
    """Lazily expose adapter exports that require optional dependencies."""
    target = _OPTIONAL_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, dependencies, extra = target
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        missing_name = exc.name or ""
        if not missing_name and exc.args:
            missing_name = str(exc.args[0]).replace("No module named ", "")
            missing_name = missing_name.strip("'\"")
        missing = missing_name.split(".", maxsplit=1)[0]
        if missing in dependencies:
            dep_list = ", ".join(dependencies)
            raise ModuleNotFoundError(
                f"Optional dependencies missing for {name!r}: {dep_list}. "
                "Install with "
                f"`pip install nova-dash-bridge[{extra}]`."
            ) from exc
        raise

    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return module attributes including lazy optional exports."""
    return sorted(set(globals()) | set(_OPTIONAL_EXPORTS))


__all__ = [
    "BearerAuthHeader",
    "FileTransferAssets",
    "S3FileUploader",
    "__version__",
]
