from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.types import UNSET, Unset

if TYPE_CHECKING:
    from nova_sdk_py.models.sign_parts_request_checksums_sha_256_type_0 import (
        SignPartsRequestChecksumsSha256Type0,
    )


T = TypeVar("T", bound="SignPartsRequest")


@_attrs_define
class SignPartsRequest:
    """Multipart sign-parts request."""

    key: str
    part_numbers: list[int]
    upload_id: str
    checksums_sha256: None | SignPartsRequestChecksumsSha256Type0 | Unset = (
        UNSET
    )

    def to_dict(self) -> dict[str, Any]:
        from nova_sdk_py.models.sign_parts_request_checksums_sha_256_type_0 import (
            SignPartsRequestChecksumsSha256Type0,
        )

        key = self.key

        part_numbers = self.part_numbers

        upload_id = self.upload_id

        checksums_sha256: dict[str, Any] | None | Unset
        if isinstance(self.checksums_sha256, Unset):
            checksums_sha256 = UNSET
        elif isinstance(
            self.checksums_sha256, SignPartsRequestChecksumsSha256Type0
        ):
            checksums_sha256 = self.checksums_sha256.to_dict()
        else:
            checksums_sha256 = self.checksums_sha256

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
                "part_numbers": part_numbers,
                "upload_id": upload_id,
            }
        )
        if checksums_sha256 is not UNSET:
            field_dict["checksums_sha256"] = checksums_sha256

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.sign_parts_request_checksums_sha_256_type_0 import (
            SignPartsRequestChecksumsSha256Type0,
        )

        d = dict(src_dict)
        key = d.pop("key")

        part_numbers = cast(list[int], d.pop("part_numbers"))

        upload_id = d.pop("upload_id")

        def _parse_checksums_sha256(
            data: object,
        ) -> None | SignPartsRequestChecksumsSha256Type0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                checksums_sha256_type_0 = (
                    SignPartsRequestChecksumsSha256Type0.from_dict(
                        cast("Mapping[str, Any]", data)
                    )
                )

                return checksums_sha256_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                None | SignPartsRequestChecksumsSha256Type0 | Unset, data
            )

        checksums_sha256 = _parse_checksums_sha256(
            d.pop("checksums_sha256", UNSET)
        )

        sign_parts_request = cls(
            key=key,
            part_numbers=part_numbers,
            upload_id=upload_id,
            checksums_sha256=checksums_sha256,
        )

        return sign_parts_request
