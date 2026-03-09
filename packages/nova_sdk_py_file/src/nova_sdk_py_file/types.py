# ruff: noqa
"""Shared type helpers used by generated SDK client modules."""

from collections.abc import Mapping, MutableMapping
from typing import IO, BinaryIO, Generic, Literal, TypeVar

from attrs import define


class Unset:
    """Sentinel type representing an omitted field value."""

    def __bool__(self) -> Literal[False]:
        """Always evaluate UNSET as False in conditional checks."""
        return False


UNSET: Unset = Unset()

# The types that `httpx.Client(files=)` can accept, copied from that library.
FileContent = IO[bytes] | bytes | str
FileTypes = (
    # (filename, file (or bytes), content_type)
    tuple[str | None, FileContent, str | None]
    # (filename, file (or bytes), content_type, headers)
    | tuple[str | None, FileContent, str | None, Mapping[str, str]]
)
RequestFiles = list[tuple[str, FileTypes]]


@define
class File:
    """Container for multipart file upload metadata."""

    payload: BinaryIO
    file_name: str | None = None
    mime_type: str | None = None

    def to_tuple(self) -> FileTypes:
        """Build the tuple representation accepted by `httpx` multipart uploads."""
        return self.file_name, self.payload, self.mime_type


T = TypeVar("T")


@define
class Response(Generic[T]):
    """Standard parsed HTTP response wrapper returned by generated helpers."""

    status_code: int
    content: bytes
    headers: MutableMapping[str, str]
    parsed: T | None


__all__ = ["UNSET", "File", "FileTypes", "RequestFiles", "Response", "Unset"]
