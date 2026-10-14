"""Canonical Evidence Source Preparation stage runtime."""

from __future__ import annotations

from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageExecutor,
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationStageResult,
)
from operations.evidence_source_preparation.stage_validation import (
    validate_evidence_source_preparation_stage_input,
)


def run_evidence_source_preparation_stage(
    *,
    stage_input: EvidenceSourcePreparationStageInput,
    stage_executor: EvidenceSourcePreparationStageExecutor,
) -> EvidenceSourcePreparationStageResult:
    """Validate neutral stage input/result and delegate once to the installed executor."""

    if not isinstance(stage_input, EvidenceSourcePreparationStageInput):
        raise TypeError(
            "stage_input must be an EvidenceSourcePreparationStageInput; "
            f"got {type(stage_input)!r}"
        )
    validate_evidence_source_preparation_stage_input(stage_input)
    result = stage_executor(stage_input=stage_input)
    if not isinstance(result, EvidenceSourcePreparationStageResult):
        raise TypeError(
            "stage_executor must return EvidenceSourcePreparationStageResult; "
            f"got {type(result)!r}"
        )
    return result


__all__ = [
    "run_evidence_source_preparation_stage",
]
