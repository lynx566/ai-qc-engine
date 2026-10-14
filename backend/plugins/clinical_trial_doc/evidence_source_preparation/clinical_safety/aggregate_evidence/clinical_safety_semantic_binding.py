"""Clinical-safety concrete semantic binding for aggregate-evidence ESP."""

from __future__ import annotations

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.profile import (
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy import (
    build_heading_scope_eligibility_entries,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidencePrepareSemanticBinding,
    AggregateEvidenceSemanticBinding,
)

CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING = AggregateEvidencePrepareSemanticBinding(
    assessment_profile_ref=CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME,
    instructions=DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
)

CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING = AggregateEvidenceSemanticBinding(
    prepare=CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
    build_heading_scope_eligibility_entries=build_heading_scope_eligibility_entries,
)
