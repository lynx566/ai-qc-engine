"""Minimal Extract strategy resolution by configuration id."""

from __future__ import annotations

from collections.abc import Callable

from core.document.doc_identity import DocumentProcessingIdentity
from core.document.document_schema import DocumentBundle

ExtractCallable = Callable[..., DocumentBundle]


class UnsupportedExtractFormatError(ValueError):
    """Raised when *extract_config_id* has no Extract implementation."""


def resolve_extract_strategy(extract_config_id: str) -> ExtractCallable:
    """Return the Extract implementation for *extract_config_id*."""
    token = str(extract_config_id).strip().lower()
    if not token:
        raise UnsupportedExtractFormatError("extract_config_id must be a non-empty string")
    if token == "docx":
        from core.document.docx import extract_docx_document

        return extract_docx_document
    raise UnsupportedExtractFormatError(
        f"Unsupported extract_config_id {extract_config_id!r}; supported: docx"
    )


__all__ = [
    "ExtractCallable",
    "UnsupportedExtractFormatError",
    "resolve_extract_strategy",
]
