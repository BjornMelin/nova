"""Top-level package for nova-dash-bridge."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ._version import __version__
from .config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
    policy_from_env,
)
from .s3_client import S3ClientFactory
from .service import AsyncFileTransferService, FileTransferService

if TYPE_CHECKING:
    from .dash_integration import FileTransferAssets, S3FileUploader
    from .fastapi_integration import create_fastapi_app, create_fastapi_router
    from .flask_integration import (
        create_file_transfer_blueprint,
        register_file_transfer_assets,
        register_file_transfer_blueprint,
    )

_OPTIONAL_EXPORTS: dict[str, tuple[str, tuple[str, ...], str]] = {
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
    "create_fastapi_app": (
        "nova_dash_bridge.fastapi_integration",
        ("fastapi", "starlette"),
        "fastapi",
    ),
    "create_fastapi_router": (
        "nova_dash_bridge.fastapi_integration",
        ("fastapi", "starlette"),
        "fastapi",
    ),
    "create_file_transfer_blueprint": (
        "nova_dash_bridge.flask_integration",
        ("flask",),
        "flask",
    ),
    "register_file_transfer_assets": (
        "nova_dash_bridge.flask_integration",
        ("flask",),
        "flask",
    ),
    "register_file_transfer_blueprint": (
        "nova_dash_bridge.flask_integration",
        ("flask",),
        "flask",
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
    "AsyncFileTransferService",
    "AuthPolicy",
    "FileTransferAssets",
    "FileTransferEnvConfig",
    "FileTransferService",
    "S3ClientFactory",
    "S3FileUploader",
    "UploadPolicy",
    "__version__",
    "create_fastapi_app",
    "create_fastapi_router",
    "create_file_transfer_blueprint",
    "policy_from_env",
    "register_file_transfer_assets",
    "register_file_transfer_blueprint",
]
