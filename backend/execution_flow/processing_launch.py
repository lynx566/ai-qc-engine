"""Neutral Processing Launch: intaked source → document-processing identity."""

from __future__ import annotations

from core.document.doc_identity import (
    DocumentProcessingIdentity,
    build_document_processing_identity,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.extract import ExtractDocumentInput
from runtime.request_file_intake import RequestFileIntakeOperationReport


def launch_document_processing_from_admitted_source(
    admitted_source: DocumentIntakeSourceBinding,
) -> ExtractDocumentInput:
    """Launch one document-processing instance from an admitted source binding."""

    identity = build_document_processing_identity(
        file_hash=admitted_source.file_hash,
        original_file_name=admitted_source.original_file_name,
    )
    return ExtractDocumentInput(
        source_path=admitted_source.source_path,
        identity=identity,
    )


def launch_document_processing_from_intake(
    intake_report: RequestFileIntakeOperationReport,
) -> ExtractDocumentInput:
    """Launch one document-processing instance from authoritative Intake outputs."""
    intake_result = intake_report.result.request_file_intake_result
    document = intake_result.get("document")
    if not isinstance(document, dict):
        raise ValueError("request_file_intake_result.document must be a mapping")
    file_hash = document.get("file_hash")
    original_file_name = document.get("original_file_name")
    if not isinstance(file_hash, str) or not file_hash.strip():
        raise ValueError("request_file_intake_result.document.file_hash is required")
    if not isinstance(original_file_name, str) or not original_file_name.strip():
        raise ValueError(
            "request_file_intake_result.document.original_file_name is required"
        )
    binding = intake_report.result.source_binding
    if binding.file_hash != file_hash.strip():
        raise ValueError(
            f"source binding file_hash {binding.file_hash!r} does not match "
            f"intake document file_hash {file_hash.strip()!r}"
        )
    if binding.original_file_name != original_file_name.strip():
        raise ValueError(
            "source binding original_file_name does not match intake document"
        )
    return launch_document_processing_from_admitted_source(binding)


def launched_document_identity(launched_document: ExtractDocumentInput) -> DocumentProcessingIdentity:
    """Return the processing identity from a launched document input."""
    return launched_document.identity
