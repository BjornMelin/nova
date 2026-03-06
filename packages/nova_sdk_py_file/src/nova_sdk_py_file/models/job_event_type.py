from enum import Enum


class JobEventType(str, Enum):
    SNAPSHOT = "snapshot"

    def __str__(self) -> str:
        return str(self.value)
