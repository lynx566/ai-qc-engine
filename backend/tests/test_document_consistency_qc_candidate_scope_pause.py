"""Tests for canonical Candidate Scope pause boundary in document_consistency_qc flow."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    validate_flow_run_summary,
)
from capability import DSUR_UPDATED_IB_CONSISTENCY_QC, INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc import CandidateScopeDecisionMode
from execution_flow.document_consistency_qc.errors import (
    DocumentConsistencyQcFlowExecutionError,
)
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcParticipantRunInput,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.io import load_json
from tests.document_consistency_qc_flow_helpers import (
    admitted_source_bindings,
    clinical_flow_invocation_kwargs,
)

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)
SECOND_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)


def _git_prov() -> dict[str, str | bool | None]:
    return {"git_commit": "abc", "git_dirty": False}


def _participant_inputs(
    slot_ids: tuple[str, ...],
) -> dict[str, DocumentConsistencyQcParticipantRunInput]:
    return {
        slot_id: DocumentConsistencyQcParticipantRunInput(
            prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                ClinicalPreparePrivacyConfig.identity()
            ),
        )
        for slot_id in slot_ids
    }


def _run_flow(
    *,
    capability_config,
    uploads: dict[str, Path | str],
    project_root: Path,
    candidate_scope_decision_mode: CandidateScopeDecisionMode = (
        CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
    ),
):
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    return flow_module.run_document_consistency_qc_flow(
        project_root=project_root,
        capability_config=capability_config,
        uploads=admitted_source_bindings(uploads),
        participant_inputs=_participant_inputs(tuple(uploads)),
        prepare_analysis_config_registry=registry,
        git_provenance=_git_prov(),
        candidate_scope_decision_mode=candidate_scope_decision_mode,
        **clinical_flow_invocation_kwargs(),
    )


def test_default_flow_still_runs_projection(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()

    with patch.object(
        flow_module,
        "run_filter_output_projection_stage",
        wraps=flow_module.run_filter_output_projection_stage,
    ) as projection_stage:
        report = _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    assert projection_stage.call_count >= 1
    assert report.result.paused_at_candidate_scope is False
    assert report.result.slots[0].projection_results
    projection_summary = load_json(
        report.result.slots[0].projection_results[0].stage_result.run_summary_path
    )
    assert projection_summary["source_stage"] == "filter"
    assert projection_summary["pipeline"] == [
        "extract",
        "prepare_analysis",
        "filter",
        "filter_output_projection",
    ]


def test_pause_after_all_filter_jobs(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()

    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
        candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
    )

    assert report.result.paused_at_candidate_scope is True
    slot = report.result.slots[0]
    assert len(slot.filter_results) == 2
    assert {job.filter_job_id for job in slot.filter_results} == {
        "dsur_clinical_safety",
        "dsur_overview",
    }
    assert slot.projection_results == ()
    assert slot.route_semantic_module_results == ()


def test_pause_mode_does_not_run_projection_route_esp_or_comparison(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()

    with (
        patch.object(
            flow_module,
            "run_filter_output_projection_stage",
        ) as projection_stage,
        patch.object(
            flow_module,
            "run_projected_source_route_from_projection_bundles",
        ) as route_stage,
        patch.object(
            flow_module,
            "run_evidence_source_preparation_stage",
        ) as esp_stage,
        patch.object(
            flow_module,
            "run_evidence_comparison_stage",
        ) as comparison_stage,
    ):
        report = _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
            candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
        )

    assert report.result.paused_at_candidate_scope is True
    projection_stage.assert_not_called()
    route_stage.assert_not_called()
    esp_stage.assert_not_called()
    comparison_stage.assert_not_called()


def test_pause_persists_flow_run_summary(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()

    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
        candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
    )

    summary_path = report.flow_run_summary_path
    assert summary_path.is_file()
    summary = load_json(summary_path)
    validate_flow_run_summary(summary)

    assert summary["flow_run_id"] == report.flow_run_id
    assert summary["status"] == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert summary["slots"][0]["slot_id"] == "source"
    assert summary["slots"][0]["status"] == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert summary["slots"][0]["filter_jobs"]
    assert len(summary["slots"][0]["filter_jobs"]) == 2
    assert "projection_jobs" not in summary["slots"][0]
    assert "evidence_comparison" not in summary


def test_filter_failure_does_not_create_paused_checkpoint(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    call_count = 0

    def _filter_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("filter job failed")
        return flow_module.run_filter_stage(*args, **kwargs)

    with patch.object(flow_module, "run_filter_stage", side_effect=_filter_side_effect):
        with pytest.raises(
            DocumentConsistencyQcFlowExecutionError,
            match="filter job failed",
        ) as exc_info:
            _run_flow(
                capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
                uploads={"source": SAMPLE_DOCX},
                project_root=tmp_path,
                candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
            )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert str(exc_info.value.__cause__) == "filter job failed"

    flow_dirs = list((tmp_path / "runs" / "document_consistency_qc").iterdir())
    assert flow_dirs
    summary = load_json(flow_dirs[0] / FLOW_RUN_SUMMARY_FILENAME)
    assert summary["slots"][0]["status"] in {"partial", "failed"}
    assert summary["slots"][0]["status"] != SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE


def test_multi_slot_pauses_after_all_slots_filter(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()

    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={
            "source_a": SAMPLE_DOCX,
            "source_b": SECOND_SAMPLE_DOCX,
        },
        project_root=tmp_path,
        candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
    )

    assert report.result.paused_at_candidate_scope is True
    assert len(report.result.slots) == 2
    assert {slot.slot_id for slot in report.result.slots} == {"source_a", "source_b"}

    summary = load_json(report.flow_run_summary_path)
    assert summary["status"] == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    slot_statuses = {slot["slot_id"]: slot["status"] for slot in summary["slots"]}
    assert slot_statuses["source_a"] == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert slot_statuses["source_b"] == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert all(slot.get("doc_id") for slot in summary["slots"])
    assert all(slot.get("filter_jobs") for slot in summary["slots"])
    assert "evidence_comparison" not in summary
    assert report.result.slots[0].projection_results == ()
    assert report.result.slots[1].projection_results == ()
