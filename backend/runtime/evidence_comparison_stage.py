"""Canonical generic Evidence Comparison stage runtime."""

from __future__ import annotations

from operations.evidence_comparison.stage import (
    EvidenceComparisonStageExecutor,
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)


def run_evidence_comparison_stage(
    *,
    stage_input: EvidenceComparisonStageInput,
    stage_executor: EvidenceComparisonStageExecutor,
) -> EvidenceComparisonStageResult:
    """Validate the neutral envelope and delegate without loading artifacts."""

    if not isinstance(stage_input, EvidenceComparisonStageInput):
        raise TypeError(
            "stage_input must be an EvidenceComparisonStageInput; "
            f"got {type(stage_input)!r}"
        )
    result = stage_executor(stage_input=stage_input)
    if not isinstance(result, EvidenceComparisonStageResult):
        raise TypeError(
            "stage_executor must return EvidenceComparisonStageResult; "
            f"got {type(result)!r}"
        )
    return result


__all__ = ["run_evidence_comparison_stage"]

