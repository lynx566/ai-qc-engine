"""Production-owned Intake → Launch → Extract orchestration sequence.

``on_intake_launched`` is an optional lifecycle hook invoked after Intake and
Launch complete and before Extract starts. Its contract is neutral document
processing only:

    on_intake_launched(intake_report, launched_document)

Callers (for example QC Flow) may map those values into their own provenance
models inside the callback. This module must not accept or import consumer
representations such as slot provenance bags or flow execution state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from execution_flow.processing_launch import (
    launch_document_processing_from_admitted_source,
    launch_document_processing_from_intake,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.extract import ExtractDocumentInput, ExtractOperationReport, run_extract_operation
from runtime.request_file_intake import (
    RequestFileIntakeOperationReport,
    run_request_file_intake_operation,
)


@dataclass(frozen=True)
class DocumentProcessingLaunchExtractResult:
    admitted_source: DocumentIntakeSourceBinding
    launched_document: ExtractDocumentInput
    extract_report: ExtractOperationReport


@dataclass(frozen=True)
class DocumentProcessingIntakeLaunchExtractResult:
    intake_report: RequestFileIntakeOperationReport
    extract_report: ExtractOperationReport


def run_document_processing_launch_extract(
    *,
    project_root: Path,
    admitted_source: DocumentIntakeSourceBinding,
    extract_config_id: str,
    extract_output_dir: Path | str | None = None,
    extract_run_id: str | None = None,
    export_slices: bool = False,
    git_provenance: Mapping[str, str | bool | None] | None = None,
    on_launched: (
        Callable[[DocumentIntakeSourceBinding, ExtractDocumentInput], None] | None
    ) = None,
) -> DocumentProcessingLaunchExtractResult:
    """Run Processing Launch and Extract for one already-admitted source."""

    git_prov = dict(git_provenance) if git_provenance is not None else None
    launched_document = launch_document_processing_from_admitted_source(admitted_source)
    if on_launched is not None:
        on_launched(admitted_source, launched_document)
    extract_report = run_extract_operation(
        project_root=project_root,
        document=launched_document,
        extract_config_id=extract_config_id,
        output_dir=extract_output_dir,
        run_id=extract_run_id,
        export_slices=export_slices,
        git_provenance=git_prov,
    )
    return DocumentProcessingLaunchExtractResult(
        admitted_source=admitted_source,
        launched_document=launched_document,
        extract_report=extract_report,
    )


def run_document_processing_intake_launch_extract(
    *,
    project_root: Path,
    source_file: Path | str,
    extract_config_id: str,
    intake_output_dir: Path | str | None = None,
    extract_output_dir: Path | str | None = None,
    intake_run_id: str | None = None,
    extract_run_id: str | None = None,
    export_slices: bool = False,
    git_provenance: Mapping[str, str | bool | None] | None = None,
    on_intake_launched: (
        Callable[[RequestFileIntakeOperationReport, ExtractDocumentInput], None] | None
    ) = None,
) -> DocumentProcessingIntakeLaunchExtractResult:
    """Run Request File Intake, processing launch, and Extract for one source file.

    ``on_intake_launched`` runs after identity is established and before Extract.
    Use it when a caller must record intake/launch outcomes even if Extract later
    fails. Keep hook arguments limited to ``RequestFileIntakeOperationReport`` and
    ``ExtractDocumentInput``; do not widen the signature for consumer-specific
    provenance structures.
    """
    git_prov = dict(git_provenance) if git_provenance is not None else None
    intake_report = run_request_file_intake_operation(
        project_root=project_root,
        source_file=source_file,
        output_dir=intake_output_dir,
        run_id=intake_run_id,
        git_provenance=git_prov,
    )
    launched_document = launch_document_processing_from_intake(intake_report)
    if on_intake_launched is not None:
        on_intake_launched(intake_report, launched_document)
    extract_report = run_extract_operation(
        project_root=project_root,
        document=launched_document,
        extract_config_id=extract_config_id,
        output_dir=extract_output_dir,
        run_id=extract_run_id,
        export_slices=export_slices,
        git_provenance=git_prov,
    )
    return DocumentProcessingIntakeLaunchExtractResult(
        intake_report=intake_report,
        extract_report=extract_report,
    )
