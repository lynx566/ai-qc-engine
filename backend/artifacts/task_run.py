"""Neutral persisted TaskRun artifact contract."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.io import load_json, save_json_atomic

TASK_RUN_FILENAME = "task_run.json"
TASK_RUN_ARTIFACT_TYPE = "task_run"
TASK_RUN_SCHEMA_VERSION = "0.3.0"
TASK_RUN_SCHEMA_VERSION_0_2_0 = "0.2.0"
_SUPPORTED_TASK_RUN_SCHEMA_VERSIONS = frozenset(
    {TASK_RUN_SCHEMA_VERSION_0_2_0, TASK_RUN_SCHEMA_VERSION}
)

_TASK_RUN_ID_PATTERN = re.compile(r"^task_run_[A-Za-z0-9][A-Za-z0-9_]*$")
_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "task_run_id",
        "task_id",
        "created_at",
        "updated_at",
        "flow_runs",
    }
)
_FLOW_EXECUTION_REF_KEYS = frozenset({"flow_id", "flow_run_id"})


@dataclass(frozen=True, slots=True)
class FlowExecutionRef:
    """Minimal identity reference to one child FlowRun."""

    flow_id: str
    flow_run_id: str

    def to_record(self) -> dict[str, str]:
        return _validate_flow_execution_ref(
            {
                "flow_id": self.flow_id,
                "flow_run_id": self.flow_run_id,
            },
            label="flow_run",
        )


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_task_run_id(value: Any) -> str:
    task_run_id = _require_str(value, field="task_run_id")
    if not _TASK_RUN_ID_PATTERN.fullmatch(task_run_id):
        raise ValueError("task_run_id must be a URL-safe task_run_ identifier")
    return task_run_id


def _validate_flow_execution_ref(value: Any, *, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    extra = set(value) - _FLOW_EXECUTION_REF_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _FLOW_EXECUTION_REF_KEYS - set(value)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    return {
        "flow_id": _require_str(value["flow_id"], field=f"{label}.flow_id"),
        "flow_run_id": _require_str(
            value["flow_run_id"],
            field=f"{label}.flow_run_id",
        ),
    }


def validate_task_run_manifest(payload: Mapping[str, Any]) -> None:
    """Validate one TaskRun artifact without resolving child artifacts."""

    if not isinstance(payload, Mapping):
        raise TypeError("task_run manifest must be a mapping")
    extra = set(payload) - _ROOT_KEYS
    if extra:
        raise ValueError(f"task_run manifest has unexpected keys: {sorted(extra)!r}")
    missing = _ROOT_KEYS - set(payload)
    if missing:
        raise ValueError(
            f"task_run manifest is missing required keys: {sorted(missing)!r}"
        )

    artifact_type = _require_str(payload["artifact_type"], field="artifact_type")
    if artifact_type != TASK_RUN_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {TASK_RUN_ARTIFACT_TYPE!r}, got {artifact_type!r}"
        )
    schema_version = _require_str(payload["schema_version"], field="schema_version")
    if schema_version not in _SUPPORTED_TASK_RUN_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(_SUPPORTED_TASK_RUN_SCHEMA_VERSIONS))
        raise ValueError(
            f"schema_version must be one of {{{supported}}}, got {schema_version!r}"
        )

    _require_task_run_id(payload["task_run_id"])
    _require_str(payload["task_id"], field="task_id")
    _require_str(payload["created_at"], field="created_at")
    _require_str(payload["updated_at"], field="updated_at")

    flow_runs = payload["flow_runs"]
    if not isinstance(flow_runs, list):
        raise TypeError("flow_runs must be an array")
    if not flow_runs and schema_version == TASK_RUN_SCHEMA_VERSION_0_2_0:
        raise ValueError("flow_runs must contain at least one entry")
    normalized = [
        _validate_flow_execution_ref(value, label=f"flow_runs[{index}]")
        for index, value in enumerate(flow_runs)
    ]
    flow_run_ids = [value["flow_run_id"] for value in normalized]
    if len(set(flow_run_ids)) != len(flow_run_ids):
        raise ValueError("flow_runs must not contain duplicate flow_run_id values")


def build_task_run_manifest(
    *,
    task_run_id: str,
    task_id: str,
    created_at: str,
    updated_at: str,
    flow_runs: Sequence[FlowExecutionRef],
) -> dict[str, Any]:
    """Build and validate one TaskRun artifact."""

    manifest: dict[str, Any] = {
        "artifact_type": TASK_RUN_ARTIFACT_TYPE,
        "schema_version": TASK_RUN_SCHEMA_VERSION,
        "task_run_id": _require_task_run_id(task_run_id),
        "task_id": _require_str(task_id, field="task_id"),
        "created_at": _require_str(created_at, field="created_at"),
        "updated_at": _require_str(updated_at, field="updated_at"),
        "flow_runs": [flow_run.to_record() for flow_run in flow_runs],
    }
    validate_task_run_manifest(manifest)
    return manifest


def task_run_manifest_path(*, project_root: Path, task_run_id: str) -> Path:
    """Return the canonical TaskRun artifact path."""

    normalized_id = _require_task_run_id(task_run_id)
    return project_root / "runs" / "task_runs" / normalized_id / TASK_RUN_FILENAME


def save_task_run_manifest(
    *,
    project_root: Path,
    manifest: Mapping[str, Any],
) -> Path:
    """Persist and verify one canonical TaskRun artifact."""

    validate_task_run_manifest(manifest)
    path = task_run_manifest_path(
        project_root=project_root,
        task_run_id=str(manifest["task_run_id"]),
    )
    save_json_atomic(path, dict(manifest))
    reloaded = load_json(path)
    validate_task_run_manifest(reloaded)
    if reloaded != dict(manifest):
        raise RuntimeError("persisted task_run does not match input manifest")
    return path


def load_task_run_manifest(
    *,
    project_root: Path,
    task_run_id: str,
) -> dict[str, Any]:
    """Load and validate one canonical TaskRun artifact."""

    normalized_id = _require_task_run_id(task_run_id)
    path = task_run_manifest_path(
        project_root=project_root,
        task_run_id=normalized_id,
    )
    manifest = load_json(path)
    validate_task_run_manifest(manifest)
    if manifest["task_run_id"] != normalized_id:
        raise ValueError("task_run.task_run_id does not match requested task_run_id")
    return dict(manifest)


__all__ = [
    "TASK_RUN_ARTIFACT_TYPE",
    "TASK_RUN_FILENAME",
    "TASK_RUN_SCHEMA_VERSION",
    "TASK_RUN_SCHEMA_VERSION_0_2_0",
    "FlowExecutionRef",
    "build_task_run_manifest",
    "load_task_run_manifest",
    "save_task_run_manifest",
    "task_run_manifest_path",
    "validate_task_run_manifest",
]
