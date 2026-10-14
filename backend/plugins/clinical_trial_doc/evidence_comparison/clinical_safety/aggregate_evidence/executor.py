"""Clinical-trial aggregate Evidence Comparison executor."""

from __future__ import annotations

from operations.evidence_comparison.contracts import (
    EvidenceComparisonExecutor,
    EvidenceComparisonInvocation,
    EvidenceComparisonResult,
)

from .execution import run_aggregate_evidence_comparison_execution
from .execution_types import (
    AggregateEvidenceComparisonExecution,
    AggregateEvidenceComparisonExecutionInput,
)


def execute_clinical_trial_aggregate_evidence_comparison(
    *,
    invocation: EvidenceComparisonInvocation,
) -> EvidenceComparisonResult:
    """Bridge neutral Comparison invocation to configured aggregate execution."""

    if not isinstance(invocation, AggregateEvidenceComparisonExecutionInput):
        raise TypeError(
            "clinical-trial aggregate comparison executor requires "
            "AggregateEvidenceComparisonExecutionInput; "
            f"got {type(invocation)!r}"
        )
    execution = run_aggregate_evidence_comparison_execution(
        execution_input=invocation,
    )
    if not isinstance(execution, AggregateEvidenceComparisonExecution):
        raise TypeError(
            "run_aggregate_evidence_comparison_execution must return "
            "AggregateEvidenceComparisonExecution; "
            f"got {type(execution)!r}"
        )
    return execution


CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR: EvidenceComparisonExecutor = (
    execute_clinical_trial_aggregate_evidence_comparison
)

__all__ = [
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR",
    "execute_clinical_trial_aggregate_evidence_comparison",
]
