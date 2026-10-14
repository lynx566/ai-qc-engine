"""Append one durable Product Start transition to a Task-owned journal."""

from __future__ import annotations

from pathlib import Path

from artifacts.task_lifecycle import (
    build_task_lifecycle_manifest,
    load_task_lifecycle_manifest,
    task_lifecycle_manifest_path,
)
from artifacts.task_run import load_task_run_manifest
from runtime.io import save_json_atomic
from runtime.run_layout import utc_now_iso


def append_task_lifecycle_event(
    *, project_root: Path, task_run_id: str, event_type: str,
    flow_id: str | None = None, flow_run_id: str | None = None,
    failure_boundary: str | None = None, message: str | None = None,
) -> Path:
    """Validate the proposed full history, persist atomically, and verify it."""

    task = load_task_run_manifest(project_root=project_root, task_run_id=task_run_id)
    current = load_task_lifecycle_manifest(project_root=project_root, task_run_id=task_run_id)
    events = [] if current is None else list(current["events"])
    event = {"event_type": event_type, "occurred_at": utc_now_iso()}
    if flow_id is not None:
        event["flow_id"] = flow_id
    if flow_run_id is not None:
        event["flow_run_id"] = flow_run_id
    if failure_boundary is not None:
        event["failure_boundary"] = failure_boundary
    if message is not None:
        event["message"] = message
    manifest = build_task_lifecycle_manifest(task_run_id=task_run_id,
                                             events=[*events, event])
    if event_type == "flow_execution_requested":
        ref = {"flow_id": flow_id, "flow_run_id": flow_run_id}
        if ref not in task["flow_runs"]:
            raise ValueError("requested Flow is not attached to TaskRun")
    path = task_lifecycle_manifest_path(project_root=project_root, task_run_id=task_run_id)
    save_json_atomic(path, manifest)
    if load_task_lifecycle_manifest(project_root=project_root,
                                    task_run_id=task_run_id) != manifest:
        raise RuntimeError("persisted task_lifecycle does not match appended history")
    return path


__all__ = ["append_task_lifecycle_event"]
