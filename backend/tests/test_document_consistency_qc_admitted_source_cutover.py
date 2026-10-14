"""Slice 3 regressions: admitted-source boundary and exactly-once Intake."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from artifacts.task_input import TASK_INPUT_FILENAME
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from scripts import run_consistency_qc
from task.clinical_trial_doc_qc import (
    INTERNAL_DSUR_QC_TASK_ID,
    plan_installed_product_task_start,
    start_installed_product_task,
)
from task.clinical_trial_doc_qc.task_input import load_task_input_manifest
from tests.test_document_consistency_qc_flow import _run_flow

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)


def test_flow_does_not_invoke_request_file_intake(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    with patch(
        "execution_flow.document_processing_sequence.run_request_file_intake_operation",
        side_effect=AssertionError("flow must not run Intake"),
    ):
        _run_flow(
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )


def test_execution_request_rejects_raw_path(tmp_path: Path) -> None:
    source = tmp_path / "raw.docx"
    source.write_bytes(b"x")
    with pytest.raises(TypeError, match="DocumentIntakeSourceBinding"):
        DocumentConsistencyQcExecutionRequest(
            capability_id="internal_dsur",
            project_root=tmp_path,
            participant_inputs={"source": source},
            participant_privacy_paths={"source": None},
            source_language="zh",
        )


def test_product_start_persists_task_input_before_dcqc(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    events: list[str] = []

    def _track_execute(*, request, **kwargs):
        events.append("dcqc")
        task_input_path = (
            tmp_path / "runs" / "task_runs" / planned.task_run_id / TASK_INPUT_FILENAME
        )
        assert task_input_path.is_file()
        raise RuntimeError("stop")

    with (
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_track_execute,
        ),
        pytest.raises(RuntimeError, match="stop"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    assert events == ["dcqc"]
    task_input = load_task_input_manifest(
        project_root=tmp_path,
        task_run_id=planned.task_run_id,
    )
    source_ref = task_input["inputs"][0]["source_ref"]
    assert "runs/task_runs/" in source_ref
    assert "/inputs/source/" in source_ref
    assert "upload_staging" not in source_ref


def test_product_admission_calls_intake_once_per_slot(tmp_path: Path) -> None:
    from task.clinical_trial_doc_qc import DSUR_UPDATED_IB_QC_TASK_ID

    assert SAMPLE_DOCX.is_file()
    second = tmp_path / "second.docx"
    second.write_bytes(b"second")
    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        upload_slot_ids={"source_a", "source_b"},
    )
    intake_calls = 0
    original = __import__(
        "runtime.request_file_intake",
        fromlist=["run_request_file_intake_operation"],
    ).run_request_file_intake_operation

    def _count_intake(**kwargs):
        nonlocal intake_calls
        intake_calls += 1
        return original(**kwargs)

    with (
        patch(
            "task.clinical_trial_doc_qc.product_source_admission.run_request_file_intake_operation",
            side_effect=_count_intake,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=RuntimeError("stop"),
        ),
        pytest.raises(RuntimeError, match="stop"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source_a": SAMPLE_DOCX, "source_b": second},
            project_root=tmp_path,
        )

    assert intake_calls == 2


def test_product_single_slot_calls_intake_once(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    intake_calls = 0
    original = __import__(
        "runtime.request_file_intake",
        fromlist=["run_request_file_intake_operation"],
    ).run_request_file_intake_operation

    def _count_intake(**kwargs):
        nonlocal intake_calls
        intake_calls += 1
        return original(**kwargs)

    with (
        patch(
            "task.clinical_trial_doc_qc.product_source_admission.run_request_file_intake_operation",
            side_effect=_count_intake,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=RuntimeError("stop"),
        ),
        pytest.raises(RuntimeError, match="stop"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": SAMPLE_DOCX},
            project_root=tmp_path,
        )

    assert intake_calls == 1


def test_standalone_cli_calls_intake_once_per_participant(tmp_path: Path) -> None:
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    intake_calls = 0
    original = run_consistency_qc.run_request_file_intake_operation

    def _count_intake(**kwargs):
        nonlocal intake_calls
        intake_calls += 1
        return original(**kwargs)

    with (
        patch.object(
            run_consistency_qc,
            "run_request_file_intake_operation",
            side_effect=_count_intake,
        ),
        patch.object(
            run_consistency_qc,
            "prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=RuntimeError("stop after request"),
        ),
        pytest.raises(RuntimeError, match="stop after request"),
    ):
        run_consistency_qc.main(
            [
                "--capability",
                "dsur_updated_ib",
                "--source-a",
                str(first),
                "--source-b",
                str(second),
                "--project-root",
                str(tmp_path),
            ]
        )

    assert intake_calls == 2
