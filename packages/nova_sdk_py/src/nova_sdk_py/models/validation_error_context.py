"""Context for HTTP validation error payloads (additionalProperties)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define, field as _attrs_field

T = TypeVar("T", bound="ValidationErrorContext")


@_attrs_define
class ValidationErrorContext:
    """Hold arbitrary key/value pairs returned alongside validation errors.

    Attributes:
        additional_properties: Extra response members preserved from the
            decoded payload.
    """

    additional_properties: dict[str, Any] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize additional properties to a plain ``dict``.

        Returns:
            Mapping of preserved validation-error context values.
        """

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build an instance from a decoded mapping.

        Args:
            src_dict: Decoded mapping containing arbitrary context members.

        Returns:
            New ``ValidationErrorContext`` containing all supplied keys.
        """

        d = dict(src_dict)
        validation_error_context = cls()

        validation_error_context.additional_properties = d
        return validation_error_context

    @property
    def additional_keys(self) -> list[str]:
        """Return keys present in ``additional_properties``.

        Returns:
            Ordered list of preserved context keys.
        """

        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        """Return the value for ``key`` from ``additional_properties``.

        Args:
            key: Context key to retrieve.

        Returns:
            Stored value for ``key``.

        Raises:
            KeyError: If ``key`` is not present.
        """

        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set ``key`` on ``additional_properties``.

        Args:
            key: Context key to update.
            value: Value to store for ``key``.

        Returns:
            None.
        """

        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove ``key`` from ``additional_properties``.

        Args:
            key: Context key to remove.

        Returns:
            None.

        Raises:
            KeyError: If ``key`` is not present.
        """

        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        """Return whether ``key`` exists in ``additional_properties``.

        Args:
            key: Context key to test.

        Returns:
            ``True`` when ``key`` is present, else ``False``.
        """

        return key in self.additional_properties
