"""Neutral in-memory contracts for Evidence Source Preparation execution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class EvidenceSourcePreparationInvocation:
    """Marker base for one domain-owned ESP invocation envelope.

    Concrete implementations carry domain-specific upstream and route facts.
    The neutral operation boundary intentionally does not enumerate them.
    """


class EvidenceSourcePreparationResult:
    """Marker base for one domain-owned ESP execution result.

    Concrete implementations carry domain-specific prepared evidence payloads.
    The neutral operation boundary intentionally does not enumerate them.
    """


@runtime_checkable
class EvidenceSourcePreparationExecutor(Protocol):
    """Installed implementation boundary for one ESP operation execution."""

    def __call__(
        self,
        *,
        invocation: EvidenceSourcePreparationInvocation,
    ) -> EvidenceSourcePreparationResult: ...


__all__ = [
    "EvidenceSourcePreparationExecutor",
    "EvidenceSourcePreparationInvocation",
    "EvidenceSourcePreparationResult",
]
