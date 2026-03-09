# ruff: noqa
from enum import Enum


class CreateJobResponse503ErrorCode(str, Enum):
    QUEUE_UNAVAILABLE = "queue_unavailable"

    def __str__(self) -> str:
        return str(self.value)
