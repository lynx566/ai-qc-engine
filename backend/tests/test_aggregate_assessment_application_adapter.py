"""Focused Step B tests for the aggregate assessment application boundary."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceAssessmentExecution,
)
from tests.test_assessment_input_compact import (
    _aggregate_unit,
    _compact_assessment_input_from_units,
)


def test_assess_adapter_returns_canonical_assessment_execution() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Safety"],
            context_block_ids=["C0010"],
        )
    ]
    assessment_input, assessment_runtime_context = _compact_assessment_input_from_units(
        units
    )
    execution = run_aggregate_evidence_assess_heading_scopes(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        llm_mode="mock",
    )

    assert isinstance(execution, AggregateEvidenceAssessmentExecution)
    assert execution.scope_assessments_filename == "scope_assessments.json"
    assert execution.scope_assessments["artifact_type"] == "scope_assessments"
    assert execution.scope_assessments["phase"] == "assess"
    assert execution.scope_assessment_count == 1
    assert execution.scope_assessment_trace is not None
    assert execution.scope_assessment_review is not None
