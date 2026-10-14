"""Evidence Comparison production installation for clinical-trial documents."""

from __future__ import annotations

from operations.evidence_comparison.contracts import (
    EvidenceComparisonExecutor,
)
from operations.evidence_comparison.stage import EvidenceComparisonStageExecutor
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.executor import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    build_clinical_trial_aggregate_evidence_comparison_stage_executor,
)

INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY = None

INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_EXECUTOR: EvidenceComparisonExecutor = (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
)

INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_STAGE_EXECUTOR: (
    EvidenceComparisonStageExecutor
) = build_clinical_trial_aggregate_evidence_comparison_stage_executor(
    evidence_comparison_executor=INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_EXECUTOR,
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_EXECUTOR",
    "INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY",
    "INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_STAGE_EXECUTOR",
]
