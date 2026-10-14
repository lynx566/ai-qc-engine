"""Pure in-memory canonical operation for Evidence Comparison."""

from __future__ import annotations

from operations.evidence_comparison.contracts import (
    EvidenceComparisonExecutor,
    EvidenceComparisonInvocation,
    EvidenceComparisonResult,
)


def run_evidence_comparison(
    *,
    invocation: EvidenceComparisonInvocation,
    executor: EvidenceComparisonExecutor,
) -> EvidenceComparisonResult:
    """Validate neutral contracts and delegate once to the installed executor."""

    if not isinstance(invocation, EvidenceComparisonInvocation):
        raise TypeError(
            "invocation must be an EvidenceComparisonInvocation; "
            f"got {type(invocation)!r}"
        )
    result = executor(invocation=invocation)
    if not isinstance(result, EvidenceComparisonResult):
        raise TypeError(
            "executor must return EvidenceComparisonResult; "
            f"got {type(result)!r}"
        )
    return result


__all__ = ["run_evidence_comparison"]

