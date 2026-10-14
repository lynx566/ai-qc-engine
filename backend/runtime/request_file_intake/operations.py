"""Request File Intake runtime operation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steps.request_file_intake import RequestFileInput, run as run_request_file_intake_step
from runtime.document_source_binding import (
    DocumentIntakeSourceBinding,
    build_intake_source_binding,
)
from runtime.request_file_intake.persistence import persist_request_file_intake_run
from runtime.run_ids import build_run_id_from_session_dir, build_session_dir_segment, utc_run_stamp
from runtime.run_layout import REQUEST_FILE_INTAKE_RUN_DIR_LAYOUT, sanitize_run_segment


REQUEST_FILE_INTAKE_STAGE = "request_file_intake"
REQUEST_FILE_INTAKE_CONTEXT = "request"


def _allocate_session_dir(
    runs_root: Path,
    *,
    stamp,
) -> Path:
    """Allocate ``runs/request_file_intake/<run_id>/`` with collision suffix when needed."""
    _ = REQUEST_FILE_INTAKE_RUN_DIR_LAYOUT, REQUEST_FILE_INTAKE_CONTEXT
    session_base = build_session_dir_segment(stamp)
    stage_root = runs_root / sanitize_run_segment(REQUEST_FILE_INTAKE_STAGE).lower()
    stage_root.mkdir(parents=True, exist_ok=True)
    candidate = stage_root / session_base
    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    suffix = 2
    while True:
        alt = stage_root / f"{session_base}__{suffix}"
        if not alt.exists():
            alt.mkdir(parents=True, exist_ok=True)
            return alt
        suffix += 1


@dataclass(frozen=True)
class RequestFileIntakeOperationResult:
    run_id: str
    output_dir: Path
    request_file_intake_result: dict[str, Any]
    source_binding: DocumentIntakeSourceBinding
    request_file_intake_result_path: Path
    run_summary_path: Path
    index_path: Path | None


@dataclass(frozen=True)
class RequestFileIntakeOperationReport:
    result: RequestFileIntakeOperationResult
    messages: tuple[str, ...]


def _resolve_source_file(source_file: Path) -> Path:
    candidate = Path(source_file)
    if not candidate.is_file():
        label = candidate.as_posix()
        raise ValueError(f"source_file must be a regular file: {label}")
    return candidate.resolve()


def _read_request_file_input(source_file: Path) -> RequestFileInput:
    try:
        content = source_file.read_bytes()
    except OSError as exc:
        raise ValueError(
            f"failed to read source_file {source_file.as_posix()}: {exc}"
        ) from exc
    return RequestFileInput(
        content=content,
        original_file_name=source_file.name,
    )


def _resolve_output_dir(
    *,
    project_root: Path,
    output_dir: Path | str | None,
    stamp,
) -> tuple[Path, str]:
    if output_dir is not None:
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        run_id = build_run_id_from_session_dir(
            REQUEST_FILE_INTAKE_STAGE,
            out_dir.name,
        )
        return out_dir, run_id

    session_dir = _allocate_session_dir(
        project_root / "runs",
        stamp=stamp,
    )
    run_id = build_run_id_from_session_dir(
        REQUEST_FILE_INTAKE_STAGE,
        session_dir.name,
    )
    return session_dir, run_id


def run_request_file_intake_operation(
    *,
    project_root: Path,
    source_file: Path | str,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> RequestFileIntakeOperationReport:
    """Execute Request File Intake for one source: read file, call Step, persist."""
    resolved_file = _resolve_source_file(Path(source_file))
    step_input = _read_request_file_input(resolved_file)
    step_result = run_request_file_intake_step(step_input)
    request_file_intake_result = step_result.request_file_intake_result
    source_binding = build_intake_source_binding(
        source_path=resolved_file,
        request_file_intake_result=request_file_intake_result,
    )

    stamp = utc_run_stamp()
    out_dir, resolved_run_id = _resolve_output_dir(
        project_root=project_root,
        output_dir=output_dir,
        stamp=stamp,
    )
    if run_id is not None:
        resolved_run_id = run_id

    persistence = persist_request_file_intake_run(
        output_dir=out_dir,
        run_id=resolved_run_id,
        request_file_intake_result=request_file_intake_result,
        source_file=resolved_file,
        git_root=project_root,
        git_provenance=git_provenance,
    )

    result = RequestFileIntakeOperationResult(
        run_id=resolved_run_id,
        output_dir=out_dir,
        request_file_intake_result=request_file_intake_result,
        source_binding=source_binding,
        request_file_intake_result_path=persistence.request_file_intake_result_path,
        run_summary_path=persistence.run_summary_path,
        index_path=persistence.index_path,
    )
    messages = (
        f"run_id: {resolved_run_id}",
        f"request_file_intake_result: {persistence.request_file_intake_result_path}",
        f"run_summary: {persistence.run_summary_path}",
    )
    if persistence.index_path is not None:
        messages = (*messages, f"index: {persistence.index_path}")
    return RequestFileIntakeOperationReport(result=result, messages=messages)
