from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.metrics_summary_response_activity import (
        MetricsSummaryResponseActivity,
    )
    from nova_sdk_py.models.metrics_summary_response_counters import (
        MetricsSummaryResponseCounters,
    )
    from nova_sdk_py.models.metrics_summary_response_latencies_ms import (
        MetricsSummaryResponseLatenciesMs,
    )


T = TypeVar("T", bound="MetricsSummaryResponse")


@_attrs_define
class MetricsSummaryResponse:
    """Metrics summary endpoint response body.

    Attributes:
        activity (MetricsSummaryResponseActivity):
        counters (MetricsSummaryResponseCounters):
        latencies_ms (MetricsSummaryResponseLatenciesMs):
    """

    activity: MetricsSummaryResponseActivity
    counters: MetricsSummaryResponseCounters
    latencies_ms: MetricsSummaryResponseLatenciesMs

    def to_dict(self) -> dict[str, Any]:
        activity = self.activity.to_dict()

        counters = self.counters.to_dict()

        latencies_ms = self.latencies_ms.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "activity": activity,
                "counters": counters,
                "latencies_ms": latencies_ms,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.metrics_summary_response_activity import (
            MetricsSummaryResponseActivity,
        )
        from nova_sdk_py.models.metrics_summary_response_counters import (
            MetricsSummaryResponseCounters,
        )
        from nova_sdk_py.models.metrics_summary_response_latencies_ms import (
            MetricsSummaryResponseLatenciesMs,
        )

        d = dict(src_dict)
        activity = MetricsSummaryResponseActivity.from_dict(d.pop("activity"))

        counters = MetricsSummaryResponseCounters.from_dict(d.pop("counters"))

        latencies_ms = MetricsSummaryResponseLatenciesMs.from_dict(
            d.pop("latencies_ms")
        )

        metrics_summary_response = cls(
            activity=activity,
            counters=counters,
            latencies_ms=latencies_ms,
        )

        return metrics_summary_response
