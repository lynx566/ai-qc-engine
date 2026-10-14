"""Neutral persisted TaskInput artifact contract."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from core.document.doc_identity import validate_file_hash_format

TASK_INPUT_FILENAME = "task_input.json"
TASK_INPUT_ARTIFACT_TYPE = "task_input"
TASK_INPUT_SCHEMA_VERSION = "0.1.0"

_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "task_run_id",
        "inputs",
    }
)
_ENTRY_KEYS = frozenset(
    {
        "task_slot_id",
        "file_hash",
        "original_file_name",
        "source_ref",
    }
)
_TASK_SLOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_TASK_RUN_ID_PATTERN = re.compile(r"^task_run_[A-Za-z0-9][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class TaskInputEntry:
    """One canonical Product input slot admission fact."""

    task_slot_id: str
    file_hash: str
    original_file_name: str
    source_ref: str

    def to_record(self) -> dict[str, str]:
        return _validate_task_input_entry(
            {
                "task_slot_id": self.task_slot_id,
                "file_hash": self.file_hash,
                "original_file_name": self.original_file_name,
                "source_ref": self.source_ref,
            },
            label="inputs entry",
        )


def _require_task_run_id(value: Any) -> str:
    task_run_id = _require_str(value, field="task_run_id")
    if not _TASK_RUN_ID_PATTERN.fullmatch(task_run_id):
        raise ValueError("task_run_id must be a URL-safe task_run_ identifier")
    return task_run_id


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_original_file_name(value: Any, *, field: str) -> str:
    name = _require_str(value, field=field)
    if name != PurePosixPath(name).name or "\\" in name or "/" in name:
        raise ValueError(f"{field} must be a safe basename")
    return name


def validate_task_input_source_ref(value: Any, *, field: str = "source_ref") -> str:
    """Validate a project-relative POSIX source reference."""

    ref = _require_str(value, field=field)
    if "\\" in ref:
        raise ValueError(f"{field} must use forward-slash project-relative paths")
    if ref.startswith("/"):
        raise ValueError(f"{field} must not be absolute")
    if len(ref) >= 2 and ref[1] == ":":
        raise ValueError(f"{field} must not be drive-qualified")
    path = PurePosixPath(ref)
    if path.is_absolute():
        raise ValueError(f"{field} must not be absolute")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"{field} must not contain parent traversal")
    if not path.parts:
        raise ValueError(f"{field} must not be empty")
    return path.as_posix()


def validate_task_slot_id(value: Any, *, field: str = "task_slot_id") -> str:
    task_slot_id = _require_str(value, field=field)
    if not _TASK_SLOT_ID_PATTERN.fullmatch(task_slot_id):
        raise ValueError(f"{field} must be a URL-safe task slot identifier")
    return task_slot_id


def validate_task_input_original_file_name(
    value: Any,
    *,
    field: str = "original_file_name",
) -> str:
    return _validate_original_file_name(value, field=field)


def _validate_task_input_entry(value: Any, *, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    extra = set(value) - _ENTRY_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _ENTRY_KEYS - set(value)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    return {
        "task_slot_id": validate_task_slot_id(
            value["task_slot_id"],
            field=f"{label}.task_slot_id",
        ),
        "file_hash": validate_file_hash_format(
            value["file_hash"],
            field=f"{label}.file_hash",
        ),
        "original_file_name": _validate_original_file_name(
            value["original_file_name"],
            field=f"{label}.original_file_name",
        ),
        "source_ref": validate_task_input_source_ref(
            value["source_ref"],
            field=f"{label}.source_ref",
        ),
    }


def validate_task_input_manifest(payload: Mapping[str, Any]) -> None:
    """Validate one TaskInput artifact without resolving source bytes."""

    if not isinstance(payload, Mapping):
        raise TypeError("task_input manifest must be a mapping")
    extra = set(payload) - _ROOT_KEYS
    if extra:
        raise ValueError(f"task_input manifest has unexpected keys: {sorted(extra)!r}")
    missing = _ROOT_KEYS - set(payload)
    if missing:
        raise ValueError(
            f"task_input manifest is missing required keys: {sorted(missing)!r}"
        )

    artifact_type = _require_str(payload["artifact_type"], field="artifact_type")
    if artifact_type != TASK_INPUT_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {TASK_INPUT_ARTIFACT_TYPE!r}, got {artifact_type!r}"
        )
    schema_version = _require_str(payload["schema_version"], field="schema_version")
    if schema_version != TASK_INPUT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {TASK_INPUT_SCHEMA_VERSION!r}, got "
            f"{schema_version!r}"
        )

    _require_task_run_id(payload["task_run_id"])

    inputs = payload["inputs"]
    if not isinstance(inputs, list):
        raise TypeError("inputs must be an array")
    if not inputs:
        raise ValueError("inputs must contain at least one entry")
    normalized = [
        _validate_task_input_entry(value, label=f"inputs[{index}]")
        for index, value in enumerate(inputs)
    ]
    slot_ids = [entry["task_slot_id"] for entry in normalized]
    if len(set(slot_ids)) != len(slot_ids):
        raise ValueError("inputs must not contain duplicate task_slot_id values")


def build_task_input_entry(
    *,
    task_slot_id: str,
    file_hash: str,
    original_file_name: str,
    source_ref: str,
) -> dict[str, str]:
    """Build and validate one TaskInput entry record."""

    return _validate_task_input_entry(
        {
            "task_slot_id": task_slot_id,
            "file_hash": file_hash,
            "original_file_name": original_file_name,
            "source_ref": source_ref,
        },
        label="inputs entry",
    )


def build_task_input_entry_from_intake(
    *,
    task_slot_id: str,
    source_ref: str,
    request_file_intake_result: Mapping[str, Any],
) -> dict[str, str]:
    """Build one TaskInput entry from neutral Intake facts and a Task-owned source_ref."""

    from artifacts.request_file_intake import validate_request_file_intake_result

    validate_request_file_intake_result(request_file_intake_result)
    document = request_file_intake_result["document"]
    if not isinstance(document, Mapping):
        raise TypeError("request_file_intake_result.document must be a mapping")
    return build_task_input_entry(
        task_slot_id=task_slot_id,
        file_hash=str(document["file_hash"]),
        original_file_name=str(document["original_file_name"]),
        source_ref=source_ref,
    )


def build_task_input_manifest(
    *,
    task_run_id: str,
    inputs: Sequence[TaskInputEntry],
) -> dict[str, Any]:
    """Build and validate one TaskInput artifact."""

    manifest: dict[str, Any] = {
        "artifact_type": TASK_INPUT_ARTIFACT_TYPE,
        "schema_version": TASK_INPUT_SCHEMA_VERSION,
        "task_run_id": _require_task_run_id(task_run_id),
        "inputs": [entry.to_record() for entry in inputs],
    }
    validate_task_input_manifest(manifest)
    return manifest


__all__ = [
    "TASK_INPUT_ARTIFACT_TYPE",
    "TASK_INPUT_FILENAME",
    "TASK_INPUT_SCHEMA_VERSION",
    "TaskInputEntry",
    "build_task_input_entry",
    "build_task_input_entry_from_intake",
    "build_task_input_manifest",
    "validate_task_input_manifest",
    "validate_task_input_original_file_name",
    "validate_task_input_source_ref",
    "validate_task_slot_id",
]
