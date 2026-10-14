"""Process.assess runtime tests."""

# ruff: noqa: B017
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_FILENAME,
    SCOPE_ASSESSMENT_TRACE_FILENAME,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.io import load_json
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assess import run_assess
from tests.evidence_source_preparation_phase_test_helpers import installed_assess_phase_kwargs
from tests.test_aggregate_evidence_runtime_prepare import _run_route_to_prepare


def test_mock_assess_writes_scope_artifacts(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    assess_out = tmp_path / "assess_out"
    result = run_assess(
        **installed_assess_phase_kwargs(),
        assessment_input_path=refs["assessment_input"],
        output_dir=assess_out,
        run_id="assess_test",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    assert result.scope_assessments_path.is_file()
    assert not (assess_out / "heading_scope_eligibility.json").exists()
    assert not (assess_out / "scope_processing_plan.json").exists()
    assert not (assess_out / "aggregate_assessments.json").exists()
    assert not (assess_out / "assessment_review.json").exists()
    assert not (assess_out / "assessment_coverage_report.json").exists()
    assert (assess_out / "scope_assessment_review.json").is_file()
    assert result.scope_assessment_trace_path == (
        assess_out / SCOPE_ASSESSMENT_TRACE_FILENAME
    ).resolve()
    assert result.scope_assessment_trace_path.is_file()

    assessments = load_json(result.scope_assessments_path)
    assert assessments["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert assessments["phase"] == EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE
    assert "comparison_type" not in assessments
    assert assessments["artifact_type"] == "scope_assessments"
    assert assessments.get("scope_assessments") is not None
    assert assessments.get("tagged_items") is None
    runtime_ref = assessments["source_assessment_runtime_context_ref"]
    assert runtime_ref["assessment_runtime_context_id"] == assessments[
        "source_assessment_input_ref"
    ]["llm_input_bundle_id"].replace("llm_input_", "assessment_runtime_")
    assert runtime_ref["path"] == "assessment_runtime_context.json"
    summary = load_json(result.run_summary_path)
    assert summary["outputs"]["scope_assessment_review"] == "scope_assessment_review.json"
    assert summary["outputs"]["scope_assessment_review_schema_version"] == "0.3.0"
    assert summary["outputs"]["scope_assessment_trace"] == SCOPE_ASSESSMENT_TRACE_FILENAME


def test_assess_ignores_unknown_upstream_summary_output_metadata(
    tmp_path: Path,
) -> None:
    refs = _run_route_to_prepare(tmp_path)
    prepare_dir = refs["assessment_input"].parent
    from runtime.io import save_json

    prepare_summary_path = prepare_dir / "run_summary.json"
    prepare_summary = load_json(prepare_summary_path)
    prepare_summary.setdefault("outputs", {})["pre_llm_review_state"] = (
        "missing_legacy_review_state.json"
    )

    save_json(prepare_summary_path, prepare_summary)

    assess_out = tmp_path / "assess_with_state"
    result = run_assess(
        **installed_assess_phase_kwargs(),
        assessment_input_path=refs["assessment_input"],
        output_dir=assess_out,
        run_id="assess_state_ref",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    summary = load_json(result.run_summary_path)
    assert "pre_llm_review_state" not in summary["inputs"]


def test_assess_rejects_wrong_prepare_phase(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    bad_input = load_json(refs["assessment_input"])
    bad_input["phase"] = "assess"
    bad_path = tmp_path / "bad_assessment_input.json"
    from runtime.io import save_json

    save_json(bad_path, bad_input)
    with pytest.raises(ValueError, match="phase"):
        run_assess(
            **installed_assess_phase_kwargs(),
            assessment_input_path=bad_path,
            output_dir=tmp_path / "assess_bad",
            run_id="assess_bad",
            evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        )


def test_assess_api_contract_error_does_not_write_scope_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refs = _run_route_to_prepare(tmp_path)
    assess_out = tmp_path / "assess_invalid"

    def _fake_scope_assess(**_kwargs: object) -> dict:
        from llm.execution_errors import APIStructuredResponseError

        raise APIStructuredResponseError(
            "invalid contract",
            debug_artifacts={"scope_assessment_trace": {"contract_error": "bad"}},
            failure_reason="api_schema_validation_error",
        )

    monkeypatch.setattr(
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assess.run_aggregate_evidence_scope_assess",
        _fake_scope_assess,
    )

    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assess import (
        run_assess_with_error_handling,
    )

    with pytest.raises(Exception):
        run_assess_with_error_handling(
            **installed_assess_phase_kwargs(),
            assessment_input_path=refs["assessment_input"],
            output_dir=assess_out,
            run_id="assess_invalid",
            evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
            llm_mode="api",
        )

    assert not (assess_out / SCOPE_ASSESSMENTS_FILENAME).is_file()
    assert not (assess_out / "scope_assessment_review.json").is_file()
    failure_summary = load_json(assess_out / "run_summary.json")
    assert failure_summary["stage"] == "evidence_source_preparation"
