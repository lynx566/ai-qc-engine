"""Clinical-safety aggregate Evidence Comparison concrete implementation."""

from __future__ import annotations

import importlib

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_evidence import (
    materialize_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceComparisonExecution,
    AggregateEvidenceComparisonExecutionInput,
    AggregateEvidenceComparisonPreFinalState,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_adapter import (
    build_aggregate_evidence_comparison_invocation,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonInvocation,
    AggregateEvidenceComparisonParticipant,
    AggregateEvidenceComparisonParticipantEvidence,
    AggregateEvidenceComparisonScope,
    AggregateEvidenceComparisonSentence,
    AggregateEvidenceComparisonSourceAdapter,
    AggregateEvidenceComparisonSourceProvenance,
    AggregateEvidenceComparisonUnit,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.source_adapter import (
    adapt_clinical_safety_aggregate_source_bundle,
)

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AggregateEvidenceComparisonFinalizationFailure": (
        ".execution",
        "AggregateEvidenceComparisonFinalizationFailure",
    ),
    "AggregateEvidenceComparisonFinalizationError": (
        ".finalization",
        "AggregateEvidenceComparisonFinalizationError",
    ),
    "run_aggregate_evidence_comparison_execution": (
        ".execution",
        "run_aggregate_evidence_comparison_execution",
    ),
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR": (
        ".executor",
        "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR",
    ),
    "execute_clinical_trial_aggregate_evidence_comparison": (
        ".executor",
        "execute_clinical_trial_aggregate_evidence_comparison",
    ),
    "finalize_aggregate_evidence_comparison": (
        ".finalization",
        "finalize_aggregate_evidence_comparison",
    ),
}


def __getattr__(name: str) -> object:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = [
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR",
    "AggregateEvidenceComparisonExecution",
    "AggregateEvidenceComparisonExecutionInput",
    "AggregateEvidenceComparisonFinalizationFailure",
    "AggregateEvidenceComparisonFinalizationError",
    "AggregateEvidenceComparisonPreFinalState",
    "AggregateEvidenceComparisonInvocation",
    "AggregateEvidenceComparisonParticipant",
    "AggregateEvidenceComparisonParticipantEvidence",
    "AggregateEvidenceComparisonScope",
    "AggregateEvidenceComparisonSentence",
    "AggregateEvidenceComparisonSourceAdapter",
    "AggregateEvidenceComparisonSourceProvenance",
    "AggregateEvidenceComparisonUnit",
    "adapt_clinical_safety_aggregate_source_bundle",
    "build_aggregate_evidence_comparison_invocation",
    "execute_clinical_trial_aggregate_evidence_comparison",
    "finalize_aggregate_evidence_comparison",
    "materialize_aggregate_comparison_evidence",
    "run_aggregate_evidence_comparison_execution",
]
