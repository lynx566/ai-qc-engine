# ruff: noqa: TRY004
"""Pure in-memory canonical operations for evidence source preparation."""

from __future__ import annotations

from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationExecutor,
    EvidenceSourcePreparationInvocation,
    EvidenceSourcePreparationResult,
)


def run_evidence_source_preparation(
    *,
    invocation: EvidenceSourcePreparationInvocation,
    executor: EvidenceSourcePreparationExecutor,
) -> EvidenceSourcePreparationResult:
    """Canonical in-memory Evidence Source Preparation entry."""
    if not isinstance(invocation, EvidenceSourcePreparationInvocation):
        raise TypeError(
            "invocation must be an EvidenceSourcePreparationInvocation; "
            f"got {type(invocation)!r}"
        )
    result = executor(invocation=invocation)
    if not isinstance(result, EvidenceSourcePreparationResult):
        raise TypeError(
            "executor must return EvidenceSourcePreparationResult; "
            f"got {type(result)!r}"
        )
    return result
