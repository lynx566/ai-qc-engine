"""Application bindings for dsur_updated_ib capability."""

from __future__ import annotations

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCapabilityDeclaration,
    DsurToIbComparisonModeBinding,
    IbToDsurComparisonModeBinding,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.profiles import (
    DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
    DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    ComparisonFindingConsolidationCapabilityDeclaration,
)
from plugins.clinical_trial_doc.prepare_analysis.config import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
)

CAPABILITY_ID = "dsur_updated_ib"

EXPECTED_DOCUMENT_TYPE_BINDINGS = {
    "source_a": "DSUR",
    "source_b": "IB",
}

PREPARE_ANALYSIS_BINDINGS = {
    "source_a": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    "source_b": CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
}

FILTER_JOB_BINDINGS = {
    "source_a": (
        "dsur_clinical_safety",
        "dsur_overview",
    ),
    "source_b": (
        "ib_clinical_safety",
        "ib_overview",
    ),
}

CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS = {
    "source_a": "dsur_clinical_safety",
    "source_b": "ib_clinical_safety",
}

COMPARISON_FINDING_ASSESSMENT_DECLARATION = (
    ComparisonFindingAssessmentCapabilityDeclaration(
        enabled_comparison_modes=(
            "ib_to_dsur",
            "dsur_to_ib",
        ),
        participant_role_ids=("source_a", "source_b"),
        ib_to_dsur=IbToDsurComparisonModeBinding(
            focus_role_id="source_b",
            comparison_role_id="source_a",
        ),
        dsur_to_ib=DsurToIbComparisonModeBinding(
            dsur_role_id="source_a",
            ib_role_id="source_b",
            dsur_scope_selection=DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
            ib_scope_selection=DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
        ),
    )
)

COMPARISON_FINDING_CONSOLIDATION_DECLARATION = (
    ComparisonFindingConsolidationCapabilityDeclaration(
        enabled_comparison_modes=(),
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
