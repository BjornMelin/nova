# ruff: noqa
"""Contains shared errors types that can be raised from API functions"""


class UnexpectedStatus(Exception):
    """Raised when the response status is undocumented.

    This exception is raised by API functions when
    Client.raise_on_unexpected_status is True.
    """

    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content

        super().__init__(f"Unexpected status code: {status_code}")


__all__ = ["UnexpectedStatus"]
