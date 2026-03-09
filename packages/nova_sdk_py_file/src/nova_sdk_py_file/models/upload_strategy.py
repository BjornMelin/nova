# ruff: noqa
from enum import Enum


class UploadStrategy(str, Enum):
    MULTIPART = "multipart"
    SINGLE = "single"

    def __str__(self) -> str:
        return str(self.value)
