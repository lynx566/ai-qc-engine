"""Formal contracts for Doc Meta stage artifacts (doc_meta_bundle, document_context_preview).

Owns canonical filenames and the doc_meta_bundle.json body builder only.
Does not perform metadata extraction, clinical summary interpretation, or preview projection.
"""

from __future__ import annotations

from typing import Any

from core.metadata.schemas import MetadataResult

DOC_META_BUNDLE_FILENAME = "doc_meta_bundle.json"
DOCUMENT_CONTEXT_PREVIEW_FILENAME = "document_context_preview.json"


def metadata_result_to_doc_meta_bundle(
    result: MetadataResult,
    *,
    doc_meta_bundle_id: str,
    summary: dict[str, Any],
    file_hash: str | None = None,
) -> dict[str, Any]:
    """Serialize MetadataResult to doc_meta_bundle with caller-provided summary."""
    base = result.to_dict()
    bundle: dict[str, Any] = {
        "doc_meta_bundle_id": doc_meta_bundle_id,
        "doc_id": base["doc_id"],
        "profile": base["profile"],
        "context_strategy": base["context_strategy"],
        "context_block_count": base["context_block_count"],
        "summary": summary,
        "doc_type": base["doc_type"],
        "fields": base["fields"],
        "warnings": base["warnings"],
    }
    if isinstance(file_hash, str) and file_hash.strip():
        bundle["file_hash"] = file_hash.strip()
    return bundle
