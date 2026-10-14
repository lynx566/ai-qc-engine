"""Dev/integration bootstrap for per-document processing identity.

Production orchestration will supply ``file_hash`` from Request File Intake and
call :func:`build_document_processing_identity` at processing launch. This module
is for naked-path dev and integration callers only.
"""

from __future__ import annotations

from pathlib import Path

from core.document.doc_identity import (
    DocumentProcessingIdentity,
    build_document_processing_identity,
    compute_file_hash,
)


def bootstrap_processing_identity_from_path(path: Path | str) -> DocumentProcessingIdentity:
    """Hash *path* and build a new processing identity (dev/integration only)."""
    resolved = Path(path)
    return build_document_processing_identity(
        file_hash=compute_file_hash(resolved),
        original_file_name=resolved.name,
    )
