"""Shared export-copy transfer service for workflow handlers."""

from __future__ import annotations

import asyncio
import math
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

_COPY_OBJECT_MAX_BYTES = 5_000_000_000
_MAX_MULTIPART_PARTS = 10_000
_MIN_MULTIPART_PART_SIZE_BYTES = 5 * 1024 * 1024
_MAX_MULTIPART_PART_SIZE_BYTES = 5 * 1024 * 1024 * 1024


@dataclass(slots=True, frozen=True, kw_only=True)
class ExportTransferConfig:
    """Transfer configuration required by export workflow handlers."""

    bucket: str
    upload_prefix: str
    export_prefix: str
    tmp_prefix: str
    part_size_bytes: int
    max_concurrency: int


@dataclass(slots=True, frozen=True)
class ExportCopyResult:
    """Result returned after copying an upload object to the export prefix."""

    export_key: str
    download_filename: str


class ExportTransferService(Protocol):
    """Minimal transfer surface required by workflow handlers."""

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """Copy a scoped upload object into the export prefix."""


class S3ExportTransferService:
    """S3-backed implementation of the workflow export-copy seam."""

    def __init__(
        self,
        *,
        config: ExportTransferConfig,
        s3_client: Any,
    ) -> None:
        """Initialize the export-copy service with config and S3 client."""
        self.config = config
        self._s3 = s3_client
        self._upload_prefix = _normalize_prefix(self.config.upload_prefix)
        self._export_prefix = _normalize_prefix(self.config.export_prefix)
        self._tmp_prefix = _normalize_prefix(self.config.tmp_prefix)

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """Copy a caller-scoped upload object into the export prefix."""
        if source_bucket != self.config.bucket:
            raise ValueError("bucket does not match configured transfer bucket")
        self._assert_upload_scope(key=source_key, scope_id=scope_id)
        source_object = await self._head_object(
            bucket=self.config.bucket,
            key=source_key,
            missing_message="source upload object not found",
            failure_message="failed to inspect source upload object",
        )
        download_filename = _sanitize_filename(
            filename or Path(source_key).name
        )
        export_key = self._new_export_key(
            scope_id=scope_id,
            export_id=export_id,
            filename=download_filename,
        )
        source_size_bytes = _require_non_negative_int(
            source_object.get("ContentLength"),
            error_message="source upload object is missing content length",
        )
        try:
            if source_size_bytes <= _COPY_OBJECT_MAX_BYTES:
                await self._s3.copy_object(
                    Bucket=self.config.bucket,
                    CopySource={
                        "Bucket": self.config.bucket,
                        "Key": source_key,
                    },
                    Key=export_key,
                    MetadataDirective="COPY",
                )
            else:
                await self._multipart_copy_upload_to_export(
                    source_key=source_key,
                    export_key=export_key,
                    source_size_bytes=source_size_bytes,
                    source_object=source_object,
                )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ValueError("source upload object not found") from exc
            raise RuntimeError(
                "failed to copy upload object to export key"
            ) from exc
        except BotoCoreError as exc:
            raise RuntimeError(
                "failed to copy upload object to export key"
            ) from exc
        return ExportCopyResult(
            export_key=export_key,
            download_filename=download_filename,
        )

    async def _head_object(
        self,
        *,
        bucket: str,
        key: str,
        missing_message: str,
        failure_message: str,
    ) -> dict[str, Any]:
        try:
            output = await self._s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ValueError(missing_message) from exc
            raise RuntimeError(failure_message) from exc
        except BotoCoreError as exc:
            raise RuntimeError(failure_message) from exc
        return cast(dict[str, Any], output)

    async def _multipart_copy_upload_to_export(
        self,
        *,
        source_key: str,
        export_key: str,
        source_size_bytes: int,
        source_object: dict[str, Any],
    ) -> None:
        upload_id: str | None = None
        part_size_bytes = _multipart_copy_part_size_bytes(
            source_size_bytes=source_size_bytes,
            preferred_part_size_bytes=self.config.part_size_bytes,
        )
        try:
            output = await self._s3.create_multipart_upload(
                **_multipart_copy_create_upload_kwargs(
                    bucket=self.config.bucket,
                    key=export_key,
                    source_object=source_object,
                )
            )
            upload_id = _opt_str(output.get("UploadId"))
            if upload_id is None:
                raise RuntimeError(
                    "multipart export copy response missing upload id"
                )

            completed_parts: list[dict[str, Any]] = []
            ranges = [
                (
                    part_number,
                    start_byte,
                    min(
                        source_size_bytes - 1,
                        start_byte + part_size_bytes - 1,
                    ),
                )
                for part_number, start_byte in enumerate(
                    range(0, source_size_bytes, part_size_bytes),
                    start=1,
                )
            ]
            for start_index in range(
                0,
                len(ranges),
                self.config.max_concurrency,
            ):
                batch = ranges[
                    start_index : start_index + self.config.max_concurrency
                ]
                completed_parts.extend(
                    await asyncio.gather(
                        *[
                            self._copy_multipart_export_part(
                                source_key=source_key,
                                export_key=export_key,
                                upload_id=upload_id,
                                part_number=part_number,
                                start_byte=start_byte,
                                end_byte=end_byte,
                            )
                            for part_number, start_byte, end_byte in batch
                        ]
                    )
                )

            await self._s3.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=export_key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": sorted(
                        completed_parts,
                        key=lambda item: int(item["PartNumber"]),
                    )
                },
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if upload_id is not None:
                with suppress(ClientError, BotoCoreError):
                    await self._s3.abort_multipart_upload(
                        Bucket=self.config.bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ValueError("source upload object not found") from exc
            raise RuntimeError(
                "failed to copy upload object to export key"
            ) from exc
        except BotoCoreError as exc:
            if upload_id is not None:
                with suppress(ClientError, BotoCoreError):
                    await self._s3.abort_multipart_upload(
                        Bucket=self.config.bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            raise RuntimeError(
                "failed to copy upload object to export key"
            ) from exc

    async def _copy_multipart_export_part(
        self,
        *,
        source_key: str,
        export_key: str,
        upload_id: str,
        part_number: int,
        start_byte: int,
        end_byte: int,
    ) -> dict[str, Any]:
        response = await self._s3.upload_part_copy(
            Bucket=self.config.bucket,
            CopySource={
                "Bucket": self.config.bucket,
                "Key": source_key,
            },
            CopySourceRange=f"bytes={start_byte}-{end_byte}",
            Key=export_key,
            PartNumber=part_number,
            UploadId=upload_id,
        )
        return {
            "ETag": _copy_part_etag(response),
            "PartNumber": part_number,
        }

    def _new_export_key(
        self,
        *,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> str:
        stable_export_id = "".join(
            character
            for character in export_id.strip()
            if character.isalnum() or character in {"-", "_"}
        )
        if not stable_export_id:
            stable_export_id = uuid4().hex
        return f"{self._export_prefix}{scope_id}/{stable_export_id}/{filename}"

    def _assert_upload_scope(self, *, key: str, scope_id: str) -> None:
        expected_prefix = f"{self._upload_prefix}{scope_id}/"
        if not key.startswith(expected_prefix):
            raise ValueError("key is outside caller upload scope")


def _sanitize_filename(filename: str) -> str:
    base_name = Path(filename).name
    cleaned = "".join(
        character
        for character in base_name
        if character.isalnum() or character in {".", "-", "_"}
    )
    if not cleaned:
        return "file"
    if len(cleaned) > 255:
        return cleaned[:255]
    return cleaned


def _normalize_prefix(prefix: str) -> str:
    normalized = prefix.strip()
    if not normalized:
        return ""
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def _opt_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _require_non_negative_int(value: Any, *, error_message: str) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    raise RuntimeError(error_message)


def _copy_part_etag(response: dict[str, Any]) -> str:
    copy_result = response.get("CopyPartResult")
    if not isinstance(copy_result, dict):
        raise TypeError("multipart export copy part result is missing")
    etag = _opt_str(copy_result.get("ETag"))
    if etag is None:
        raise RuntimeError("multipart export copy part etag is missing")
    return etag


def _multipart_copy_part_size_bytes(
    *,
    source_size_bytes: int,
    preferred_part_size_bytes: int,
) -> int:
    return min(
        _MAX_MULTIPART_PART_SIZE_BYTES,
        max(
            preferred_part_size_bytes,
            _MIN_MULTIPART_PART_SIZE_BYTES,
            math.ceil(source_size_bytes / _MAX_MULTIPART_PARTS),
        ),
    )


def _multipart_copy_create_upload_kwargs(
    *,
    bucket: str,
    key: str,
    source_object: dict[str, Any],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key}
    for field in (
        "CacheControl",
        "ContentDisposition",
        "ContentEncoding",
        "ContentLanguage",
        "ContentType",
        "Expires",
        "Metadata",
    ):
        value = source_object.get(field)
        if value is not None:
            kwargs[field] = value
    return kwargs
