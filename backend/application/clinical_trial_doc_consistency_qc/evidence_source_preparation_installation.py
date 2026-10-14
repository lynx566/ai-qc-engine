"""Evidence Source Preparation production installation for clinical-trial documents."""

from __future__ import annotations

from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationExecutor,
    EvidenceSourcePreparationInvocation,
    EvidenceSourcePreparationResult,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageExecutor,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.executor import (
    execute_clinical_trial_aggregate_evidence_source_preparation,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidenceSemanticBinding,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    build_clinical_trial_aggregate_evidence_source_preparation_stage_executor,
)

INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING: (
    AggregateEvidenceSemanticBinding
) = CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING


def _installed_aggregate_evidence_source_preparation_executor(
    *,
    invocation: EvidenceSourcePreparationInvocation,
) -> EvidenceSourcePreparationResult:
    return execute_clinical_trial_aggregate_evidence_source_preparation(
        invocation=invocation,
        semantic_binding=INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING,
    )


INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR: (
    EvidenceSourcePreparationExecutor
) = _installed_aggregate_evidence_source_preparation_executor

INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR: (
    EvidenceSourcePreparationStageExecutor
) = build_clinical_trial_aggregate_evidence_source_preparation_stage_executor(
    evidence_source_preparation_executor=(
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR
    ),
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING",
    "INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR",
    "INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR",
]
