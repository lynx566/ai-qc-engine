"""Contract tests for the Product-owned Task lifecycle journal."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.task_lifecycle import (
    build_task_lifecycle_manifest,
    task_lifecycle_manifest_path,
    validate_task_lifecycle_manifest,
)

T = "task_run_20260922_010203_123456Z"
F = "document_consistency_qc_20260922_010204_123456Z"
FLOW = "document_consistency_qc"
STAMP = "2026-09-22T01:02:03Z"


def _event(event_type: str, **extra: str) -> dict[str, str]:
    return {"event_type": event_type, "occurred_at": STAMP, **extra}


def _manifest(events: list[dict[str, str]]) -> dict[str, object]:
    return {
        "artifact_type": "task_lifecycle",
        "schema_version": "0.1.0",
        "task_run_id": T,
        "events": events,
    }


def test_valid_success_and_attach_failure_histories() -> None:
    prefix = [
        _event("input_admission_started"),
        _event("flow_allocation_started"),
        _event("flow_allocated", flow_id=FLOW, flow_run_id=F),
    ]
    validate_task_lifecycle_manifest(_manifest([
        *prefix,
        _event("flow_execution_requested", flow_id=FLOW, flow_run_id=F),
    ]))
    validate_task_lifecycle_manifest(_manifest([
        *prefix,
        _event("product_start_failed", failure_boundary="membership_attach",
               message="Unable to attach Flow", flow_id=FLOW, flow_run_id=F),
    ]))


@pytest.mark.parametrize("events", [
    [],
    [_event("flow_allocation_started")],
    [_event("input_admission_started"), _event("input_admission_started")],
    [_event("input_admission_started"), _event("flow_allocation_started"),
     _event("flow_execution_requested", flow_id=FLOW, flow_run_id=F)],
    [_event("input_admission_started"),
     _event("product_start_failed", failure_boundary="input_intake", message="failed"),
     _event("flow_allocation_started")],
    [_event("input_admission_started", status="running")],
])
def test_rejects_invalid_event_history(events: list[dict[str, str]]) -> None:
    with pytest.raises((TypeError, ValueError)):
        validate_task_lifecycle_manifest(_manifest(events))


def test_rejects_wrong_identity_and_unknown_boundary() -> None:
    bad = _manifest([_event("input_admission_started")])
    bad["task_run_id"] = "../escape"
    with pytest.raises(ValueError):
        validate_task_lifecycle_manifest(bad)


def test_rejects_unsafe_flow_identity() -> None:
    bad = _manifest([
        _event("input_admission_started"),
        _event("flow_allocation_started"),
        _event("flow_allocated", flow_id=FLOW, flow_run_id="../other_flow"),
    ])
    with pytest.raises(ValueError, match="flow_run_id"):
        validate_task_lifecycle_manifest(bad)
    bad = _manifest([_event("input_admission_started"),
                     _event("product_start_failed", failure_boundary="flow_failed",
                            message="failed")])
    with pytest.raises(ValueError):
        validate_task_lifecycle_manifest(bad)


def test_path_and_builder_use_canonical_identity(tmp_path: Path) -> None:
    assert task_lifecycle_manifest_path(project_root=tmp_path, task_run_id=T) == (
        tmp_path / "runs" / "task_runs" / T / "task_lifecycle.json"
    )
    assert build_task_lifecycle_manifest(task_run_id=T,
                                         events=[_event("input_admission_started")]) == (
        _manifest([_event("input_admission_started")])
    )
