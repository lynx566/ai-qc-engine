"""Immutable aggregate-evidence form identity; contains no business logic."""

from __future__ import annotations

CLINICAL_TRIAL_DOC_PLUGIN_ID = "clinical_trial_doc"

AGGREGATE_EVIDENCE_FORM_ID = "aggregate_evidence"

PREPARE_ASSESSMENT_INPUT_OPERATION = "aggregate_evidence.prepare_assessment_input"

ASSESS_HEADING_SCOPES_OPERATION = "aggregate_evidence.assess_heading_scopes"

EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION = (
    "aggregate_evidence.evaluate_heading_scope_eligibility"
)

ASSEMBLE_AGGREGATE_EVIDENCE_SOURCE_BUNDLE_OPERATION = (
    "aggregate_evidence.assemble_aggregate_evidence_source_bundle"
)

IMPLEMENTED_OPERATIONS = (
    PREPARE_ASSESSMENT_INPUT_OPERATION,
    ASSESS_HEADING_SCOPES_OPERATION,
    EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION,
    ASSEMBLE_AGGREGATE_EVIDENCE_SOURCE_BUNDLE_OPERATION,
)

CURRENT_DEFAULT_THROUGH = EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION
