"""Neutral LLM execution error contracts."""

from __future__ import annotations

from typing import Any


class APIStructuredResponseError(RuntimeError):
    """Raised when API mode cannot produce a usable structured LLM response."""

    def __init__(
        self,
        message: str,
        *,
        debug_artifacts: dict[str, Any],
        failure_reason: str,
    ) -> None:
        super().__init__(message)
        self.debug_artifacts = debug_artifacts
        self.failure_reason = failure_reason
