from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from core.document.doc_identity import require_bundle_file_hash
from core.metadata.block_context import require_analysis_bundle
from artifacts.doc_meta import metadata_result_to_doc_meta_bundle
from core.metadata.rule_engine import extract_metadata_from_analysis_bundle
from core.metadata.schemas import MetadataProfile


@dataclass(frozen=True)
class DocMetaPayloads:
    doc_meta_bundle: dict[str, Any]
    document_context_preview: dict[str, Any]


def build_doc_meta_payloads(
    *,
    analysis_bundle: dict[str, Any],
    profile: MetadataProfile,
    build_summary: Callable[[dict[str, Any]], dict[str, Any]],
    doc_meta_bundle_id: str,
    context_block_count: int | None = None,
) -> DocMetaPayloads:
    """Build doc_meta artifact payloads from an in-memory analysis_bundle."""
    require_analysis_bundle(analysis_bundle)

    effective_block_count = (
        context_block_count
        if context_block_count is not None
        else profile.context.default_block_count
    )

    metadata_result, metadata_sources = extract_metadata_from_analysis_bundle(
        doc_id=str(analysis_bundle.get("doc_id", "")),
        analysis_bundle=analysis_bundle,
        profile=profile,
        context_block_count=effective_block_count,
    )

    legacy_blocks = [
        {
            "block_id": s.block_id,
            "kind": s.kind,
            "text": s.text,
            "order": s.order,
        }
        for s in metadata_sources
        if s.source_type in ("title_block", "heading", "early_block")
    ]

    metadata_base = metadata_result.to_dict()
    summary = build_summary(metadata_base)
    doc_meta_bundle = metadata_result_to_doc_meta_bundle(
        metadata_result,
        doc_meta_bundle_id=doc_meta_bundle_id,
        summary=summary,
        file_hash=require_bundle_file_hash(analysis_bundle, label="analysis_bundle"),
    )
    document_context_preview = {
        "doc_id": str(analysis_bundle.get("doc_id", "")),
        "source": "analysis_bundle",
        "strategy": profile.context.strategy,
        "context_block_count": effective_block_count,
        "sources": [asdict(s) for s in metadata_sources],
        "blocks": legacy_blocks,
    }
    return DocMetaPayloads(
        doc_meta_bundle=doc_meta_bundle,
        document_context_preview=document_context_preview,
    )
