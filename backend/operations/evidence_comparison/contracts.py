"""Neutral in-memory contracts for Evidence Comparison execution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class EvidenceComparisonInvocation:
    """Marker base for one concrete Evidence Comparison invocation."""


class EvidenceComparisonResult:
    """Marker base for one concrete Evidence Comparison result."""


@runtime_checkable
class EvidenceComparisonExecutor(Protocol):
    """Installed implementation boundary for one comparison execution."""

    def __call__(
        self,
        *,
        invocation: EvidenceComparisonInvocation,
    ) -> EvidenceComparisonResult: ...


__all__ = [
    "EvidenceComparisonExecutor",
    "EvidenceComparisonInvocation",
    "EvidenceComparisonResult",
]

