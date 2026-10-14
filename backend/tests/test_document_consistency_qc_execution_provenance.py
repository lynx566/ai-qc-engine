"""Tests for Document Consistency QC execution provenance and flow_run_summary."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.execution_provenance as execution_provenance_module
import execution_flow.document_consistency_qc.flow as flow_module
import execution_flow.document_processing_sequence as sequence_module
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    validate_flow_run_summary,
)
from capability import DSUR_UPDATED_IB_CONSISTENCY_QC, INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcParticipantRunInput,
)
from execution_flow.document_consistency_qc.flow_loader import load_flow_run_execution
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from steps.extract import run as run_extract_step
from steps.request_file_intake import run as run_request_file_intake_step
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.extract import ExtractDocumentInput, run_extract_operation
from runtime.io import load_json, save_json
from runtime.request_file_intake import run_request_file_intake_operation
from tests.document_consistency_qc_flow_helpers import (
    admit_participant_source_binding,
    clinical_flow_invocation_kwargs,
)
from tests.extract_test_helpers import build_test_processing_identity

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


def _flow_kwargs(
    *,
    capability_config,
    uploads: dict[str, Path | str],
    project_root: Path,
) -> dict[str, object]:
    admitted_uploads = {
        slot_id: admit_participant_source_binding(project_root, Path(path))
        for slot_id, path in uploads.items()
    }
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    return {
        **clinical_flow_invocation_kwargs(),
        "project_root": project_root,
        "capability_config": capability_config,
        "uploads": admitted_uploads,
        "participant_inputs": {
            slot_id: DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
            for slot_id in admitted_uploads
        },
        "prepare_analysis_config_registry": registry,
        "git_provenance": _git_prov(),
    }


def _run_flow(
    *,
    capability_config,
    uploads: dict[str, Path | str],
    project_root: Path,
):
    return flow_module.run_document_consistency_qc_flow(
        **_flow_kwargs(
            capability_config=capability_config,
            uploads=uploads,
            project_root=project_root,
        )
    )


def _stage_run_dir_names(project_root: Path, stage: str) -> set[str]:
    stage_root = project_root / "runs" / stage
    if not stage_root.is_dir():
        return set()
    return {path.name for path in stage_root.iterdir() if path.is_dir()}


def _flow_root(report) -> Path:
    return report.flow_run_summary_path.parent


def test_internal_capability_persists_under_flow_root(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    before_intake = _stage_run_dir_names(tmp_path, "request_file_intake")
    before_extract = _stage_run_dir_names(tmp_path, "extract")

    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )

    flow_root = _flow_root(report)
    intake_dir = flow_root / "participants" / "source" / "intake"
    extract_dir = flow_root / "participants" / "source" / "extract"
    assert not intake_dir.is_dir()
    assert extract_dir.is_dir()
    assert (extract_dir / "bundle.json").is_file()

    slot = report.result.slots[0]
    assert slot.admitted_source.file_hash
    assert slot.admitted_source.original_file_name
    assert slot.extract_report.result.document.output_dir == extract_dir.resolve()
    assert slot.extract_report.result.document.bundle_path.is_file()

    assert _stage_run_dir_names(tmp_path, "request_file_intake") == before_intake
    assert _stage_run_dir_names(tmp_path, "extract") - before_extract == set()


def test_cross_capability_persists_distinct_slot_sinks_under_flow_root(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    before_intake = _stage_run_dir_names(tmp_path, "request_file_intake")
    before_extract = _stage_run_dir_names(tmp_path, "extract")

    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={
            "source_a": SAMPLE_DOCX,
            "source_b": SECOND_SAMPLE_DOCX,
        },
        project_root=tmp_path,
    )

    flow_root = _flow_root(report)
    sinks = {
        slot.slot_id: (
            flow_root / "participants" / slot.slot_id / "intake",
            flow_root / "participants" / slot.slot_id / "extract",
        )
        for slot in report.result.slots
    }
    assert set(sinks) == {"source_a", "source_b"}
    assert sinks["source_a"][0] != sinks["source_b"][0]
    assert sinks["source_a"][1] != sinks["source_b"][1]

    for slot in report.result.slots:
        intake_dir, extract_dir = sinks[slot.slot_id]
        assert not intake_dir.is_dir()
        assert (extract_dir / "bundle.json").is_file()
        assert slot.admitted_source.file_hash
        assert slot.extract_report.result.document.output_dir == extract_dir.resolve()

    assert _stage_run_dir_names(tmp_path, "request_file_intake") == before_intake
    assert _stage_run_dir_names(tmp_path, "extract") - before_extract == set()


def test_standalone_intake_still_allocates_stage_root(tmp_path: Path) -> None:
    source = tmp_path / "standalone.docx"
    source.write_bytes(b"standalone-intake")
    before = _stage_run_dir_names(tmp_path, "request_file_intake")

    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
    )

    after = _stage_run_dir_names(tmp_path, "request_file_intake")
    assert len(after - before) == 1
    assert report.result.output_dir.parent == (tmp_path / "runs" / "request_file_intake").resolve()


def test_standalone_extract_still_allocates_stage_root(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    before = _stage_run_dir_names(tmp_path, "extract")

    report = run_extract_operation(
        project_root=tmp_path,
        document=ExtractDocumentInput(
            source_path=SAMPLE_DOCX,
            identity=build_test_processing_identity(SAMPLE_DOCX),
        ),
        extract_config_id="docx",
    )

    after = _stage_run_dir_names(tmp_path, "extract")
    assert len(after - before) == 1
    assert report.result.output_dir.parent == (tmp_path / "runs" / "extract").resolve()


def test_composed_flow_reaches_canonical_steps_through_runtime(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    with (
        patch(
            "runtime.request_file_intake.operations.run_request_file_intake_step",
            wraps=run_request_file_intake_step,
        ) as intake_step,
        patch(
            "runtime.extract.operations.run_extract_step",
            wraps=run_extract_step,
        ) as extract_step,
    ):
        report = _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    assert intake_step.call_count == 0
    assert extract_step.call_count == 1
    slot = report.result.slots[0]
    assert slot.extract_report.result.document.bundle_path.is_file()


def test_composed_flow_retains_in_memory_slot_results(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={
            "source_a": SAMPLE_DOCX,
            "source_b": SECOND_SAMPLE_DOCX,
        },
        project_root=tmp_path,
    )

    flow_root = _flow_root(report)
    assert len(report.result.slots) == 2
    for slot in report.result.slots:
        assert slot.admitted_source.file_hash
        assert slot.extract_report.result.document.bundle_path.is_file()
        assert slot.extract_report.result.document.output_dir.is_relative_to(flow_root)
        assert not (flow_root / "participants" / slot.slot_id / "intake").is_dir()


def test_single_slot_success_persists_flow_run_summary(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )

    assert report.flow_run_id.startswith("document_consistency_qc_")
    assert report.flow_run_summary_path.is_file()
    summary = load_json(report.flow_run_summary_path)
    validate_flow_run_summary(summary)

    assert summary["flow_id"] == "document_consistency_qc"
    assert summary["flow_run_id"] == report.flow_run_id
    assert summary["capability_id"] == "internal_dsur"
    assert summary["status"] == "success"
    assert len(summary["slots"]) == 1

    slot = summary["slots"][0]
    assert slot["slot_id"] == "source"
    assert slot["status"] == "success"
    assert slot["extract_config_id"] == "docx"
    assert slot["original_file_name"]
    assert "intake_run_id" not in slot
    assert slot["extract_run_id"].startswith("extract_")
    assert slot["file_hash"]
    assert slot["doc_id"]

    flow_slot = report.result.slots[0]
    assert slot["original_file_name"] == flow_slot.admitted_source.original_file_name
    assert slot["extract_run_id"] == flow_slot.extract_report.result.run_id
    assert slot["doc_id"] == flow_slot.extract_report.result.document.identity.doc_id
    assert slot["doc_meta_run_id"] == "doc_meta_source"
    assert slot["doc_meta_output_dir"] == flow_slot.doc_meta_report["output_dir"]
    assert slot["doc_meta_bundle_path"] == flow_slot.doc_meta_report["doc_meta_bundle_path"]
    assert (
        slot["doc_meta_run_summary_path"]
        == flow_slot.doc_meta_report["run_summary_path"]
    )
    assert (
        report.flow_run_summary_path.parent
        / "participants/source/doc_meta/doc_meta_bundle.json"
    ).is_file()


def test_new_summary_omits_task_run_backlink(
    tmp_path: Path,
) -> None:
    flow_kwargs = _flow_kwargs(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    with patch.object(
        flow_module,
        "_run_canonical_slot_through_candidate_scope_checkpoint",
        side_effect=AssertionError("stage started during allocation"),
    ):
        prepared = flow_module.prepare_and_allocate_document_consistency_qc_flow(
            **flow_kwargs
        )
    assert not hasattr(prepared.execution, "task_run_id")
    assert prepared.execution.output_dir.is_dir()
    assert not prepared.execution.flow_run_summary_path.exists()
    with patch.object(
        flow_module,
        "begin_flow_run_execution",
        side_effect=AssertionError("second allocation"),
    ):
        report = flow_module.execute_prepared_document_consistency_qc_flow(
            prepared
        )

    summary = load_json(report.flow_run_summary_path)
    assert report.flow_run_id == prepared.execution.flow_run_id
    assert len(_stage_run_dir_names(tmp_path, "document_consistency_qc")) == 1
    assert summary["schema_version"] == "0.13.0"
    assert "task_run_id" not in summary
    loaded = load_flow_run_execution(
        project_root=tmp_path,
        flow_run_id=report.flow_run_id,
    )
    assert not hasattr(loaded, "task_run_id")


def test_legacy_summary_without_task_run_id_remains_readable(tmp_path: Path) -> None:
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    legacy_summary = load_json(report.flow_run_summary_path)
    legacy_summary["schema_version"] = "0.11.0"
    legacy_summary.pop("task_run_id", None)
    for slot in legacy_summary["slots"]:
        slot.pop("original_file_name", None)
        slot["intake_run_id"] = "request_file_intake_legacy_fixture"
    save_json(report.flow_run_summary_path, legacy_summary)

    validate_flow_run_summary(legacy_summary)
    execution = load_flow_run_execution(
        project_root=tmp_path,
        flow_run_id=report.flow_run_id,
    )
    assert not hasattr(execution, "task_run_id")


def test_historical_013_task_run_id_is_accepted_but_not_restored(tmp_path: Path) -> None:
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    summary = load_json(report.flow_run_summary_path)
    summary["task_run_id"] = "task_run_historical_owner"
    save_json(report.flow_run_summary_path, summary)

    validate_flow_run_summary(summary)
    execution = load_flow_run_execution(
        project_root=tmp_path, flow_run_id=report.flow_run_id,
    )
    assert not hasattr(execution, "task_run_id")


def test_legacy_summary_rejects_task_run_id() -> None:
    payload = {
        "artifact_type": "document_consistency_qc_flow_run_summary",
        "schema_version": "0.11.0",
        "flow_id": "document_consistency_qc",
        "flow_run_id": "document_consistency_qc_20260920T010203000000Z",
        "task_run_id": "task_run_20260920T010203000000Z_example",
        "capability_id": "internal_dsur",
        "source_language": "zh",
        "status": "failed",
        "created_at": "2026-09-20T01:02:03+00:00",
        "completed_at": "2026-09-20T01:02:04+00:00",
        "slots": [
            {
                "slot_id": "source",
                "status": "not_started",
                "extract_config_id": "docx",
                "prepare_analysis_config_id": "clinical_trial_doc",
            }
        ],
    }

    with pytest.raises(ValueError, match="unexpected root keys.*task_run_id"):
        validate_flow_run_summary(payload)


def test_multi_slot_success_shares_one_flow_run_id(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        uploads={
            "source_a": SAMPLE_DOCX,
            "source_b": SECOND_SAMPLE_DOCX,
        },
        project_root=tmp_path,
    )

    summary = load_json(report.flow_run_summary_path)
    validate_flow_run_summary(summary)
    assert summary["capability_id"] == "dsur_updated_ib"
    assert summary["status"] == "success"
    assert [slot["slot_id"] for slot in summary["slots"]] == ["source_a", "source_b"]

    extract_run_ids = {slot["extract_run_id"] for slot in summary["slots"]}
    assert len(extract_run_ids) == 2

    for slot in summary["slots"]:
        assert slot["status"] == "success"
        assert slot["extract_config_id"] == "docx"
        assert slot["original_file_name"]
        assert "intake_run_id" not in slot


def test_separate_flow_invocations_get_distinct_flow_run_ids(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    first = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    second = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )

    assert first.flow_run_id != second.flow_run_id
    first_summary = load_json(first.flow_run_summary_path)
    second_summary = load_json(second.flow_run_summary_path)
    assert first_summary["slots"][0]["file_hash"] == second_summary["slots"][0]["file_hash"]


def test_partial_failure_persists_manifest_and_reraises(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    original_extract = sequence_module.run_extract_operation
    call_count = 0

    def _extract_second_slot_fails(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("extract failed for source_b")
        return original_extract(**kwargs)

    with patch.object(sequence_module, "run_extract_operation", side_effect=_extract_second_slot_fails):
        with pytest.raises(RuntimeError, match="extract failed for source_b"):
            _run_flow(
                capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
                uploads={
                    "source_a": SAMPLE_DOCX,
                    "source_b": SECOND_SAMPLE_DOCX,
                },
                project_root=tmp_path,
            )

    flow_dirs = list((tmp_path / "runs" / "document_consistency_qc").iterdir())
    assert len(flow_dirs) == 1
    summary_path = flow_dirs[0] / FLOW_RUN_SUMMARY_FILENAME
    assert summary_path.is_file()
    summary = load_json(summary_path)
    validate_flow_run_summary(summary)
    assert summary["status"] == "partial"
    assert "task_run_id" not in summary

    source_a, source_b = summary["slots"]
    assert source_a["slot_id"] == "source_a"
    assert source_a["status"] == "success"
    assert source_a["original_file_name"]
    assert source_a["extract_run_id"]

    assert source_b["slot_id"] == "source_b"
    assert source_b["status"] == "partial"
    assert source_b["original_file_name"]
    assert source_b["file_hash"]
    assert "extract_run_id" not in source_b


def test_launch_failure_perserves_failed_slot_without_established_fields(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()

    with patch.object(
        flow_module,
        "run_document_processing_launch_extract",
        side_effect=ValueError("launch failed"),
    ):
        with pytest.raises(ValueError, match="launch failed"):
            _run_flow(
                capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
                uploads={"source": SAMPLE_DOCX},
                project_root=tmp_path,
            )

    summary_path = next(
        (tmp_path / "runs" / "document_consistency_qc").iterdir()
    ) / FLOW_RUN_SUMMARY_FILENAME
    summary = load_json(summary_path)
    validate_flow_run_summary(summary)
    assert summary["status"] == "failed"
    assert "task_run_id" not in summary
    slot = summary["slots"][0]
    assert slot["status"] == "failed"
    assert "intake_run_id" not in slot
    assert "file_hash" not in slot


def test_operation_summaries_unchanged_by_flow_provenance(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    extract_summary = load_json(slot.extract_report.result.document.run_summary_path)

    for summary in (extract_summary,):
        assert "capability_id" not in summary
        assert "slot_id" not in summary
        assert "flow_run_id" not in summary


def test_flow_run_layout_under_document_consistency_qc_stage(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )

    assert report.flow_run_summary_path == (
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / report.flow_run_id.removeprefix("document_consistency_qc_")
        / FLOW_RUN_SUMMARY_FILENAME
    )


def test_manifest_persistence_failure_does_not_hide_operation_error(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()

    with (
        patch.object(
            flow_module,
            "run_document_processing_launch_extract",
            side_effect=ValueError("launch failed"),
        ),
        patch.object(
            execution_provenance_module,
            "persist_flow_run_summary",
            side_effect=RuntimeError("manifest failed"),
        ),
    ):
        with pytest.raises(ValueError, match="launch failed"):
            _run_flow(
                capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
                uploads={"source": SAMPLE_DOCX},
                project_root=tmp_path,
            )


def test_runtime_contracts_have_no_flow_provenance_fields() -> None:
    intake_ops = (
        BACKEND_ROOT / "runtime" / "request_file_intake" / "operations.py"
    ).read_text(encoding="utf-8")
    extract_ops = (BACKEND_ROOT / "runtime" / "extract" / "operations.py").read_text(
        encoding="utf-8"
    )
    for source in (intake_ops, extract_ops):
        assert "flow_run_id" not in source
        assert "capability_id" not in source
