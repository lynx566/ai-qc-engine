"""Application lifecycle for persisted TaskRun identity and membership."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from artifacts.task_run import (
    FlowExecutionRef,
    build_task_run_manifest,
    load_task_run_manifest,
    save_task_run_manifest,
    task_run_manifest_path,
)
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import utc_now_iso


def allocate_task_run_id() -> str:
    """Allocate an independent, URL-safe TaskRun identity without persistence."""

    timestamp = format_run_timestamp(utc_run_stamp())
    return f"task_run_{timestamp}_{uuid4().hex}"


def create_task_run(
    *,
    project_root: Path,
    task_run_id: str,
    task_id: str,
) -> Path:
    """Persist a new TaskRun before any child FlowRun membership exists."""

    path = task_run_manifest_path(project_root=project_root, task_run_id=task_run_id)
    if path.exists():
        raise FileExistsError(f"task_run already exists: {path.as_posix()}")
    stamp = utc_now_iso()
    manifest = build_task_run_manifest(
        task_run_id=task_run_id,
        task_id=task_id,
        created_at=stamp,
        updated_at=stamp,
        flow_runs=(),
    )
    return save_task_run_manifest(project_root=project_root, manifest=manifest)


def create_task_run_for_flow(
    *,
    project_root: Path,
    task_run_id: str,
    task_id: str,
    flow_id: str,
    flow_run_id: str,
) -> Path:
    """Persist a new TaskRun with one child membership (compatibility wrapper)."""

    create_task_run(
        project_root=project_root,
        task_run_id=task_run_id,
        task_id=task_id,
    )
    return attach_flow_run(
        project_root=project_root,
        task_run_id=task_run_id,
        flow_id=flow_id,
        flow_run_id=flow_run_id,
    )


def attach_flow_run(
    *,
    project_root: Path,
    task_run_id: str,
    flow_id: str,
    flow_run_id: str,
) -> Path:
    """Append one child execution while preserving TaskRun ownership metadata."""

    current = load_task_run_manifest(
        project_root=project_root,
        task_run_id=task_run_id,
    )
    flow_runs = tuple(
        FlowExecutionRef(
            flow_id=str(item["flow_id"]),
            flow_run_id=str(item["flow_run_id"]),
        )
        for item in current["flow_runs"]
    ) + (FlowExecutionRef(flow_id=flow_id, flow_run_id=flow_run_id),)
    updated = build_task_run_manifest(
        task_run_id=str(current["task_run_id"]),
        task_id=str(current["task_id"]),
        created_at=str(current["created_at"]),
        updated_at=utc_now_iso(),
        flow_runs=flow_runs,
    )
    return save_task_run_manifest(project_root=project_root, manifest=updated)


def load_task_run(
    *,
    project_root: Path,
    task_run_id: str,
) -> dict[str, object]:
    """Load one validated TaskRun for application consumers."""

    return load_task_run_manifest(
        project_root=project_root,
        task_run_id=task_run_id,
    )


__all__ = [
    "allocate_task_run_id",
    "attach_flow_run",
    "create_task_run",
    "create_task_run_for_flow",
    "load_task_run",
]
