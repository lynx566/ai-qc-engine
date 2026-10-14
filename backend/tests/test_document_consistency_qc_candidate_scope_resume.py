"""Tests for canonical Candidate Scope resume boundary in document_consistency_qc flow."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
from application.clinical_trial_doc_consistency_qc.evidence_comparison_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
)
from artifacts.candidate_scope_decision import (
    CANDIDATE_SCOPE_DECISION_FILENAME,
    validate_candidate_scope_decision,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    validate_flow_run_summary,
)
from artifacts.effective_candidate_scope import RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
from capability import DSUR_UPDATED_IB_CONSISTENCY_QC, INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc import (
    CandidateScopeDecisionMode,
    FilterJobCandidateScopeSelection,
)
from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
    automatic_candidate_scope_selections,
)
from execution_flow.document_consistency_qc.candidate_scope_selection import (
    anchor_ids_from_zone_bundle,
    canonicalize_anchor_ids_for_job,
)
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcParticipantRunInput,
)
from execution_flow.document_consistency_qc.flow_loader import FlowResumeError
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoff,
    EvidenceComparisonHandoffResolution,
    EvidenceComparisonHandoffResolutionStatus,
)
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantReference,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageResult,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.io import load_json, save_json
from tests.document_consistency_qc_flow_helpers import (
    admitted_source_bindings,
    clinical_flow_invocation_kwargs,
    clinical_flow_resume_invocation_kwargs,
)

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "samples"
    / "clinical_trial_doc"
    / "docx"
    / "zh"
    / "clinical_program_001_vt8802"
    / "demo"
    / "艾美妥珠单抗 研发期间安全性更新报告#2_错误模拟.docx"
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
        CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE
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


def _resume_flow(
    *,
    capability_config,
    paused_report,
    decisions_by_slot: dict[str, tuple[FilterJobCandidateScopeSelection, ...]]
    | None = None,
    slot_id: str | None = None,
    selections: tuple[FilterJobCandidateScopeSelection, ...] | None = None,
    project_root: Path,
    **extra_resume_kwargs,
):
    if decisions_by_slot is None:
        if slot_id is None or selections is None:
            raise ValueError(
                "slot_id and selections are required when decisions_by_slot is omitted"
            )
        decisions_by_slot = {slot_id: selections}
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    resume_kwargs = clinical_flow_resume_invocation_kwargs()
    resume_kwargs.update(extra_resume_kwargs)
    return flow_module.resume_document_consistency_qc_flow(
        project_root=project_root,
        capability_config=capability_config,
        flow_run_id=paused_report.flow_run_id,
        candidate_scope_decisions_by_slot=decisions_by_slot,
        **resume_kwargs,
    )


def _automatic_decisions_for_slot(
    paused_report,
    slot_id: str,
) -> tuple[FilterJobCandidateScopeSelection, ...]:
    slot_record = _paused_slot_provenance(paused_report, slot_id)
    return automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )


def _automatic_decisions_for_capability(
    paused_report,
    capability_config,
) -> dict[str, tuple[FilterJobCandidateScopeSelection, ...]]:
    return {
        slot.slot_id: _automatic_decisions_for_slot(paused_report, slot.slot_id)
        for slot in capability_config.slots
    }


def _paused_slot_provenance(paused_report, slot_id: str):
    summary = load_json(paused_report.flow_run_summary_path)
    for slot in summary["slots"]:
        if slot["slot_id"] == slot_id:
            return slot
    raise AssertionError(f"slot {slot_id!r} not found in flow summary")


def _downgrade_paused_summary_to_legacy_012(paused_report) -> dict:
    summary = load_json(paused_report.flow_run_summary_path)
    summary["schema_version"] = PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION
    for slot in summary["slots"]:
        slot["intake_run_id"] = f"request_file_intake_{slot['slot_id']}"
        slot.pop("original_file_name", None)
    save_json(paused_report.flow_run_summary_path, summary)
    validate_flow_run_summary(summary)
    return summary


def _write_legacy_intake_artifacts(
    paused_report,
    *,
    slot_id: str,
    source_path: Path,
    file_hash: str,
) -> None:
    intake_dir = (
        paused_report.flow_run_summary_path.parent / "participants" / slot_id / "intake"
    )
    intake_dir.mkdir(parents=True, exist_ok=True)
    save_json(
        intake_dir / "request_file_intake_result.json",
        {
            "artifact_type": "request_file_intake_result",
            "schema_version": "0.2.0",
            "document": {
                "file_hash": file_hash,
                "original_file_name": source_path.name,
            },
        },
    )
    save_json(
        intake_dir / "run_summary.json",
        {
            "stage": "request_file_intake",
            "run_id": f"request_file_intake_{slot_id}",
            "status": "success",
            "inputs": {"source_file": source_path.as_posix()},
            "outputs": {
                "request_file_intake_result": "request_file_intake_result.json",
                "run_summary": "run_summary.json",
            },
        },
    )


def test_single_slot_resume_happy_path(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )

    with patch.object(
        flow_module,
        "run_filter_output_projection_stage",
        wraps=flow_module.run_filter_output_projection_stage,
    ) as projection_stage:
        resumed = _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    assert projection_stage.call_count >= 1
    assert resumed.flow_run_id == paused.flow_run_id
    assert resumed.flow_run_summary_path == paused.flow_run_summary_path
    assert resumed.result.paused_at_candidate_scope is False
    summary = load_json(resumed.flow_run_summary_path)
    assert summary["status"] == "success"
    assert summary["slots"][0]["status"] == "success"
    decision_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    assert decision_path.is_file()
    validate_candidate_scope_decision(load_json(decision_path))


def test_legacy_012_paused_resume_recovers_real_source_facts_and_writes_013(
    tmp_path: Path,
) -> None:
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    legacy = _downgrade_paused_summary_to_legacy_012(paused)
    legacy["task_run_id"] = "task_run_historical_owner"
    save_json(paused.flow_run_summary_path, legacy)
    validate_flow_run_summary(legacy)
    legacy_slot = legacy["slots"][0]
    _write_legacy_intake_artifacts(
        paused,
        slot_id="source",
        source_path=SAMPLE_DOCX,
        file_hash=legacy_slot["file_hash"],
    )
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(legacy_slot["filter_job_ids"]),
        filter_jobs=legacy_slot["filter_jobs"],
    )

    with patch(
        "execution_flow.document_processing_sequence.run_request_file_intake_operation",
        side_effect=AssertionError("legacy resume must not rerun Intake"),
    ):
        resumed = _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    summary = load_json(resumed.flow_run_summary_path)
    validate_flow_run_summary(summary)
    assert summary["schema_version"] == FLOW_RUN_SUMMARY_SCHEMA_VERSION
    assert "task_run_id" not in summary
    assert summary["status"] == "success"
    assert summary["slots"][0]["file_hash"] == legacy_slot["file_hash"]
    assert summary["slots"][0]["original_file_name"] == SAMPLE_DOCX.name
    assert summary["slots"][0]["doc_id"] == legacy_slot["doc_id"]
    assert "intake_run_id" not in summary["slots"][0]


def test_legacy_012_paused_resume_fails_when_source_provenance_is_unrecoverable(
    tmp_path: Path,
) -> None:
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    legacy = _downgrade_paused_summary_to_legacy_012(paused)
    legacy_slot = legacy["slots"][0]
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(legacy_slot["filter_job_ids"]),
        filter_jobs=legacy_slot["filter_jobs"],
    )

    with pytest.raises(
        FlowResumeError,
        match="legacy resume source provenance unavailable",
    ):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )


def test_legacy_012_multi_slot_resume_recovers_each_slots_own_source(
    tmp_path: Path,
) -> None:
    uploads = {"source_a": SAMPLE_DOCX, "source_b": SECOND_SAMPLE_DOCX}
    paused = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads=uploads,
        project_root=tmp_path,
    )
    legacy = _downgrade_paused_summary_to_legacy_012(paused)
    legacy_by_slot = {slot["slot_id"]: slot for slot in legacy["slots"]}
    for slot_id, source_path in uploads.items():
        _write_legacy_intake_artifacts(
            paused,
            slot_id=slot_id,
            source_path=source_path,
            file_hash=legacy_by_slot[slot_id]["file_hash"],
        )

    with patch(
        "execution_flow.document_processing_sequence.run_request_file_intake_operation",
        side_effect=AssertionError("legacy resume must not rerun Intake"),
    ):
        resumed = _resume_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            paused_report=paused,
            decisions_by_slot=_automatic_decisions_for_capability(
                paused,
                DSUR_UPDATED_IB_CONSISTENCY_QC,
            ),
            project_root=tmp_path,
        )

    summary = load_json(resumed.flow_run_summary_path)
    validate_flow_run_summary(summary)
    assert summary["schema_version"] == FLOW_RUN_SUMMARY_SCHEMA_VERSION
    resumed_by_slot = {slot["slot_id"]: slot for slot in summary["slots"]}
    assert resumed_by_slot["source_a"]["original_file_name"] == SAMPLE_DOCX.name
    assert resumed_by_slot["source_b"]["original_file_name"] == SECOND_SAMPLE_DOCX.name
    assert all("intake_run_id" not in slot for slot in summary["slots"])


def test_fresh_projection_per_filter_job(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )

    with patch.object(
        flow_module,
        "run_filter_output_projection_stage",
        wraps=flow_module.run_filter_output_projection_stage,
    ) as projection_stage:
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    assert projection_stage.call_count == len(slot_record["filter_job_ids"])


def test_automatic_unchanged_resume_materializes_resolved_candidate_scope(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    analysis_bundle = load_json(Path(slot_record["analysis_bundle_path"]))
    original_filter_paths = {
        job["filter_job_id"]: Path(job["zone_match_bundle_path"]).resolve()
        for job in slot_record["filter_jobs"]
    }

    with patch.object(
        flow_module,
        "run_filter_output_projection_stage",
        wraps=flow_module.run_filter_output_projection_stage,
    ) as projection_stage:
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    decision_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    decision = validate_candidate_scope_decision(load_json(decision_path))
    project_root = tmp_path.resolve()

    for filter_job_id, original_path in original_filter_paths.items():
        selection = next(
            item
            for item in decision["candidate_selections"]
            if item["filter_job_id"] == filter_job_id
        )
        assert selection["resolution"]["kind"] == "automatic_unchanged"
        upstream_path = (
            project_root / selection["resolution"]["upstream_bundle_ref"]
        ).resolve()
        assert upstream_path == original_path

        resolved_path = (project_root / selection["resolved_bundle_ref"]).resolve()
        assert resolved_path.is_file()
        assert resolved_path != original_path
        resolved_bundle = load_json(resolved_path)
        assert resolved_bundle["stage"] == "candidate_scope"
        assert resolved_bundle["input_stage"] == "filter"
        assert "candidate_scope" in resolved_bundle["pipeline"]

        automatic_bundle = load_json(original_path)
        expected_anchors = sorted(
            canonicalize_anchor_ids_for_job(
                anchor_ids=set(anchor_ids_from_zone_bundle(automatic_bundle)),
                analysis_bundle=analysis_bundle,
            )
        )
        resolved_anchors = sorted(anchor_ids_from_zone_bundle(resolved_bundle))
        assert resolved_anchors == expected_anchors

        job_calls = [
            call
            for call in projection_stage.call_args_list
            if call.kwargs.get("filter_job_id") == filter_job_id
        ]
        assert job_calls
        projection_path = Path(job_calls[0].kwargs["zone_match_bundle_path"]).resolve()
        assert projection_path == resolved_path

    flow_summary = load_json(paused.flow_run_summary_path)
    resumed_slot = next(
        item for item in flow_summary["slots"] if item["slot_id"] == "source"
    )
    projection_summary_path = Path(
        resumed_slot["projection_jobs"][0]["run_summary_path"]
    )
    if not projection_summary_path.is_absolute():
        projection_summary_path = project_root / projection_summary_path
    projection_summary = load_json(projection_summary_path)
    assert projection_summary["source_stage"] == "candidate_scope"
    assert projection_summary["pipeline"] == [
        "extract",
        "prepare_analysis",
        "filter",
        "candidate_scope",
        "filter_output_projection",
    ]


def test_adjusted_decision_materializes_effective_zone_match(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    automatic = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    adjusted_job_id = slot_record["filter_job_ids"][0]
    automatic_anchors = next(
        item.anchor_block_ids
        for item in automatic
        if item.filter_job_id == adjusted_job_id
    )
    assert len(automatic_anchors) >= 2
    adjusted_anchors = tuple(automatic_anchors[:-1])
    selections = tuple(
        FilterJobCandidateScopeSelection(
            filter_job_id=item.filter_job_id,
            anchor_block_ids=(
                adjusted_anchors
                if item.filter_job_id == adjusted_job_id
                else item.anchor_block_ids
            ),
        )
        for item in automatic
    )
    original_filter_path = Path(
        next(
            job["zone_match_bundle_path"]
            for job in slot_record["filter_jobs"]
            if job["filter_job_id"] == adjusted_job_id
        )
    )
    original_filter_bundle = load_json(original_filter_path)

    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id="source",
        selections=selections,
        project_root=tmp_path,
    )

    assert load_json(original_filter_path) == original_filter_bundle
    resolved_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / adjusted_job_id
        / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    )
    assert resolved_path.is_file()
    decision = load_json(
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    adjusted_selection = next(
        item
        for item in decision["candidate_selections"]
        if item["filter_job_id"] == adjusted_job_id
    )
    assert adjusted_selection["resolution"]["kind"] == "review_adjusted"


MANUAL_ADD_ANCHOR = "C0015"
CLINICAL_SAFETY_JOB = "dsur_clinical_safety"
OVERVIEW_JOB = "dsur_overview"


def _selections_by_job(
    slot_record: dict,
) -> dict[str, set[str]]:
    automatic = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    return {item.filter_job_id: set(item.anchor_block_ids) for item in automatic}


def _selections_from_sets(
    selection_by_job: dict[str, set[str]],
) -> tuple[FilterJobCandidateScopeSelection, ...]:
    return tuple(
        FilterJobCandidateScopeSelection(
            filter_job_id=filter_job_id,
            anchor_block_ids=tuple(sorted(anchor_ids)),
        )
        for filter_job_id, anchor_ids in selection_by_job.items()
    )


def _assert_manual_add_anchor_available(slot_record: dict) -> None:
    analysis_bundle = load_json(Path(slot_record["analysis_bundle_path"]))
    automatic = _selections_by_job(slot_record)
    automatic_all = set().union(*automatic.values())
    assert MANUAL_ADD_ANCHOR not in automatic_all
    heading_ids = {
        str(block.get("block_id"))
        for block in analysis_bundle.get("content_blocks") or []
        if isinstance(block, dict) and block.get("kind") == "heading"
    }
    assert MANUAL_ADD_ANCHOR in heading_ids


def test_manual_add_accepted_and_materializes_effective_zone_match(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    _assert_manual_add_anchor_available(slot_record)
    selection_by_job = _selections_by_job(slot_record)
    selection_by_job[CLINICAL_SAFETY_JOB].add(MANUAL_ADD_ANCHOR)

    original_filter_path = Path(
        next(
            job["zone_match_bundle_path"]
            for job in slot_record["filter_jobs"]
            if job["filter_job_id"] == CLINICAL_SAFETY_JOB
        )
    )
    original_filter_bundle = load_json(original_filter_path)

    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id="source",
        selections=_selections_from_sets(selection_by_job),
        project_root=tmp_path,
    )

    assert load_json(original_filter_path) == original_filter_bundle
    resolved_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CLINICAL_SAFETY_JOB
        / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    )
    assert resolved_path.is_file()
    effective_bundle = load_json(resolved_path)
    zone = next(
        item
        for item in effective_bundle.get("matched_zones") or []
        if (item.get("match") or {}).get("matched_heading_block_id")
        == MANUAL_ADD_ANCHOR
    )
    match = zone["match"]
    assert match["match_type"] == "manual"
    assert match["match_mode"] == "user_override"
    block_ids = {block["block_id"] for block in zone.get("blocks") or []}
    assert MANUAL_ADD_ANCHOR in block_ids
    assert len(block_ids) > 1


def test_remove_and_manual_add_materializes_effective_zone_match(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    _assert_manual_add_anchor_available(slot_record)
    selection_by_job = _selections_by_job(slot_record)
    clinical_anchors = selection_by_job[CLINICAL_SAFETY_JOB]
    assert len(clinical_anchors) >= 1
    removed_anchor = min(clinical_anchors)
    selection_by_job[CLINICAL_SAFETY_JOB] = (clinical_anchors - {removed_anchor}) | {
        MANUAL_ADD_ANCHOR
    }

    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id="source",
        selections=_selections_from_sets(selection_by_job),
        project_root=tmp_path,
    )

    resolved_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CLINICAL_SAFETY_JOB
        / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    )
    assert resolved_path.is_file()
    effective_anchors = {
        str((zone.get("match") or {}).get("matched_heading_block_id"))
        for zone in load_json(resolved_path).get("matched_zones") or []
    }
    assert MANUAL_ADD_ANCHOR in effective_anchors
    assert removed_anchor not in effective_anchors


def test_unknown_heading_rejected(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selection_by_job = _selections_by_job(slot_record)
    selection_by_job[CLINICAL_SAFETY_JOB].add("C9999")

    with pytest.raises(ValueError, match="not a known heading"):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=_selections_from_sets(selection_by_job),
            project_root=tmp_path,
        )


def test_manual_add_wrong_job_rejected(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    _assert_manual_add_anchor_available(slot_record)
    selection_by_job = _selections_by_job(slot_record)
    selection_by_job[OVERVIEW_JOB].add(MANUAL_ADD_ANCHOR)

    with pytest.raises(ValueError, match="ownership mismatch"):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=_selections_from_sets(selection_by_job),
            project_root=tmp_path,
        )


def test_automatic_owner_wins_over_manual_default(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selection_by_job = _selections_by_job(slot_record)
    overview_anchor = min(selection_by_job[OVERVIEW_JOB])
    selection_by_job[CLINICAL_SAFETY_JOB].add(overview_anchor)

    with pytest.raises(ValueError, match="ownership mismatch"):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=_selections_from_sets(selection_by_job),
            project_root=tmp_path,
        )


def test_manual_add_projection_consumes_effective_zone_match(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    _assert_manual_add_anchor_available(slot_record)
    selection_by_job = _selections_by_job(slot_record)
    selection_by_job[CLINICAL_SAFETY_JOB].add(MANUAL_ADD_ANCHOR)
    resolved_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CLINICAL_SAFETY_JOB
        / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    )

    with patch.object(
        flow_module,
        "run_filter_output_projection_stage",
        wraps=flow_module.run_filter_output_projection_stage,
    ) as projection_stage:
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=_selections_from_sets(selection_by_job),
            project_root=tmp_path,
        )

    clinical_calls = [
        call
        for call in projection_stage.call_args_list
        if call.kwargs.get("filter_job_id") == CLINICAL_SAFETY_JOB
    ]
    assert clinical_calls
    assert clinical_calls[0].kwargs["zone_match_bundle_path"] == resolved_path


def test_resume_uses_shared_continuation_helper(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )

    with patch.object(
        flow_module,
        "_continue_slot_after_candidate_scope",
        wraps=flow_module._continue_slot_after_candidate_scope,
    ) as continuation:
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    assert continuation.call_count == 1


def test_invalid_decision_remains_paused(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = (
        FilterJobCandidateScopeSelection(
            filter_job_id=slot_record["filter_job_ids"][0],
            anchor_block_ids=("UNKNOWN_ANCHOR",),
        ),
        FilterJobCandidateScopeSelection(
            filter_job_id=slot_record["filter_job_ids"][1],
            anchor_block_ids=("UNKNOWN_ANCHOR",),
        ),
    )

    with (
        patch.object(
            flow_module, "run_filter_output_projection_stage"
        ) as projection_stage,
        pytest.raises(ValueError, match="not a known heading"),
    ):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    projection_stage.assert_not_called()
    summary = load_json(paused.flow_run_summary_path)
    assert summary["status"] in {"partial", "failed"}
    assert summary["slots"][0]["status"] in {"partial", "failed"}


def test_resume_does_not_rerun_upstream_stages(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )

    with (
        patch.object(flow_module, "run_document_processing_launch_extract") as intake,
        patch.object(flow_module, "run_prepare_analysis_operation") as prepare,
        patch.object(flow_module, "run_doc_meta_stage") as doc_meta,
        patch.object(flow_module, "run_filter_stage") as filter_stage,
    ):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    intake.assert_not_called()
    prepare.assert_not_called()
    doc_meta.assert_not_called()
    filter_stage.assert_not_called()


def test_repeated_resume_rejected(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id="source",
        selections=selections,
        project_root=tmp_path,
    )

    with pytest.raises(FlowResumeError, match="not paused_at_candidate_scope"):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )


def test_projection_failure_persists_decision(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )

    with (
        patch.object(
            flow_module,
            "run_filter_output_projection_stage",
            side_effect=RuntimeError("projection failed"),
        ),
        pytest.raises(RuntimeError, match="projection failed"),
    ):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )

    decision_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    assert decision_path.is_file()
    summary = load_json(paused.flow_run_summary_path)
    assert summary["slots"][0]["status"] in {"partial", "failed"}


def test_multi_slot_resume_completes_entire_flow(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    uploads = {"source_a": SAMPLE_DOCX, "source_b": SECOND_SAMPLE_DOCX}
    paused = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads=uploads,
        project_root=tmp_path,
    )
    decisions = _automatic_decisions_for_capability(
        paused,
        DSUR_UPDATED_IB_CONSISTENCY_QC,
    )

    resumed = _resume_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        paused_report=paused,
        decisions_by_slot=decisions,
        project_root=tmp_path,
    )

    assert resumed.flow_run_id == paused.flow_run_id
    assert resumed.result.paused_at_candidate_scope is False
    summary = load_json(resumed.flow_run_summary_path)
    assert summary["slots"][0]["status"] == "success"
    assert summary["slots"][1]["status"] == "success"
    assert "evidence_comparison" in summary


class _FakeComparisonExecutionDependencies(EvidenceComparisonExecutionDependencies):
    """Minimal Comparison dependencies for resume gating tests."""


def _ready_comparison_handoff_resolution() -> EvidenceComparisonHandoffResolution:
    binding = INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS.resolve_consumer_binding(
        DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id
    )
    assert binding is not None
    return EvidenceComparisonHandoffResolution(
        status=EvidenceComparisonHandoffResolutionStatus.READY,
        consumer_binding=binding,
        handoff=EvidenceComparisonHandoff(
            consumer_binding=binding,
            participants=(
                EvidenceComparisonParticipantReference(
                    role_id="source_a",
                    slot_id="source_a",
                    semantic_module_id="clinical_safety",
                    declared_output_path=Path("runs/fake/source_a"),
                ),
                EvidenceComparisonParticipantReference(
                    role_id="source_b",
                    slot_id="source_b",
                    semantic_module_id="clinical_safety",
                    declared_output_path=Path("runs/fake/source_b"),
                ),
            ),
        ),
    )


def test_comparison_runs_after_flow_level_resume(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    uploads = {"source_a": SAMPLE_DOCX, "source_b": SECOND_SAMPLE_DOCX}

    paused = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads=uploads,
        project_root=tmp_path,
    )
    decisions = _automatic_decisions_for_capability(
        paused,
        DSUR_UPDATED_IB_CONSISTENCY_QC,
    )
    comparison_stage_result = EvidenceComparisonStageResult(
        output_dir=tmp_path / "comparison",
        run_id="evidence_comparison_dsur_updated_ib",
        stage_executor_id="fake_comparison_executor",
        run_status="success",
        declared_output_path=tmp_path / "comparison" / "findings.json",
        run_summary_path=tmp_path / "comparison" / "run_summary.json",
    )
    with (
        patch.object(
            flow_module,
            "resolve_evidence_comparison_handoff",
            return_value=_ready_comparison_handoff_resolution(),
        ),
        patch.object(
            flow_module,
            "run_evidence_comparison_stage",
            return_value=comparison_stage_result,
        ) as comparison_stage,
    ):
        final_report = _resume_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            paused_report=paused,
            decisions_by_slot=decisions,
            project_root=tmp_path,
            evidence_comparison_consumer_bindings=(
                INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS
            ),
            evidence_comparison_execution_dependencies=(
                _FakeComparisonExecutionDependencies()
            ),
        )
    assert final_report.result.paused_at_candidate_scope is False
    comparison_stage.assert_called_once()


def test_partial_slot_decisions_rejected_for_multi_slot_flow(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    uploads = {"source_a": SAMPLE_DOCX, "source_b": SECOND_SAMPLE_DOCX}
    paused = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads=uploads,
        project_root=tmp_path,
    )
    with pytest.raises(FlowResumeError, match="missing paused slot"):
        _resume_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source_a",
            selections=_automatic_decisions_for_slot(paused, "source_a"),
            project_root=tmp_path,
        )


def test_unknown_slot_decision_rejected(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    selections = _automatic_decisions_for_slot(paused, "source")
    with pytest.raises(FlowResumeError, match="unknown slot"):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            decisions_by_slot={
                "source": selections,
                "unexpected": selections,
            },
            project_root=tmp_path,
        )


def test_start_and_resume_delegate_shared_finalization_helper(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    with patch.object(
        flow_module,
        "_finalize_flow_with_evidence_comparison",
        wraps=flow_module._finalize_flow_with_evidence_comparison,
    ) as finalize_flow:
        start_report = flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
            participant_inputs=_participant_inputs(("source",)),
            prepare_analysis_config_registry=registry,
            git_provenance=_git_prov(),
            candidate_scope_decision_mode=CandidateScopeDecisionMode.AUTOMATIC_CONTINUE,
            **clinical_flow_invocation_kwargs(),
        )
    assert finalize_flow.call_count == 1
    assert start_report.result.paused_at_candidate_scope is False

    paused = flow_module.run_document_consistency_qc_flow(
        project_root=tmp_path,
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads=admitted_source_bindings({"source": SAMPLE_DOCX}),
        participant_inputs=_participant_inputs(("source",)),
        prepare_analysis_config_registry=registry,
        git_provenance=_git_prov(),
        candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
        **clinical_flow_invocation_kwargs(),
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    resume_kwargs = clinical_flow_resume_invocation_kwargs()
    with patch.object(
        flow_module,
        "_finalize_flow_with_evidence_comparison",
        wraps=flow_module._finalize_flow_with_evidence_comparison,
    ) as finalize_flow:
        flow_module.resume_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            flow_run_id=paused.flow_run_id,
            candidate_scope_decisions_by_slot={"source": selections},
            git_provenance=_git_prov(),
            **resume_kwargs,
        )
    assert finalize_flow.call_count == 1


def test_finalize_flow_comparison_failure_persists_and_reraises(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    with (
        patch.object(
            flow_module,
            "resolve_evidence_comparison_handoff",
            return_value=_ready_comparison_handoff_resolution(),
        ),
        patch.object(
            flow_module,
            "run_evidence_comparison_stage",
            side_effect=RuntimeError("comparison setup failed"),
        ),
        pytest.raises(RuntimeError, match="comparison setup failed"),
    ):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
            evidence_comparison_consumer_bindings=(
                INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS
            ),
            evidence_comparison_execution_dependencies=(
                _FakeComparisonExecutionDependencies()
            ),
        )
    summary = load_json(paused.flow_run_summary_path)
    evidence_comparison = summary.get("evidence_comparison")
    assert evidence_comparison is not None
    assert evidence_comparison["run_status"] == "failed"


def test_start_delegates_shared_canonical_slot_helper(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    with patch.object(
        flow_module,
        "_run_canonical_slot",
        wraps=flow_module._run_canonical_slot,
    ) as run_canonical_slot:
        _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
            candidate_scope_decision_mode=CandidateScopeDecisionMode.AUTOMATIC_CONTINUE,
        )
    assert run_canonical_slot.call_count == 1


def test_multi_slot_resume_does_not_use_canonical_slot_helper(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    uploads = {"source_a": SAMPLE_DOCX, "source_b": SECOND_SAMPLE_DOCX}
    paused = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads=uploads,
        project_root=tmp_path,
    )
    decisions = _automatic_decisions_for_capability(
        paused,
        DSUR_UPDATED_IB_CONSISTENCY_QC,
    )
    with (
        patch.object(flow_module, "_run_canonical_slot") as run_canonical_slot,
        patch.object(
            flow_module,
            "_run_canonical_slot_through_candidate_scope_checkpoint",
        ) as run_through_checkpoint,
        patch.object(
            flow_module,
            "_continue_slot_after_candidate_scope",
            wraps=flow_module._continue_slot_after_candidate_scope,
        ) as continue_slot,
        patch.object(flow_module, "run_filter_stage") as filter_stage,
    ):
        _resume_flow(
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            paused_report=paused,
            decisions_by_slot=decisions,
            project_root=tmp_path,
        )
    run_canonical_slot.assert_not_called()
    run_through_checkpoint.assert_not_called()
    assert continue_slot.call_count == 2
    filter_stage.assert_not_called()


def test_paused_slot_resume_does_not_use_canonical_slot_helper(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, "source")
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    with (
        patch.object(flow_module, "_run_canonical_slot") as run_canonical_slot,
        patch.object(
            flow_module,
            "_continue_slot_after_candidate_scope",
            wraps=flow_module._continue_slot_after_candidate_scope,
        ) as continue_slot,
        patch.object(flow_module, "run_filter_stage") as filter_stage,
    ):
        _resume_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            paused_report=paused,
            slot_id="source",
            selections=selections,
            project_root=tmp_path,
        )
    run_canonical_slot.assert_not_called()
    continue_slot.assert_called_once()
    filter_stage.assert_not_called()
