"""Export-copy collaborator for transfer-owned S3 objects."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.errors import invalid_request, upstream_s3_error
from nova_file_api.export_transfer import ExportCopyResult
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
from nova_file_api.transfer_config import TransferConfig


def _upstream_s3_err(message: str) -> Exception:
    return upstream_s3_error(message)


class ExportCopyCoordinator:
    """Own copies from caller upload scope into export object scope."""

    def __init__(self, *, config: TransferConfig, s3_client: Any) -> None:
        """Initialize export-copy coordination with transfer config and S3."""
        self._config = config
        self._s3 = s3_client
        self._upload_prefix = normalize_prefix(config.upload_prefix)
        self._export_prefix = normalize_prefix(config.export_prefix)

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """Copy one caller-scoped upload object into the export prefix."""
        if source_bucket != self._config.bucket:
            raise invalid_request(
                "bucket does not match configured transfer bucket",
                details={
                    "bucket": source_bucket,
                    "expected_bucket": self._config.bucket,
                },
            )
        self._assert_upload_scope(key=source_key, scope_id=scope_id)
        source_object = await self._head_object(
            bucket=self._config.bucket,
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
            err=_upstream_s3_err,
        )
        try:
            if source_size_bytes <= COPY_OBJECT_MAX_BYTES:
                await self._s3.copy_object(
                    Bucket=self._config.bucket,
                    CopySource={
                        "Bucket": self._config.bucket,
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
                raise invalid_request("source upload object not found") from exc
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc
        except BotoCoreError as exc:
            raise upstream_s3_error(
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
            return cast(dict[str, Any], output)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise invalid_request(missing_message) from exc
            raise upstream_s3_error(failure_message) from exc
        except BotoCoreError as exc:
            raise upstream_s3_error(failure_message) from exc

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
            preferred_part_size_bytes=self._config.export_copy_part_size_bytes,
        )
        try:
            create_upload_kwargs = multipart_copy_create_upload_kwargs(
                bucket=self._config.bucket,
                key=export_key,
                source_object=source_object,
            )
            output = await self._s3.create_multipart_upload(
                **create_upload_kwargs
            )
            upload_id = opt_str(output.get("UploadId"))
            if upload_id is None:
                raise upstream_s3_error(
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
            copy_concurrency = min(
                self._config.export_copy_max_concurrency,
                self._config.max_concurrency,
            )
            for start_index in range(0, len(ranges), copy_concurrency):
                batch = ranges[start_index : start_index + copy_concurrency]
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
                Bucket=self._config.bucket,
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
                        Bucket=self._config.bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise invalid_request("source upload object not found") from exc
            raise upstream_s3_error(
                "failed to copy upload object to export key"
            ) from exc
        except BotoCoreError as exc:
            if upload_id is not None:
                with suppress(ClientError, BotoCoreError):
                    await self._s3.abort_multipart_upload(
                        Bucket=self._config.bucket,
                        Key=export_key,
                        UploadId=upload_id,
                    )
            raise upstream_s3_error(
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
            Bucket=self._config.bucket,
            CopySource={
                "Bucket": self._config.bucket,
                "Key": source_key,
            },
            CopySourceRange=f"bytes={start_byte}-{end_byte}",
            Key=export_key,
            PartNumber=part_number,
            UploadId=upload_id,
        )
        return {
            "ETag": copy_part_etag(response, err=_upstream_s3_err),
            "PartNumber": part_number,
        }

    def _assert_upload_scope(self, *, key: str, scope_id: str) -> None:
        expected_prefix = f"{self._upload_prefix}{scope_id}/"
        if not key.startswith(expected_prefix):
            raise invalid_request("key is outside caller upload scope")
