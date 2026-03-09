# ruff: noqa
from enum import Enum


class UploadStrategy(str, Enum):
    """Allowed transfer upload strategies."""

    MULTIPART = "multipart"
    SINGLE = "single"

    def __str__(self) -> str:
        return str(self.value)
