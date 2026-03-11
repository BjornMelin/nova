# ruff: noqa
"""Multipart uploaded-part model for resume introspection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from attrs import validators as _attrs_validators

T = TypeVar("T", bound="UploadedPart")


@_attrs_define
class UploadedPart:
    """Part state returned for multipart upload introspection.

    Attributes:
        etag (str): ETag returned by S3 for this uploaded part.
        part_number (int): 1-based multipart part number (valid range: 1-10,000).
    """

    etag: str
    part_number: int = _attrs_field(
        validator=_attrs_validators.and_(
            _attrs_validators.instance_of(int),
            _attrs_validators.ge(1),
            _attrs_validators.le(10000),
        )
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict.

        Args:
            None.

        Returns:
            dict[str, Any]: Serialized uploaded part payload.
        """
        etag = self.etag

        part_number = self.part_number

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "etag": etag,
                "part_number": part_number,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping.

        Args:
            src_dict (Mapping[str, Any]): Source mapping containing
                ``etag`` and ``part_number`` keys.

        Returns:
            UploadedPart: Parsed uploaded-part model.

        Raises:
            KeyError: If required keys are missing.
            TypeError: If value types are not compatible.
        """
        d = dict(src_dict)
        etag = d.pop("etag")

        part_number = d.pop("part_number")

        uploaded_part = cls(
            etag=etag,
            part_number=part_number,
        )

        return uploaded_part