"""Persistence tests for one Task-owned lifecycle history."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.task_lifecycle import append_task_lifecycle_event
from application.task_run import attach_flow_run, create_task_run
from artifacts.task_lifecycle import load_task_lifecycle_manifest

T = "task_run_20260922_010203_123456Z"
F = "document_consistency_qc_20260922_010204_123456Z"
FLOW = "document_consistency_qc"


def test_first_append_and_terminal_handoff(tmp_path: Path) -> None:
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="input_admission_started")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_allocation_started")
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_allocated", flow_id=FLOW, flow_run_id=F)
    with pytest.raises(ValueError, match="attached"):
        append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                    event_type="flow_execution_requested",
                                    flow_id=FLOW, flow_run_id=F)
    attach_flow_run(project_root=tmp_path, task_run_id=T, flow_id=FLOW, flow_run_id=F)
    append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                event_type="flow_execution_requested",
                                flow_id=FLOW, flow_run_id=F)
    assert [e["event_type"] for e in load_task_lifecycle_manifest(
        project_root=tmp_path, task_run_id=T)["events"]] == [
            "input_admission_started", "flow_allocation_started", "flow_allocated",
            "flow_execution_requested",
        ]
    with pytest.raises(ValueError):
        append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                    event_type="input_admission_started")


def test_append_requires_task_and_preserves_bytes_on_failed_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(FileNotFoundError):
        append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                    event_type="input_admission_started")
    create_task_run(project_root=tmp_path, task_run_id=T, task_id="internal_dsur_qc")
    path = append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                       event_type="input_admission_started")
    before = path.read_bytes()

    def fail_save(path: Path, data: object) -> None:
        raise OSError("write failed")

    monkeypatch.setattr("application.task_lifecycle.save_json_atomic", fail_save)
    with pytest.raises(OSError, match="write failed"):
        append_task_lifecycle_event(project_root=tmp_path, task_run_id=T,
                                    event_type="flow_allocation_started")
    assert path.read_bytes() == before
