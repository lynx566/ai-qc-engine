"""Neutral admitted-source helpers for Document Consistency QC boundary adapters."""

from __future__ import annotations

from pathlib import Path

from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.request_file_intake import run_request_file_intake_operation


def admit_participant_source_path(
    *,
    project_root: Path,
    source_path: Path,
    intake_output_dir: Path | None = None,
) -> DocumentIntakeSourceBinding:
    """Run neutral Intake once for one participant source path."""

    report = run_request_file_intake_operation(
        project_root=project_root,
        source_file=source_path,
        output_dir=intake_output_dir,
    )
    return report.result.source_binding


__all__ = ["admit_participant_source_path"]
