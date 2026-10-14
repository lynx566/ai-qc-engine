"""Application bindings for internal_ib capability."""

from __future__ import annotations

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCapabilityDeclaration,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    ComparisonFindingConsolidationCapabilityDeclaration,
)
from plugins.clinical_trial_doc.prepare_analysis.config import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
)

CAPABILITY_ID = "internal_ib"

EXPECTED_DOCUMENT_TYPE_BINDINGS = {
    "source": "IB",
}

PREPARE_ANALYSIS_BINDINGS = {
    "source": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
}

FILTER_JOB_BINDINGS = {
    "source": (
        "ib_clinical_safety",
        "ib_overview",
    ),
}

CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS = {
    "source": "ib_clinical_safety",
}

COMPARISON_FINDING_ASSESSMENT_DECLARATION = (
    ComparisonFindingAssessmentCapabilityDeclaration(
        enabled_comparison_modes=(
            "scope_local",
            "focus_comparison",
        ),
        participant_role_ids=("source",),
    )
)

COMPARISON_FINDING_CONSOLIDATION_DECLARATION = (
    ComparisonFindingConsolidationCapabilityDeclaration(
        enabled_comparison_modes=("focus_comparison",),
    )
)

__all__ = [
    "CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS",
    "CAPABILITY_ID",
    "COMPARISON_FINDING_ASSESSMENT_DECLARATION",
    "COMPARISON_FINDING_CONSOLIDATION_DECLARATION",
    "EXPECTED_DOCUMENT_TYPE_BINDINGS",
    "FILTER_JOB_BINDINGS",
    "PREPARE_ANALYSIS_BINDINGS",
]
