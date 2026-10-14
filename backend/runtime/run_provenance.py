"""Git and upstream-run metadata for pipeline run_summary.json files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

GIT_DIRTY_CHECKED_AT_BEFORE_RUN = "before_run"
GIT_DIRTY_CHECKED_AT_SUMMARY = "at_summary"


def find_git_root(start: Path) -> Path | None:
    resolved = start.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def get_git_provenance(*, root: Path) -> dict[str, str | bool | None]:
    git_root = find_git_root(root)
    if git_root is None:
        return {"git_commit": None, "git_dirty": None}

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {"git_commit": None, "git_dirty": None}

    return {
        "git_commit": commit or None,
        "git_dirty": bool(status.strip()),
    }


def snapshot_git_provenance_before_run(*, root: Path) -> dict[str, str | bool | None]:
    """
    Capture git state once at runner startup, before any run artifacts are written.

    Callers should pass the returned dict through to ``finalize_run_summary`` so
    ``git_dirty`` reflects the pre-run working tree (not newly created ``runs/``).
    """
    provenance = get_git_provenance(root=root)
    provenance["git_dirty_checked_at"] = GIT_DIRTY_CHECKED_AT_BEFORE_RUN
    return provenance


def load_upstream_run_summary(artifact_path: Path) -> dict[str, Any] | None:
    """Read ``run_summary.json`` from the directory containing an input artifact."""
    return load_optional_upstream_run_summary(artifact_path)


def load_optional_upstream_run_summary(artifact_path: Path) -> dict[str, Any] | None:
    """Optional sibling ``run_summary.json`` for operational lineage only.

    Used to populate ``upstream_run_id`` / ``upstream_stage`` on output summaries.
    Returns ``None`` when the sibling summary is missing or unreadable.

    Callers must not use this for semantic inputs (doc identity, zone, source content,
    or business context). Formal artifact lineage remains on the primary input artifact.
    """
    summary_path = artifact_path.resolve().parent / "run_summary.json"
    if not summary_path.is_file():
        return None
    try:
        with summary_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def upstream_provenance(
    upstream_summary: dict[str, Any] | None,
) -> dict[str, str | None]:
    if upstream_summary is None:
        return {"upstream_run_id": None, "upstream_stage": None}
    run_id = upstream_summary.get("run_id")
    stage = upstream_summary.get("stage")
    return {
        "upstream_run_id": str(run_id) if run_id is not None else None,
        "upstream_stage": str(stage) if stage is not None else None,
    }


def finalize_run_summary(
    *,
    stage: str,
    run_id: str,
    pipeline: list[str],
    doc_id: str | None,
    file_name: str | None = None,
    inputs: dict[str, str],
    outputs: dict[str, str],
    git_root: Path,
    upstream_summary: dict[str, Any] | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """
    Assemble a run_summary with stable field order and provenance fields.

    Provenance source of truth lives in run_summary.json (inputs + upstream_*),
    not run directory names or timestamps.
    """
    git = git_provenance if git_provenance is not None else get_git_provenance(
        root=git_root
    )
    if git_provenance is None:
        git = {**git, "git_dirty_checked_at": GIT_DIRTY_CHECKED_AT_SUMMARY}
    prefix: dict[str, Any] = {
        "stage": stage,
        "run_id": run_id,
        "pipeline": pipeline,
        "doc_id": doc_id,
    }
    if file_name is not None:
        prefix["file_name"] = file_name
    summary: dict[str, Any] = {
        **prefix,
        "git_commit": git["git_commit"],
        "git_dirty": git["git_dirty"],
        "git_dirty_checked_at": git.get(
            "git_dirty_checked_at", GIT_DIRTY_CHECKED_AT_SUMMARY
        ),
        **upstream_provenance(upstream_summary),
        "inputs": inputs,
        "outputs": outputs,
    }
    summary.update(extra)
    return summary
