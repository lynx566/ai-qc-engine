"""Persisted Product Start lifecycle facts for one TaskRun."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from runtime.io import load_json

from artifacts.task_run import task_run_manifest_path

TASK_LIFECYCLE_FILENAME = "task_lifecycle.json"
TASK_LIFECYCLE_ARTIFACT_TYPE = "task_lifecycle"
TASK_LIFECYCLE_SCHEMA_VERSION = "0.1.0"
FAILURE_BOUNDARIES = frozenset({
    "source_materialization", "input_intake", "task_input_persistence",
    "flow_prepare_or_allocation", "membership_attach",
})
_ROOT_KEYS = frozenset({"artifact_type", "schema_version", "task_run_id", "events"})
_BASE_KEYS = frozenset({"event_type", "occurred_at"})
_FLOW_KEYS = frozenset({"flow_id", "flow_run_id"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")


def task_lifecycle_manifest_path(*, project_root: Path, task_run_id: str) -> Path:
    """Return the journal next to its canonical TaskRun manifest."""

    return (task_run_manifest_path(project_root=project_root, task_run_id=task_run_id)
            .parent / TASK_LIFECYCLE_FILENAME)


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} must be a non-empty trimmed string")
    return value


def _check_keys(value: Mapping[str, Any], expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{field} must have exactly {sorted(expected)!r} keys")


def validate_task_lifecycle_manifest(payload: Mapping[str, Any]) -> None:
    """Validate exact keys, identities, and legal Product Start prefixes."""

    if not isinstance(payload, Mapping):
        raise TypeError("task_lifecycle manifest must be a mapping")
    _check_keys(payload, _ROOT_KEYS, "task_lifecycle manifest")
    if payload["artifact_type"] != TASK_LIFECYCLE_ARTIFACT_TYPE:
        raise ValueError("invalid task_lifecycle artifact_type")
    if payload["schema_version"] != TASK_LIFECYCLE_SCHEMA_VERSION:
        raise ValueError("unsupported task_lifecycle schema_version")
    task_run_id = _nonempty(payload["task_run_id"], "task_run_id")
    task_run_manifest_path(project_root=Path("."), task_run_id=task_run_id)
    events = payload["events"]
    if not isinstance(events, list) or not events:
        raise ValueError("events must be a non-empty array")

    stage = 0
    allocated: tuple[str, str] | None = None
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise TypeError(f"events[{index}] must be a mapping")
        event_type = event.get("event_type")
        if event_type == "input_admission_started" and stage == 0:
            expected = _BASE_KEYS
            stage = 1
        elif event_type == "flow_allocation_started" and stage == 1:
            expected = _BASE_KEYS
            stage = 2
        elif event_type == "flow_allocated" and stage == 2:
            expected = _BASE_KEYS | _FLOW_KEYS
            stage = 3
        elif event_type == "flow_execution_requested" and stage == 3:
            expected = _BASE_KEYS | _FLOW_KEYS
            stage = 4
        elif event_type == "product_start_failed" and stage in (1, 2, 3):
            expected = _BASE_KEYS | {"failure_boundary", "message"}
            if set(event) == expected | _FLOW_KEYS:
                expected |= _FLOW_KEYS
            stage = 4
        else:
            raise ValueError(f"invalid Product Start transition at events[{index}]")
        _check_keys(event, expected, f"events[{index}]")
        stamp = _nonempty(event["occurred_at"], "occurred_at")
        try:
            parsed_stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("occurred_at must be an ISO timestamp") from exc
        if parsed_stamp.tzinfo is None or parsed_stamp.utcoffset().total_seconds() != 0:
            raise ValueError("occurred_at must be a UTC timestamp")
        if event_type in ("flow_allocated", "flow_execution_requested") or _FLOW_KEYS <= set(event):
            flow_id = _nonempty(event["flow_id"], "flow_id")
            flow_run_id = _nonempty(event["flow_run_id"], "flow_run_id")
            if not _SAFE_ID.fullmatch(flow_id):
                raise ValueError("flow_id must be URL-safe")
            if not _SAFE_ID.fullmatch(flow_run_id):
                raise ValueError("flow_run_id must be URL-safe")
            if event_type == "flow_allocated":
                allocated = (flow_id, flow_run_id)
            elif allocated != (flow_id, flow_run_id):
                raise ValueError("Flow identity does not match flow_allocated")
        if event_type == "product_start_failed":
            boundary = event["failure_boundary"]
            if boundary not in FAILURE_BOUNDARIES:
                raise ValueError("invalid failure_boundary")
            _nonempty(event["message"], "message")
            if index == 1 and boundary not in {
                "source_materialization", "input_intake", "task_input_persistence"
            }:
                raise ValueError("failure_boundary does not match input admission")
            if index > 1 and boundary not in {
                "flow_prepare_or_allocation", "membership_attach"
            }:
                raise ValueError("failure_boundary does not match flow allocation")
            if boundary == "membership_attach" and allocated is None:
                raise ValueError("membership_attach requires flow_allocated")


def build_task_lifecycle_manifest(
    *, task_run_id: str, events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate the complete journal after one appended event."""

    manifest = {
        "artifact_type": TASK_LIFECYCLE_ARTIFACT_TYPE,
        "schema_version": TASK_LIFECYCLE_SCHEMA_VERSION,
        "task_run_id": task_run_id,
        "events": [dict(event) for event in events],
    }
    validate_task_lifecycle_manifest(manifest)
    return manifest


def load_task_lifecycle_manifest(
    *, project_root: Path, task_run_id: str,
) -> dict[str, Any] | None:
    """Load an optional historical journal, rejecting present invalid data."""

    path = task_lifecycle_manifest_path(project_root=project_root, task_run_id=task_run_id)
    if not path.exists():
        return None
    manifest = load_json(path)
    validate_task_lifecycle_manifest(manifest)
    if manifest["task_run_id"] != task_run_id:
        raise ValueError("task_lifecycle.task_run_id does not match requested TaskRun")
    return dict(manifest)


__all__ = [
    "FAILURE_BOUNDARIES",
    "TASK_LIFECYCLE_FILENAME",
    "build_task_lifecycle_manifest",
    "load_task_lifecycle_manifest",
    "task_lifecycle_manifest_path",
    "validate_task_lifecycle_manifest",
]
