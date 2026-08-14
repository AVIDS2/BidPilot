"""Public, typed failures for user-requested remote material imports."""

from __future__ import annotations


class RemoteImportError(ValueError):
    """A user-safe remote source failure with a stable remediation code."""

    def __init__(self, error_code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.public_message = message
        self.retryable = retryable
