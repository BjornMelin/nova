from enum import Enum


class ExportStatus(str, Enum):
    CANCELLED = "cancelled"
    COPYING = "copying"
    FAILED = "failed"
    FINALIZING = "finalizing"
    QUEUED = "queued"
    SUCCEEDED = "succeeded"
    VALIDATING = "validating"

    def __str__(self) -> str:
        return str(self.value)
