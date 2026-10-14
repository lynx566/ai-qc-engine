"""Frozen public Product TaskRun state from persisted ownership facts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.task_lifecycle import append_task_lifecycle_event
from application.task_run import attach_flow_run, create_task_run
from runtime.io import save_json
from task.clinical_trial_doc_qc.task_run_read import (
    load_task_run_page_context,
    task_run_page_context_to_mapping,
)
from tests.test_result_readiness import _fixture

T = "task_run_20260922_010203_123456Z"
F = "document_consistency_qc_test_projection"
FLOW = "document_consistency_qc"


def _state(tmp_path: Path) -> dict[str, object]:
    return task_run_page_context_to_mapping(load_task_run_page_context(
        project_root=tmp_path, task_run_id=T,
    ))["state"]


def test_new_task_has_frozen_unknown_state(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    assert _state(tmp_path) == {
        "input_ready": False, "product_phase": "unknown", "product_failure": None,
        "allocated_flow": None, "flow_outcome": "unknown",
        "requires_user_action": None, "result_available": False,
    }


def test_allocated_flow_does_not_become_membership(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="input_admission_started")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_allocation_started")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_allocated", flow_id=FLOW, flow_run_id=F)
    body = task_run_page_context_to_mapping(load_task_run_page_context(
        project_root=tmp_path, task_run_id=T,
    ))
    assert body["flow_runs"] == []
    assert body["state"]["allocated_flow"] == {"flow_id": FLOW, "flow_run_id": F}
    assert body["state"]["product_phase"] == "flow_allocated"
    assert body["state"]["flow_outcome"] == "unknown"


def test_requested_flow_without_summary_keeps_unknown_and_null(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    for event_type in ("input_admission_started", "flow_allocation_started"):
        append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                    event_type=event_type)
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_allocated", flow_id=FLOW, flow_run_id=F)
    attach_flow_run(project_root=tmp_path, task_run_id=T, flow_id=FLOW, flow_run_id=F)
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_execution_requested",
                                flow_id=FLOW, flow_run_id=F)
    assert _state(tmp_path)["product_phase"] == "flow_execution_requested"
    assert _state(tmp_path)["flow_outcome"] == "unknown"
    assert _state(tmp_path)["requires_user_action"] is None
    assert _state(tmp_path)["result_available"] is False


def test_present_bad_journal_is_read_error(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    save_json(tmp_path / "runs" / "task_runs" / T / "task_lifecycle.json",
              {"broken": True})
    with pytest.raises(ValueError):
        _state(tmp_path)


def test_historical_membership_proves_allocation_only(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    attach_flow_run(project_root=tmp_path, task_run_id=T, flow_id=FLOW, flow_run_id=F)
    state = _state(tmp_path)
    assert state["product_phase"] == "flow_allocated"
    assert state["allocated_flow"] is None
    assert state["flow_outcome"] == "unknown"
    assert state["requires_user_action"] is None


def test_product_failure_keeps_last_entered_phase(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="input_admission_started")
    append_task_lifecycle_event(
        project_root=tmp_path, task_run_id=T, event_type="product_start_failed",
        failure_boundary="input_intake", message="Input intake failed",
    )
    state = _state(tmp_path)
    assert state["product_phase"] == "input_admission"
    assert state["product_failure"] == {
        "boundary": "input_intake", "message": "Input intake failed",
    }


def test_persisted_task_input_is_ready_even_if_readback_failed(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    save_json(tmp_path / "runs" / "task_runs" / T / "task_input.json", {
        "artifact_type": "task_input", "schema_version": "0.1.0",
        "task_run_id": T,
        "inputs": [{
            "task_slot_id": "source",
            "file_hash": "sha256:10910f206d37eb8e78e2cd5becd0e23747dc216bb446014dcc08d1fc61579cb4",
            "original_file_name": "source.docx",
            "source_ref": f"runs/task_runs/{T}/inputs/source/source/source.docx",
        }],
    })
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="input_admission_started")
    append_task_lifecycle_event(
        project_root=tmp_path, task_run_id=T, event_type="product_start_failed",
        failure_boundary="task_input_persistence",
        message="Task input persistence failed",
    )
    state = _state(tmp_path)
    assert state["input_ready"] is True
    assert state["product_failure"]["boundary"] == "task_input_persistence"


def test_completed_dsur_updated_ib_flow_loads_with_result_unavailable(
    tmp_path: Path,
) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    summary["capability_id"] = "dsur_updated_ib"
    save_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json",
        summary,
    )
    create_task_run(
        project_root=tmp_path, task_run_id=T, task_id="dsur_updated_ib_qc"
    )
    attach_flow_run(
        project_root=tmp_path,
        task_run_id=T,
        flow_id=FLOW,
        flow_run_id=flow_run_id,
    )
    state = _state(tmp_path)
    assert state["flow_outcome"] == "success"
    assert state["requires_user_action"] is False
    assert state["result_available"] is False


def test_historical_terminal_flow_uses_summary_and_result_probe(tmp_path: Path) -> None:
    flow_run_id, _ = _fixture(tmp_path)
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    attach_flow_run(project_root=tmp_path, task_run_id=T,
                    flow_id=FLOW, flow_run_id=flow_run_id)
    state = _state(tmp_path)
    assert state["product_phase"] == "flow_allocated"
    assert state["flow_outcome"] == "success"
    assert state["requires_user_action"] is False
    assert state["result_available"] is True


def test_historical_task_backlink_does_not_override_membership(tmp_path: Path) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    summary["schema_version"] = "0.12.0"
    summary["task_run_id"] = "task_run_other"
    save_json(tmp_path / "runs" / "document_consistency_qc" /
              "test_internal_result" / "flow_run_summary.json", summary)
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    attach_flow_run(project_root=tmp_path, task_run_id=T,
                    flow_id=FLOW, flow_run_id=flow_run_id)
    state = _state(tmp_path)
    assert state["flow_outcome"] == "success"
    assert state["result_available"] is True
