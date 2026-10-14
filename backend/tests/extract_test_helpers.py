"""Test helpers for canonical Extract (not production bootstrap)."""

from __future__ import annotations

from pathlib import Path

from core.document.doc_identity import (
    DocumentProcessingIdentity,
    build_document_processing_identity,
    compute_file_hash,
)
from core.document.docx import extract_docx_document
from core.document.document_schema import DocumentBundle


def build_test_processing_identity(path: Path | str) -> DocumentProcessingIdentity:
    """Build processing identity for a test file (hashes path bytes)."""
    resolved = Path(path)
    return build_document_processing_identity(
        file_hash=compute_file_hash(resolved),
        original_file_name=resolved.name,
    )


def extract_docx_for_test(
    path: Path | str,
    *,
    identity: DocumentProcessingIdentity | None = None,
) -> DocumentBundle:
    """Run canonical Extract with explicit or test-bootstrapped identity."""
    resolved = Path(path)
    resolved_identity = identity or build_test_processing_identity(resolved)
    return extract_docx_document(resolved.read_bytes(), identity=resolved_identity)
