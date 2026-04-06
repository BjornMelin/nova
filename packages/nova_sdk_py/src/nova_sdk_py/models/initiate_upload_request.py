from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="InitiateUploadRequest")


@_attrs_define
class InitiateUploadRequest:
    """
        Initiate-upload request model.

    Client hints (``workload_class``, ``policy_hint``, ``checksum_preference``)
    are inputs only. The effective persisted transfer policy exposes
    ``checksum_mode`` as ``none|optional|required`` per SPEC-0002 (S3
    integration). ``checksum_preference`` accepts ``none|standard|strict`` as a
    client preference; preference is not the same enum as mode mapping and the
    final mode decision happens server-side.

        Attributes:
            checksum_preference: Preferred checksum strictness requested by the
            client.
            checksum_value: Optional checksum value supplied with the initiate
            request.
            content_type: Optional MIME type that should be persisted with the
            object.
            filename: Client-facing filename for the object being uploaded.
            policy_hint: Optional transfer-policy hint evaluated by the API.
            size_bytes: Total size of the object being uploaded, in bytes.
            workload_class: Optional workload-class hint for transfer policy
            selection.
    """

    filename: str
    """ Client-facing filename for the object being uploaded. """
    size_bytes: int
    """ Total size of the object being uploaded, in bytes. """
    checksum_preference: None | str | Unset = UNSET
    """ Preferred checksum strictness requested by the client. """
    checksum_value: None | str | Unset = UNSET
    """ Optional checksum value supplied with the initiate request. """
    content_type: None | str | Unset = UNSET
    """ Optional MIME type that should be persisted with the object. """
    policy_hint: None | str | Unset = UNSET
    """ Optional transfer-policy hint evaluated by the API. """
    workload_class: None | str | Unset = UNSET
    """ Optional workload-class hint for transfer policy selection. """

    def to_dict(self) -> dict[str, Any]:
        filename = self.filename

        size_bytes = self.size_bytes

        checksum_preference: None | str | Unset
        if isinstance(self.checksum_preference, Unset):
            checksum_preference = UNSET
        else:
            checksum_preference = self.checksum_preference

        checksum_value: None | str | Unset
        if isinstance(self.checksum_value, Unset):
            checksum_value = UNSET
        else:
            checksum_value = self.checksum_value

        content_type: None | str | Unset
        if isinstance(self.content_type, Unset):
            content_type = UNSET
        else:
            content_type = self.content_type

        policy_hint: None | str | Unset
        if isinstance(self.policy_hint, Unset):
            policy_hint = UNSET
        else:
            policy_hint = self.policy_hint

        workload_class: None | str | Unset
        if isinstance(self.workload_class, Unset):
            workload_class = UNSET
        else:
            workload_class = self.workload_class

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "filename": filename,
                "size_bytes": size_bytes,
            }
        )
        if checksum_preference is not UNSET:
            field_dict["checksum_preference"] = checksum_preference
        if checksum_value is not UNSET:
            field_dict["checksum_value"] = checksum_value
        if content_type is not UNSET:
            field_dict["content_type"] = content_type
        if policy_hint is not UNSET:
            field_dict["policy_hint"] = policy_hint
        if workload_class is not UNSET:
            field_dict["workload_class"] = workload_class

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        filename = d.pop("filename")

        size_bytes = d.pop("size_bytes")

        def _parse_checksum_preference(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        checksum_preference = _parse_checksum_preference(
            d.pop("checksum_preference", UNSET)
        )

        def _parse_checksum_value(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        checksum_value = _parse_checksum_value(d.pop("checksum_value", UNSET))

        def _parse_content_type(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content_type = _parse_content_type(d.pop("content_type", UNSET))

        def _parse_policy_hint(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        policy_hint = _parse_policy_hint(d.pop("policy_hint", UNSET))

        def _parse_workload_class(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        workload_class = _parse_workload_class(d.pop("workload_class", UNSET))

        initiate_upload_request = cls(
            filename=filename,
            size_bytes=size_bytes,
            checksum_preference=checksum_preference,
            checksum_value=checksum_value,
            content_type=content_type,
            policy_hint=policy_hint,
            workload_class=workload_class,
        )

        return initiate_upload_request
