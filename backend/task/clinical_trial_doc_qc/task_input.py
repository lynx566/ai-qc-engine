"""Product Task-owned TaskInput persistence, source layout, and runtime reconstruction."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

from artifacts.task_input import (
    TASK_INPUT_FILENAME,
    TaskInputEntry,
    build_task_input_manifest,
    validate_task_input_manifest,
    validate_task_input_original_file_name,
    validate_task_input_source_ref,
    validate_task_slot_id,
)
from artifacts.task_run import load_task_run_manifest, task_run_manifest_path
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.io import load_json, save_json_atomic

_TASK_INPUTS_DIR = "inputs"
_TASK_SOURCE_SUBDIR = "source"
_TASK_INTAKE_SUBDIR = "intake"


def task_run_root(*, project_root: Path, task_run_id: str) -> Path:
    """Return the canonical TaskRun artifact root directory."""

    return task_run_manifest_path(
        project_root=project_root,
        task_run_id=task_run_id,
    ).parent


def task_input_manifest_path(*, project_root: Path, task_run_id: str) -> Path:
    """Return the canonical TaskInput artifact path."""

    return (
        task_run_root(project_root=project_root, task_run_id=task_run_id)
        / TASK_INPUT_FILENAME
    )


def task_input_slot_root(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_id: str,
) -> Path:
    """Return ``runs/task_runs/<T>/inputs/<slot>/``."""

    slot_id = validate_task_slot_id(task_slot_id, field="task_slot_id")
    return (
        task_run_root(project_root=project_root, task_run_id=task_run_id)
        / _TASK_INPUTS_DIR
        / slot_id
    )


def task_input_source_dir(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_id: str,
) -> Path:
    """Return ``runs/task_runs/<T>/inputs/<slot>/source/``."""

    return (
        task_input_slot_root(
            project_root=project_root,
            task_run_id=task_run_id,
            task_slot_id=task_slot_id,
        )
        / _TASK_SOURCE_SUBDIR
    )


def task_input_intake_dir(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_id: str,
) -> Path:
    """Return ``runs/task_runs/<T>/inputs/<slot>/intake/`` for future neutral Intake."""

    return (
        task_input_slot_root(
            project_root=project_root,
            task_run_id=task_run_id,
            task_slot_id=task_slot_id,
        )
        / _TASK_INTAKE_SUBDIR
    )


def task_input_source_file_path(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_id: str,
    original_file_name: str,
) -> Path:
    """Return the canonical Task-owned source file path for one slot."""

    safe_name = validate_task_input_original_file_name(
        original_file_name,
        field="original_file_name",
    )
    return (
        task_input_source_dir(
            project_root=project_root,
            task_run_id=task_run_id,
            task_slot_id=task_slot_id,
        )
        / safe_name
    )


def task_owned_source_ref(
    *,
    project_root: Path,
    destination_path: Path,
) -> str:
    """Serialize one Task-owned source path as a project-relative POSIX source_ref."""

    root = project_root.resolve()
    resolved = destination_path.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"destination {resolved} is not under project_root {root}"
        ) from exc
    return validate_task_input_source_ref(rel.as_posix(), field="source_ref")


def resolve_task_input_source_path(
    *,
    project_root: Path,
    source_ref: str,
) -> Path:
    """Resolve and containment-check one persisted TaskInput source_ref."""

    normalized_ref = validate_task_input_source_ref(source_ref, field="source_ref")
    root = project_root.resolve()
    resolved = (root / Path(normalized_ref)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"source_ref {normalized_ref!r} resolves outside project_root"
        ) from exc
    return resolved


def materialize_task_input_source(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_id: str,
    source_path: Path,
    original_file_name: str | None = None,
) -> Path:
    """Copy source bytes into the TaskRun-owned source location.

    This establishes Task-managed source bytes only. It does not hash, run Intake,
    persist TaskInput, or admit canonical Product input facts.
    """

    load_task_run_manifest(project_root=project_root, task_run_id=task_run_id)

    resolved_source = Path(source_path).resolve()
    if not resolved_source.is_file():
        raise ValueError(
            f"source_path must be a regular file: {resolved_source.as_posix()}"
        )

    file_name = (
        original_file_name if original_file_name is not None else resolved_source.name
    )
    safe_name = validate_task_input_original_file_name(
        file_name, field="original_file_name"
    )

    destination = task_input_source_file_path(
        project_root=project_root,
        task_run_id=task_run_id,
        task_slot_id=task_slot_id,
        original_file_name=safe_name,
    )
    if destination.exists():
        raise FileExistsError(
            f"Task-owned source already exists for slot {task_slot_id!r}: "
            f"{destination.as_posix()}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(temp_fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(resolved_source, temp_path)
        with temp_path.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        # Linking then unlinking the same-directory temp publishes a complete file
        # without replacing a destination created by a concurrent writer.
        os.link(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)
    return destination.resolve()


def _validate_owned_source_entry(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_id: str,
    original_file_name: str,
    source_ref: str,
) -> Path:
    expected_path = task_input_source_file_path(
        project_root=project_root,
        task_run_id=task_run_id,
        task_slot_id=task_slot_id,
        original_file_name=original_file_name,
    ).resolve()
    expected_ref = task_owned_source_ref(
        project_root=project_root,
        destination_path=expected_path,
    )
    normalized_ref = validate_task_input_source_ref(source_ref, field="source_ref")
    if normalized_ref != expected_ref:
        raise ValueError(
            "source_ref must equal the canonical Task-owned source_ref for "
            f"task_run_id={task_run_id!r}, task_slot_id={task_slot_id!r}"
        )
    resolved = resolve_task_input_source_path(
        project_root=project_root,
        source_ref=normalized_ref,
    )
    if not resolved.is_file():
        raise ValueError(
            "canonical Task-owned source must exist as a regular file: "
            f"{resolved.as_posix()}"
        )
    return resolved


def persist_task_input(
    *,
    project_root: Path,
    task_run_id: str,
    inputs: tuple[TaskInputEntry, ...],
) -> Path:
    """Persist one canonical TaskInput manifest after verifying TaskRun ownership."""

    load_task_run_manifest(project_root=project_root, task_run_id=task_run_id)
    path = task_input_manifest_path(project_root=project_root, task_run_id=task_run_id)
    if path.exists():
        raise FileExistsError(f"task_input already exists: {path.as_posix()}")

    for entry in inputs:
        _validate_owned_source_entry(
            project_root=project_root,
            task_run_id=task_run_id,
            task_slot_id=entry.task_slot_id,
            original_file_name=entry.original_file_name,
            source_ref=entry.source_ref,
        )

    manifest = build_task_input_manifest(task_run_id=task_run_id, inputs=inputs)
    save_json_atomic(path, manifest)
    reloaded = load_json(path)
    validate_task_input_manifest(reloaded)
    if reloaded != manifest:
        raise RuntimeError("persisted task_input does not match input manifest")
    if reloaded["task_run_id"] != task_run_id:
        raise ValueError("task_input.task_run_id does not match requested task_run_id")
    return path


def load_task_input_manifest(
    *,
    project_root: Path,
    task_run_id: str,
) -> dict[str, object]:
    """Load and validate one canonical TaskInput artifact."""

    path = task_input_manifest_path(project_root=project_root, task_run_id=task_run_id)
    manifest = load_json(path)
    validate_task_input_manifest(manifest)
    if manifest["task_run_id"] != task_run_id:
        raise ValueError("task_input.task_run_id does not match requested task_run_id")
    return dict(manifest)


def load_task_input_bindings(
    *,
    project_root: Path,
    task_run_id: str,
) -> dict[str, DocumentIntakeSourceBinding]:
    """Reconstruct runtime admitted-source bindings from persisted TaskInput facts."""

    manifest = load_task_input_manifest(
        project_root=project_root, task_run_id=task_run_id
    )
    inputs_raw = manifest["inputs"]
    if not isinstance(inputs_raw, list):
        raise TypeError("inputs must be an array")

    bindings: dict[str, DocumentIntakeSourceBinding] = {}
    for item in inputs_raw:
        if not isinstance(item, Mapping):
            raise TypeError("inputs entry must be a mapping")
        task_slot_id = str(item["task_slot_id"])
        file_hash = str(item["file_hash"])
        original_file_name = str(item["original_file_name"])
        source_ref = str(item["source_ref"])
        source_path = _validate_owned_source_entry(
            project_root=project_root,
            task_run_id=task_run_id,
            task_slot_id=task_slot_id,
            original_file_name=original_file_name,
            source_ref=source_ref,
        )
        bindings[task_slot_id] = DocumentIntakeSourceBinding(
            file_hash=file_hash,
            original_file_name=original_file_name,
            source_path=source_path,
        )
    return bindings


__all__ = [
    "load_task_input_bindings",
    "load_task_input_manifest",
    "materialize_task_input_source",
    "persist_task_input",
    "resolve_task_input_source_path",
    "task_input_intake_dir",
    "task_input_manifest_path",
    "task_input_source_dir",
    "task_input_source_file_path",
    "task_owned_source_ref",
    "task_run_root",
]
