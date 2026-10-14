"""Task-owned composition against persisted application fixtures."""

from __future__ import annotations

# ruff: noqa: E402

from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.task_run import create_task_run_for_flow
from artifacts.task_input import TaskInputEntry, build_task_input_manifest
from artifacts.zone_match_bundle import build_zone_match_bundle
from artifacts.candidate_scope_decision import validate_candidate_scope_decision
from artifacts.finding_review_state import build_finding_review_state_payload
from artifacts.source_annotation_state import build_source_annotation_state_payload
from artifacts.qc_report import validate_qc_report
from runtime.io import load_json, save_json
from task.clinical_trial_doc_qc.report_read import (
    QcReportReadError,
    QcReportConsistencyError,
    load_qc_report,
)
from task.clinical_trial_doc_qc.task_ids import INTERNAL_DSUR_QC_TASK_ID
from tests.test_internal_result_read import (
    _default_extract_blocks,
    _write_minimal_internal_result_fixture,
    _TEST_FILE_HASH,
)

TASK = "task_run_report_test"


def write_fixture(root, *, zero=False, fallback=False):
    final = (
        []
        if zero
        else [
            {
                "finding_id": "L002",
                "label": "need_review",
                "conclusion": "Across sections",
                "comparison_mode_id": "scope_local",
                "source_finding_ids": ["L010", "L011"],
                "source_sentence_aliases": ["T0003", "T0001", "T0002"],
            },
            {
                "finding_id": "L001",
                "label": "fail",
                "conclusion": "Shared source",
                "comparison_mode_id": "scope_local",
                "source_finding_ids": ["L012"],
                "source_sentence_aliases": ["T0001"],
            },
        ]
    )
    flow = _write_minimal_internal_result_fixture(
        root,
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [],
            }
        ],
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=_default_extract_blocks(),
        final_findings=final,
        finalization_status="completed_with_fallback" if fallback else "completed",
        fallback_comparison_modes=["scope_local"] if fallback else [],
    )
    flow_root = root / "runs/document_consistency_qc/test_internal_result"
    summary_path = flow_root / "flow_run_summary.json"
    summary = load_json(summary_path)
    slot = summary["slots"][0]
    slot["original_file_name"] = "test.docx"
    slot_root = flow_root / "participants/source"
    job_root = slot_root / "filter/test"
    job_root.mkdir(parents=True)
    auto_path = job_root / "zone_match_bundle.json"
    scope_root = slot_root / "candidate_scope"
    resolved_path = scope_root / "test/resolved_zone_match_bundle.json"
    resolved_path.parent.mkdir(parents=True)
    bundle = build_zone_match_bundle(
        {
            "doc_id": "doc_test",
            "file_hash": _TEST_FILE_HASH,
            "zone_config_name": "test",
            "zone_config_version": "1",
            "language": "zh",
            "resolved_filter_strategy_id": "heading",
            "matched_zones": [
                {
                    "zone_id": "Z1",
                    "match": {"matched_heading_block_id": "C0001"},
                    "blocks": [],
                    "table_blocks": [],
                }
            ],
        }
    )
    save_json(auto_path, bundle)
    save_json(resolved_path, bundle)
    decision_path = scope_root / "decision.json"
    save_json(
        decision_path,
        validate_candidate_scope_decision(
            {
                "artifact_type": "document_consistency_qc_candidate_scope_decision",
                "schema_version": "0.2.0",
                "checkpoint_kind": "candidate_scope",
                "flow_run_id": flow,
                "slot_id": "source",
                "decided_at": "2026-01-01T00:00:00Z",
                "filter_job_order": ["test"],
                "candidate_selections": [
                    {
                        "filter_job_id": "test",
                        "anchor_block_ids": ["C0001"],
                        "resolved_bundle_ref": resolved_path.relative_to(
                            root
                        ).as_posix(),
                        "resolution": {
                            "kind": "automatic_unchanged",
                            "upstream_bundle_ref": auto_path.relative_to(
                                root
                            ).as_posix(),
                        },
                    }
                ],
            }
        ),
    )
    slot["filter_job_ids"] = ["test"]
    slot["filter_jobs"] = [
        {
            "filter_job_id": "test",
            "source_language": "zh",
            "zone_config_name": "test",
            "zone_config_version": "1",
            "filter_run_id": "filter_test",
            "output_dir": job_root.as_posix(),
            "zone_match_bundle_path": auto_path.as_posix(),
            "coverage_bundle_path": (job_root / "coverage_bundle.json").as_posix(),
            "run_summary_path": (job_root / "run_summary.json").as_posix(),
        }
    ]
    slot["candidate_scope_decision_path"] = decision_path.as_posix()
    slot["projection_jobs"] = [
        {
            "filter_job_id": "test",
            "projection_run_id": "projection_test",
            "output_dir": (slot_root / "filter_output_projection/test").as_posix(),
            "projection_bundle_path": (
                slot_root / "filter_output_projection/test/projection_bundle.json"
            ).as_posix(),
            "run_summary_path": (
                slot_root / "filter_output_projection/test/run_summary.json"
            ).as_posix(),
            "projected_source_count": 1,
            "semantic_outcome_count": 1,
        }
    ]
    slot["route_semantic_modules"] = []
    save_json(summary_path, summary)
    analysis_path = Path(slot["analysis_bundle_path"])
    analysis_path.parent.mkdir(parents=True)
    save_json(
        analysis_path,
        {"doc_id": "doc_test", "content_blocks": _default_extract_blocks()},
    )
    create_task_run_for_flow(
        project_root=root,
        task_run_id=TASK,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        flow_id="document_consistency_qc",
        flow_run_id=flow,
    )
    task_root = root / "runs/task_runs" / TASK
    save_json(
        task_root / "task_input.json",
        build_task_input_manifest(
            task_run_id=TASK,
            inputs=[
                TaskInputEntry(
                    task_slot_id="source",
                    file_hash=_TEST_FILE_HASH,
                    original_file_name="test.docx",
                    source_ref=f"runs/task_runs/{TASK}/inputs/source/source/test.docx",
                )
            ],
        ),
    )
    return flow, flow_root


@pytest.fixture
def state(tmp_path):
    flow, flow_root = write_fixture(tmp_path)
    return tmp_path, flow, flow_root


def report(state):
    return load_qc_report(project_root=state[0], task_run_id=TASK)


def write_annotations(state, entries):
    root, flow, flow_root = state
    records = {}
    for ann_id, block, kind, ranged in entries:
        value = {
            "annotation_id": ann_id,
            "anchor": {
                "slot_id": "source",
                "doc_id": "doc_test",
                "block_id": block,
                "sentence_id": block + ":S001",
            },
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }
        if kind is not None:
            value["kind"] = kind
        if ranged:
            value["range"] = {"start_offset": 0, "end_offset": 1}
        if kind == "edit":
            value["replacement_text"] = "fragment"
        if kind == "comment":
            value["content"] = "check"
        records[ann_id] = value
    path = flow_root / "source_annotations/annotations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(
        path,
        build_source_annotation_state_payload(flow_run_id=flow, annotations=records),
    )


def test_complete_product_final_graph_and_identity(state):
    result = report(state)
    validate_qc_report(json.loads(json.dumps(result, ensure_ascii=False)))
    assert result["task"]["task_run_id"] == TASK
    assert result["task"]["display_name"] == "研发期间安全性更新报告（DSUR）"
    assert [f["finding_id"] for f in result["findings"]] == ["L002", "L001"]
    assert result["findings"][0]["source_finding_ids"] == ["L010", "L011"]
    sources = {e["evidence_ref"]: e for e in result["source_evidence"]}
    assert len(sources) == 3
    assert [
        sources[ref]["anchor"]["block_id"]
        for ref in result["findings"][0]["evidence_refs"]
    ] == ["C0004", "C0002", "C0003"]
    assert sources[result["findings"][0]["evidence_refs"][0]]["heading_path"] == [
        "Scope B"
    ]
    assert result["findings"][1]["evidence_refs"] == [
        result["findings"][0]["evidence_refs"][1]
    ]
    doc = result["documents"][0]
    assert doc["task_input"] == {"task_slot_id": "source"}
    assert doc["file_hash"] == _TEST_FILE_HASH
    assert doc["original_file_name"] == "test.docx"
    contribution = result["contributions"][0]
    assert contribution["function_display"] == {
        "name": "Writing Accuracy & Consistency",
        "description": "撰写准确性与一致性核查",
    }
    assert contribution["content_domains"][0]["finding_refs"] == [
        f["finding_ref"] for f in result["findings"]
    ]
    assert contribution["configuration"]["availability"] == "available"
    selection = contribution["configuration"]["selections"][0]
    assert selection["automatic_scope_items"] == [
        {"anchor_block_id": "C0001", "heading_path": ["Scope A"], "doc_order_index": 1}
    ]
    assert selection["effective_scope_items"] == selection["automatic_scope_items"]
    assert selection["added_scope_items"] == []
    assert selection["removed_scope_items"] == []
    assert result["integrity"]["status"] == "complete"


def test_annotation_colocation_and_shared_entity(state):
    write_annotations(
        state,
        [
            ("ann_edit", "C0002", "edit", True),
            ("ann_comment", "C0002", "comment", False),
        ],
    )
    result = report(state)
    assert len(result["source_annotations"]) == 2
    for value in result["source_annotations"]:
        assert value["related_finding_refs"] == [
            f["finding_ref"] for f in result["findings"]
        ]
    evidence = next(
        e for e in result["source_evidence"] if e["anchor"]["block_id"] == "C0002"
    )
    assert set(evidence["annotation_refs"]) == {
        a["annotation_ref"] for a in result["source_annotations"]
    }
    comment = next(a for a in result["source_annotations"] if a["kind"] == "comment")
    assert comment["selected_original_text"] == comment["original_sentence_text"]
    assert result["independent_review_record_refs"] == []


def test_independent_edit_comment_and_highlight(tmp_path):
    flow, flow_root = write_fixture(tmp_path, zero=True)
    state = tmp_path, flow, flow_root
    write_annotations(
        state,
        [
            ("ann_edit", "C0002", "edit", True),
            ("ann_comment", "C0003", "comment", False),
            ("ann_highlight", "C0004", "highlight", True),
        ],
    )
    result = report(state)
    independent = {
        a["annotation_ref"]
        for a in result["source_annotations"]
        if a["kind"] in {"edit", "comment"}
    }
    assert set(result["independent_review_record_refs"]) == independent
    assert all(a["related_finding_refs"] == [] for a in result["source_annotations"])


def test_independent_annotation_locations_come_from_canonical_source(tmp_path):
    flow, flow_root = write_fixture(tmp_path, zero=True)
    state = tmp_path, flow, flow_root
    write_annotations(
        state,
        [
            ("ann_edit", "C0002", "edit", True),
            ("ann_comment", "C0004", "comment", False),
        ],
    )
    result = report(state)
    assert {
        a["annotation_id"]: a["heading_path"] for a in result["source_annotations"]
    } == {"ann_edit": ["Scope A"], "ann_comment": ["Scope B"]}
    validate_qc_report(result)


def test_legacy_annotation_degrades_only_review_integrity(state):
    write_annotations(state, [("ann_legacy", "C0002", None, False)])
    result = report(state)
    assert result["source_annotations"] == []
    assert len(result["findings"]) == 2
    assert result["integrity"]["status"] == "partial"
    assert result["integrity"]["limitations"]
    assert (
        result["contributions"][0]["content_domains"][0]["integrity"]["status"]
        == "complete"
    )


@pytest.mark.parametrize("decision", ["pending", "confirmed", "ignored"])
def test_review_disposition(state, decision):
    _, flow, flow_root = state
    path = flow_root / "finding_review/review.json"
    from artifacts.finding_review_state import (
        FINDING_REVIEW_STATE_FILENAME,
        FINDING_REVIEW_OPERATION_DIRNAME,
    )

    path = flow_root / FINDING_REVIEW_OPERATION_DIRNAME / FINDING_REVIEW_STATE_FILENAME
    path.parent.mkdir(parents=True)
    save_json(
        path,
        build_finding_review_state_payload(
            flow_run_id=flow,
            findings={
                "L002": {
                    "finding_id": "L002",
                    "decision": decision,
                    "marked": True,
                    "note": "saved note",
                    "updated_at": "2026-01-03T00:00:00Z",
                }
            },
        ),
    )
    result = report(state)
    review = result["findings"][0]["review_disposition"]
    assert review == {
        "decision": decision,
        "marked": True,
        "note": "saved note",
        "updated_at": "2026-01-03T00:00:00Z",
    }
    assert "resolved" not in review


def test_missing_review_is_pending_untouched(state):
    review = report(state)["findings"][0]["review_disposition"]
    assert review == {
        "decision": "pending",
        "marked": False,
        "note": None,
        "updated_at": None,
    }


@pytest.mark.parametrize("partial", [False, True])
def test_zero_findings_is_not_a_verdict(tmp_path, partial):
    flow, flow_root = write_fixture(tmp_path, zero=True)
    if partial:
        _apply_persisted_partial_execution(flow_root)
    result = report((tmp_path, flow, flow_root))
    assert result["findings"] == []
    assert result["integrity"]["status"] == ("partial" if partial else "complete")
    assert "verdict" not in result


def test_lossless_fallback_preserves_complete_result_with_limitation(tmp_path):
    flow, flow_root = write_fixture(tmp_path, fallback=True)
    result = report((tmp_path, flow, flow_root))
    integrity = result["contributions"][0]["integrity"]
    assert integrity["finalization_status"] == "completed_with_fallback"
    assert integrity["fallback_comparison_modes"] == ["scope_local"]
    assert result["integrity"]["status"] == "complete"
    assert integrity["status"] == "complete"
    assert result["integrity"]["limitations"]
    assert all("scope_local" not in text for text in result["integrity"]["limitations"])


def _apply_persisted_partial_execution(flow_root: Path) -> None:
    path = flow_root / "flow_run_summary.json"
    summary = load_json(path)
    summary["status"] = "partial"
    summary["evidence_comparison"]["run_status"] = "partial_failure"
    save_json(path, summary)


def test_lossless_fallback_with_persisted_partial_execution_stays_result_complete(
    tmp_path,
):
    flow, flow_root = write_fixture(tmp_path, fallback=True)
    _apply_persisted_partial_execution(flow_root)
    result = report((tmp_path, flow, flow_root))
    contribution = result["contributions"][0]
    integrity = contribution["integrity"]
    assert contribution["execution"]["outcome"] == "partial"
    assert integrity["finalization_status"] == "completed_with_fallback"
    assert integrity["fallback_comparison_modes"] == ["scope_local"]
    assert integrity["status"] == "complete"
    assert result["integrity"]["status"] == "complete"
    assert integrity["limitations"]
    assert all("scope_local" not in text for text in integrity["limitations"])
    validate_qc_report(result)


def test_partial_failure_without_lossless_fallback_marks_incomplete_result(tmp_path):
    flow, flow_root = write_fixture(tmp_path, fallback=False)
    _apply_persisted_partial_execution(flow_root)
    result = report((tmp_path, flow, flow_root))
    assert result["contributions"][0]["execution"]["outcome"] == "partial"
    assert result["integrity"]["status"] == "partial"


def test_fallback_does_not_hide_incomplete_scope_coverage(tmp_path):
    flow, flow_root = write_fixture(tmp_path, fallback=True)
    _apply_persisted_partial_execution(flow_root)
    path = flow_root / "participants/source/evidence_comparison/run_summary.json"
    summary = load_json(path)
    summary["jobs"][0]["assessment"]["status"] = "failed"
    save_json(path, summary)
    result = report((tmp_path, flow, flow_root))
    assert result["contributions"][0]["execution"]["outcome"] == "partial"
    assert result["integrity"]["status"] != "complete"


def test_configuration_unavailable_retains_product_final(state):
    path = state[2] / "participants/source/candidate_scope/decision.json"
    path.unlink()
    result = report(state)
    assert result["contributions"][0]["configuration"] == {
        "availability": "unavailable",
        "persisted_decision_at": None,
        "selections": [],
    }
    assert len(result["findings"]) == 2
    assert result["integrity"]["status"] == "partial"


def test_incomplete_coverage_cannot_be_hidden(state):
    path = state[2] / "participants/source/evidence_comparison/run_summary.json"
    summary = load_json(path)
    summary["jobs"][0]["assessment"]["status"] = "failed"
    save_json(path, summary)
    result = report(state)
    domain = result["contributions"][0]["content_domains"][0]
    assert domain["integrity"]["status"] != "complete"
    assert result["integrity"]["status"] != "complete"


@pytest.mark.parametrize(
    "mismatch",
    [
        "task_flow",
        "input_hash",
        "input_name",
        "result",
        "review",
        "annotation",
        "config",
    ],
)
def test_identity_mismatches_rejected(state, monkeypatch, mismatch):
    root, flow, flow_root = state
    from task.clinical_trial_doc_qc import report_read

    if mismatch == "result":
        original = report_read.load_document_consistency_qc_result
        monkeypatch.setattr(
            report_read,
            "load_document_consistency_qc_result",
            lambda **kw: replace(original(**kw), flow_run_id="other"),
        )
    elif mismatch == "review":
        original = report_read.load_finding_review_state
        monkeypatch.setattr(
            report_read,
            "load_finding_review_state",
            lambda **kw: replace(original(**kw), flow_run_id="other"),
        )
    elif mismatch == "annotation":
        write_annotations(state, [("ann_test", "C0002", "comment", False)])
        path = flow_root / "source_annotations/annotations.json"
        payload = load_json(path)
        payload["flow_run_id"] = "other"
        save_json(path, payload)
    elif mismatch == "config":
        path = flow_root / "participants/source/candidate_scope/decision.json"
        payload = load_json(path)
        payload["flow_run_id"] = "other"
        save_json(path, payload)
    else:
        path = (
            root
            / "runs/task_runs"
            / TASK
            / ("task_run.json" if mismatch == "task_flow" else "task_input.json")
        )
        payload = load_json(path)
        if mismatch == "task_flow":
            payload["flow_runs"][0]["flow_id"] = "other"
        else:
            payload["inputs"][0][
                "file_hash" if mismatch == "input_hash" else "original_file_name"
            ] = "sha256:" + "0" * 64 if mismatch == "input_hash" else "other.docx"
        save_json(path, payload)
    with pytest.raises(QcReportReadError):
        report(state)


def test_stable_refs_and_detached_json(state):
    first, second = report(state), report(state)
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second
    first["findings"][0]["conclusion"] = "local change"
    assert report(state)["findings"][0]["conclusion"] == "Across sections"


def test_changes_during_read_rejected(state, monkeypatch):
    from task.clinical_trial_doc_qc import report_read

    original = report_read.load_task_run
    calls = 0

    def changed(**kw):
        nonlocal calls
        calls += 1
        model = original(**kw)
        if calls > 1:
            model["updated_at"] = "later"
        return model

    monkeypatch.setattr(report_read, "load_task_run", changed)
    with pytest.raises(QcReportConsistencyError):
        report(state)


def test_unusable_annotation_keeps_other_saved_records_and_findings(state):
    write_annotations(
        state,
        [("ann_valid", "C0002", "comment", False), ("ann_bad", "C0003", "edit", True)],
    )
    path = state[2] / "source_annotations/annotations.json"
    payload = load_json(path)
    payload["annotations"]["ann_bad"]["range"]["end_offset"] = 999
    save_json(path, payload)
    result = report(state)
    assert [a["annotation_id"] for a in result["source_annotations"]] == ["ann_valid"]
    assert len(result["findings"]) == 2
    assert result["integrity"]["status"] == "partial"
    assert (
        result["contributions"][0]["content_domains"][0]["integrity"]["status"]
        == "complete"
    )


def test_empty_source_for_optional_comment_degrades_instead_of_losing_result(tmp_path):
    flow, flow_root = write_fixture(tmp_path, zero=True)
    state = tmp_path, flow, flow_root
    write_annotations(state, [("ann_empty", "C0002", "comment", False)])
    path = flow_root / "participants/source/extract/bundle.json"
    bundle = load_json(path)
    bundle["content_blocks"][1]["sentences"][0]["raw_text"] = ""
    save_json(path, bundle)
    result = report(state)
    assert result["findings"] == []
    assert result["source_annotations"] == []
    assert result["integrity"]["status"] == "partial"


@pytest.mark.parametrize(
    "failure", ["result_missing", "extract_missing", "sentence_missing", "paused"]
)
def test_missing_core_inputs_do_not_make_empty_report(state, failure):
    from task.clinical_trial_doc_qc.report_read import QcReportUnavailableError

    root, _, flow_root = state
    if failure == "result_missing":
        (
            flow_root / "participants/source/evidence_comparison/final_findings.json"
        ).unlink()
    elif failure == "extract_missing":
        (flow_root / "participants/source/extract/bundle.json").unlink()
    elif failure == "sentence_missing":
        path = flow_root / "participants/source/extract/bundle.json"
        bundle = load_json(path)
        bundle["content_blocks"][1]["sentences"] = []
        save_json(path, bundle)
    else:
        path = flow_root / "flow_run_summary.json"
        summary = load_json(path)
        summary["status"] = summary["slots"][0]["status"] = "paused_at_candidate_scope"
        save_json(path, summary)
    with pytest.raises(QcReportUnavailableError):
        load_qc_report(project_root=root, task_run_id=TASK)


def test_refs_stable_when_product_final_order_changes(state):
    first = report(state)
    path = state[2] / "participants/source/evidence_comparison/final_findings.json"
    payload = load_json(path)
    payload["findings"].reverse()
    save_json(path, payload)
    second = report(state)
    assert {f["finding_id"]: f["finding_ref"] for f in first["findings"]} == {
        f["finding_id"]: f["finding_ref"] for f in second["findings"]
    }
    assert {
        e["anchor"]["sentence_id"]: e["evidence_ref"] for e in first["source_evidence"]
    } == {
        e["anchor"]["sentence_id"]: e["evidence_ref"] for e in second["source_evidence"]
    }


def test_evidence_alias_duplicates_do_not_duplicate_refs(state, monkeypatch):
    from task.clinical_trial_doc_qc import report_read

    original = report_read.load_document_consistency_qc_result

    def duplicated(**kw):
        result = original(**kw)
        first = result.findings[0]
        return replace(
            result,
            findings=(
                replace(
                    first, evidence_refs=first.evidence_refs + (first.evidence_refs[0],)
                ),
                *result.findings[1:],
            ),
        )

    monkeypatch.setattr(report_read, "load_document_consistency_qc_result", duplicated)
    assert len(report(state)["findings"][0]["evidence_refs"]) == 3


def test_readable_failed_execution_keeps_result_with_failed_integrity(state):
    path = state[2] / "flow_run_summary.json"
    summary = load_json(path)
    summary["status"] = summary["slots"][0]["status"] = "failed"
    save_json(path, summary)
    result = report(state)
    assert len(result["findings"]) == 2
    assert result["integrity"]["status"] == "failed"
    assert result["integrity"]["limitations"]


def test_no_report_artifact_is_persisted(state):
    root = state[0]
    before = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    report(state)
    after = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    assert before == after


def test_real_completed_flow_and_task_input_compose(tmp_path):
    from types import SimpleNamespace
    from capability import INTERNAL_DSUR_CONSISTENCY_QC
    from application.document_consistency_qc.document_read import (
        load_document_read_execution,
    )
    from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
        automatic_candidate_scope_selections,
    )
    from task.clinical_trial_doc_qc.task_input import (
        materialize_task_input_source,
        persist_task_input,
    )
    from tests.candidate_scope_isolation import (
        prepare_paused_canonical_flow,
        SHOWCASE_DOCX,
    )
    from tests.test_document_consistency_qc_candidate_scope_resume import _resume_flow
    from application.clinical_trial_doc_consistency_qc.evidence_comparison_consumer_installation import (
        INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
    )

    config, flow, slot_id = prepare_paused_canonical_flow(tmp_path)
    root = config.workspace_root
    execution = load_document_read_execution(project_root=root, flow_run_id=flow)
    slot = execution.slot_provenance[0]
    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=SimpleNamespace(flow_run_id=flow),
        project_root=root,
        slot_id=slot_id,
        selections=automatic_candidate_scope_selections(
            filter_job_ids=slot.filter_job_ids, filter_jobs=slot.filter_jobs
        ),
        projection_runtime_dependencies=config.projection_runtime_dependencies,
        evidence_source_preparation_execution_dependencies=config.evidence_source_preparation_execution_dependencies,
        evidence_comparison_execution_dependencies=config.evidence_comparison_execution_dependencies,
        evidence_comparison_consumer_bindings=INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
    )
    create_task_run_for_flow(
        project_root=root,
        task_run_id=TASK,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        flow_id="document_consistency_qc",
        flow_run_id=flow,
    )
    source_path = materialize_task_input_source(
        project_root=root,
        task_run_id=TASK,
        task_slot_id="source",
        source_path=SHOWCASE_DOCX,
    )
    persist_task_input(
        project_root=root,
        task_run_id=TASK,
        inputs=[
            TaskInputEntry(
                task_slot_id="source",
                file_hash=slot.file_hash,
                original_file_name=slot.original_file_name,
                source_ref=source_path.relative_to(root).as_posix(),
            )
        ],
    )
    result = load_qc_report(project_root=root, task_run_id=TASK)
    validate_qc_report(result)
    assert result["contributions"][0]["execution"]["outcome"] == "success"
    assert result["contributions"][0]["configuration"]["availability"] == "available"
    assert result["documents"][0]["original_file_name"] == SHOWCASE_DOCX.name


def test_missing_coverage_propagates_unavailable_without_pass_claim(
    tmp_path, monkeypatch
):
    from task.clinical_trial_doc_qc import report_read

    flow, flow_root = write_fixture(tmp_path, zero=True)
    original = report_read.load_document_consistency_qc_result
    monkeypatch.setattr(
        report_read,
        "load_document_consistency_qc_result",
        lambda **kw: replace(original(**kw), scope_results=()),
    )
    result = report((tmp_path, flow, flow_root))
    assert result["findings"] == []
    assert (
        result["contributions"][0]["content_domains"][0]["integrity"]["status"]
        == "unavailable"
    )
    assert result["contributions"][0]["integrity"]["status"] == "unavailable"
    assert result["integrity"]["status"] == "unavailable"
    assert result["integrity"]["limitations"]


def test_owner_requires_formal_module_context(state):
    path = state[2] / "flow_run_summary.json"
    summary = load_json(path)
    summary["evidence_comparison"]["participants"][0]["semantic_module_id"] = (
        "another_module"
    )
    save_json(path, summary)
    with pytest.raises(QcReportReadError):
        report(state)
