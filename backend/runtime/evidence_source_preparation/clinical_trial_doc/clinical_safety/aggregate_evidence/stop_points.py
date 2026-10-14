"""Aggregate Evidence phase dev/debug harness stop points and durable step identities.

Phase dev/debug harness — not a canonical runtime stage.
"""

from __future__ import annotations

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    ASSESS_HEADING_SCOPES_OPERATION,
    EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION,
    PREPARE_ASSESSMENT_INPUT_OPERATION,
)

EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP = "evidence_source_preparation_prepare"
EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP = "evidence_source_preparation_assess"
EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP = (
    "evidence_source_preparation_eligibility"
)
EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_STEP = "evidence_source_preparation_assemble"

SEQUENCE_STOP_POINTS = (
    EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
)

RETIRED_STOP_POINT_REPLACEMENTS: dict[str, str] = {
    "tag_prepare": EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
    "tag": EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    "process_prepare": EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
    "process_assess": EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    "process_eligibility": EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
    "process_assemble": EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_STEP,
}


_STOP_POINT_TO_THROUGH_OPERATION: dict[str, str] = {
    EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP: PREPARE_ASSESSMENT_INPUT_OPERATION,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP: ASSESS_HEADING_SCOPES_OPERATION,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP: (
        EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION
    ),
}


def resolve_through_operation_for_stop_point(stop_point: str) -> str:
    try:
        return _STOP_POINT_TO_THROUGH_OPERATION[stop_point]
    except KeyError as exc:
        raise ValueError(
            f"stop point {stop_point!r} has no Aggregate Evidence through-operation mapping"
        ) from exc
