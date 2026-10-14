"""Deterministic QC report TaskRun workspace for integration tests."""

from __future__ import annotations

import json
import shutil
import tarfile
from pathlib import Path

from artifacts.task_input import TaskInputEntry, build_task_input_manifest
from runtime.io import load_json, save_json

REPRESENTATIVE_TASK_RUN_ID = "task_run_qc_report_representative"

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "qc_report_representative"
_ARCHIVE = _FIXTURE_DIR / "workspace.tar.gz"

_SHOWCASE_DOCX = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "clinical_trial_doc"
    / "docx"
    / "zh"
    / "clinical_program_001_vt8802"
    / "demo"
    / "艾美妥珠单抗 研发期间安全性更新报告#2_错误模拟.docx"
)


def install_representative_qc_task_run(project_root: Path) -> str:
    """Materialize a completed DSUR QC TaskRun under ``project_root``."""

    if not _ARCHIVE.is_file():
        raise FileNotFoundError(
            f"representative QC fixture archive missing: {_ARCHIVE}"
        )
    runs_root = project_root / "runs"
    if runs_root.exists():
        shutil.rmtree(runs_root)
    runs_root.mkdir(parents=True)
    with tarfile.open(_ARCHIVE, "r:gz") as archive:
        archive.extractall(project_root)
    _materialize_runs_path_strings(project_root)
    _ensure_task_input_source_file(project_root)
    return REPRESENTATIVE_TASK_RUN_ID


def _ensure_task_input_source_file(project_root: Path) -> None:
    if not _SHOWCASE_DOCX.is_file():
        raise FileNotFoundError(f"showcase docx missing: {_SHOWCASE_DOCX}")
    task_root = project_root / "runs" / "task_runs" / REPRESENTATIVE_TASK_RUN_ID
    manifest = load_json(task_root / "task_input.json")
    admitted = manifest["inputs"][0]
    source_dir = task_root / "inputs" / "source" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / admitted["original_file_name"]
    if not target.is_file():
        shutil.copy2(_SHOWCASE_DOCX, target)
    expected_ref = (
        f"runs/task_runs/{REPRESENTATIVE_TASK_RUN_ID}/inputs/source/source/"
        f"{admitted['original_file_name']}"
    )
    if admitted.get("source_ref") != expected_ref:
        admitted["source_ref"] = expected_ref
        save_json(task_root / "task_input.json", manifest)


def _runs_relative_suffix(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    marker = "/runs/"
    index = normalized.find(marker)
    if index < 0:
        if normalized.startswith("runs/"):
            return normalized
        return None
    return normalized[index + 1 :]


def _transform_json_paths(node: object, transform) -> object:
    if isinstance(node, dict):
        return {key: _transform_json_paths(value, transform) for key, value in node.items()}
    if isinstance(node, list):
        return [_transform_json_paths(value, transform) for value in node]
    if isinstance(node, str):
        return transform(node)
    return node


def _portable_runs_path_strings(staging_root: Path) -> None:
    def to_portable(value: str) -> str:
        relative = _runs_relative_suffix(value)
        return relative if relative is not None else value

    for path in (staging_root / "runs").rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated = _transform_json_paths(payload, to_portable)
        path.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _materialize_runs_path_strings(project_root: Path) -> None:
    def to_absolute(value: str) -> str:
        relative = _runs_relative_suffix(value)
        if relative is None:
            return value
        return str((project_root / relative).resolve())

    for path in (project_root / "runs").rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated = _transform_json_paths(payload, to_absolute)
        path.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _rewrite_exported_task_identity(task_root: Path, *, flow_run_id: str) -> None:
    task_doc = load_json(task_root / "task_run.json")
    task_doc["task_run_id"] = REPRESENTATIVE_TASK_RUN_ID
    save_json(task_root / "task_run.json", task_doc)
    manifest = load_json(task_root / "task_input.json")
    manifest["task_run_id"] = REPRESENTATIVE_TASK_RUN_ID
    for entry in manifest["inputs"]:
        name = entry["original_file_name"]
        entry["source_ref"] = (
            f"runs/task_runs/{REPRESENTATIVE_TASK_RUN_ID}/inputs/source/source/{name}"
        )
    save_json(task_root / "task_input.json", manifest)
    lifecycle = load_json(task_root / "task_lifecycle.json")
    if lifecycle.get("task_run_id"):
        lifecycle["task_run_id"] = REPRESENTATIVE_TASK_RUN_ID
        save_json(task_root / "task_lifecycle.json", lifecycle)
    source_docx = next(
        (task_root / "inputs" / "source" / "source").glob("*.docx"), None
    )
    if source_docx and source_docx.is_file():
        source_docx.unlink()


__all__ = [
    "REPRESENTATIVE_TASK_RUN_ID",
    "install_representative_qc_task_run",
]
