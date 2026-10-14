"""Persist Request File Intake runtime artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.request_file_intake import (
    REQUEST_FILE_INTAKE_RESULT_FILENAME,
    validate_request_file_intake_result,
)
from runtime.io import load_json, save_json
from runtime.run_index import (
    build_request_file_intake_index_document,
    resolve_index_root,
    write_run_index,
)
from runtime.run_summaries import build_request_file_intake_run_summary


@dataclass(frozen=True)
class RequestFileIntakePersistenceResult:
    request_file_intake_result_path: Path
    run_summary_path: Path
    index_path: Path | None


def persist_request_file_intake_run(
    *,
    output_dir: Path,
    run_id: str,
    request_file_intake_result: dict[str, Any],
    source_file: Path,
    git_root: Path,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> RequestFileIntakePersistenceResult:
    """Write formal result, run summary, and index without mutating artifact semantics."""
    validate_request_file_intake_result(request_file_intake_result)

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result_path = out_dir / REQUEST_FILE_INTAKE_RESULT_FILENAME
    save_json(result_path, request_file_intake_result)

    summary_path = out_dir / "run_summary.json"
    summary = build_request_file_intake_run_summary(
        run_id=run_id,
        source_file=source_file,
        request_file_intake_result=request_file_intake_result,
        git_root=git_root,
        git_provenance=git_provenance,
    )
    save_json(summary_path, summary)

    index_root = resolve_index_root(session_dir=out_dir)
    index_document = build_request_file_intake_index_document(
        run_id=run_id,
        request_file_intake_result=request_file_intake_result,
        out_dir=out_dir,
        index_root=index_root,
    )
    index_path = write_run_index(
        index_root,
        step="request_file_intake",
        documents=[index_document],
        run_id=run_id,
    )

    reloaded = load_json(result_path)
    validate_request_file_intake_result(reloaded)
    if reloaded != request_file_intake_result:
        raise RuntimeError(
            "persisted request_file_intake_result does not match in-memory result"
        )

    return RequestFileIntakePersistenceResult(
        request_file_intake_result_path=result_path,
        run_summary_path=summary_path,
        index_path=index_path,
    )
