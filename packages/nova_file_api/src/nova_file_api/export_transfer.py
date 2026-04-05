"""Shared export-copy transfer service for workflow handlers."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.export_utils import (
    COPY_OBJECT_MAX_BYTES,
    build_export_object_key,
    multipart_copy_create_upload_kwargs,
    multipart_copy_part_size_bytes,
    sanitize_filename,
)
from nova_file_api.s3_coercion import (
    copy_part_etag,
    normalize_prefix,
    opt_str,
    parse_non_negative_int,
)


@dataclass(slots=True, frozen=True, kw_only=True)
class ExportTransferConfig:
    """Transfer configuration required by export workflow handlers.

    ``part_size_bytes`` mirrors the general transfer multipart default
    (``FILE_TRANSFER_PART_SIZE_BYTES``). Export S3 multipart *copy* chunking
    uses ``copy_part_size_bytes``
    (``FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES``).
    """

    bucket: str
    upload_prefix: str
    export_prefix: str
    tmp_prefix: str
    part_size_bytes: int
    max_concurrency: int
    copy_part_size_bytes: int
    copy_max_concurrency: int
    large_copy_worker_threshold_bytes: int


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
        self._upload_prefix = normalize_prefix(self.config.upload_prefix)
        self._export_prefix = normalize_prefix(self.config.export_prefix)
        self._tmp_prefix = normalize_prefix(self.config.tmp_prefix)

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
        download_filename = sanitize_filename(filename or Path(source_key).name)
        export_key = build_export_object_key(
            export_prefix=self._export_prefix,
            scope_id=scope_id,
            export_id=export_id,
            filename=download_filename,
        )
        source_size_bytes = parse_non_negative_int(
            source_object.get("ContentLength"),
            error_message="source upload object is missing content length",
            err=RuntimeError,
        )
        try:
            if source_size_bytes <= COPY_OBJECT_MAX_BYTES:
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
        part_size_bytes = multipart_copy_part_size_bytes(
            source_size_bytes=source_size_bytes,
            preferred_part_size_bytes=self.config.copy_part_size_bytes,
        )
        try:
            output = await self._s3.create_multipart_upload(
                **multipart_copy_create_upload_kwargs(
                    bucket=self.config.bucket,
                    key=export_key,
                    source_object=source_object,
                )
            )
            upload_id = opt_str(output.get("UploadId"))
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
                self.config.copy_max_concurrency,
            ):
                batch = ranges[
                    start_index : start_index + self.config.copy_max_concurrency
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
            "ETag": copy_part_etag(response, err=RuntimeError),
            "PartNumber": part_number,
        }

    def _assert_upload_scope(self, *, key: str, scope_id: str) -> None:
        expected_prefix = f"{self._upload_prefix}{scope_id}/"
        if not key.startswith(expected_prefix):
            raise ValueError("key is outside caller upload scope")
