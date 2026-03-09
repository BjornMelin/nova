# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.job_status import JobStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.job_result_update_request_result_type_0 import (
        JobResultUpdateRequestResultType0,
    )


T = TypeVar("T", bound="JobResultUpdateRequest")


@_attrs_define
class JobResultUpdateRequest:
    """Worker/internal request payload for job result updates.

    Attributes:
        status (JobStatus): Lifecycle status of an async job.
        error (None | str | Unset):
        result (JobResultUpdateRequestResultType0 | None | Unset):
    """

    status: JobStatus
    error: None | str | Unset = UNSET
    result: JobResultUpdateRequestResultType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict."""
        from ..models.job_result_update_request_result_type_0 import (
            JobResultUpdateRequestResultType0,
        )

        status = self.status.value

        error: None | str | Unset
        if isinstance(self.error, Unset):
            error = UNSET
        else:
            error = self.error

        result: dict[str, Any] | None | Unset
        if isinstance(self.result, Unset):
            result = UNSET
        elif isinstance(self.result, JobResultUpdateRequestResultType0):
            result = self.result.to_dict()
        else:
            result = self.result

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
            }
        )
        if error is not UNSET:
            field_dict["error"] = error
        if result is not UNSET:
            field_dict["result"] = result

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping."""
        from ..models.job_result_update_request_result_type_0 import (
            JobResultUpdateRequestResultType0,
        )

        d = dict(src_dict)
        status = JobStatus(d.pop("status"))

        def _parse_error(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error = _parse_error(d.pop("error", UNSET))

        def _parse_result(
            data: object,
        ) -> JobResultUpdateRequestResultType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                result_type_0 = JobResultUpdateRequestResultType0.from_dict(
                    data
                )

                return result_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(JobResultUpdateRequestResultType0 | None | Unset, data)

        result = _parse_result(d.pop("result", UNSET))

        job_result_update_request = cls(
            status=status,
            error=error,
            result=result,
        )

        return job_result_update_request
