from __future__ import annotations

from typing import Any

from .block_context import analysis_block_text, require_analysis_bundle
from .schemas import MetadataSource

DEFAULT_DOC_TYPE_SOURCE_PRIORITY: tuple[str, ...] = (
    "file_name",
    "display_name",
    "title_block",
    "heading",
    "early_block",
)

DEFAULT_FIELD_SOURCE_TYPES: tuple[str, ...] = (
    "title_block",
    "heading",
    "early_block",
)


def _normalize_block_id(block_id: object) -> str:
    """Use bundle-local block_id (e.g. C0001), not legacy doc_id-prefixed ids."""
    return str(block_id or "").strip()


def build_metadata_sources(
    analysis_bundle: dict[str, Any],
    *,
    context_block_count: int,
) -> list[MetadataSource]:
    """
    Build structured evidence sources from an analysis_bundle (safe zone only).
    """
    require_analysis_bundle(analysis_bundle)

    sources: list[MetadataSource] = []
    doc_id = str(analysis_bundle.get("doc_id") or "doc")

    file_name = str(analysis_bundle.get("file_name") or "").strip()
    if file_name:
        sources.append(
            MetadataSource(
                source_id=f"{doc_id}:file_name",
                source_type="file_name",
                text=file_name,
            )
        )

    display_name = str(analysis_bundle.get("display_name") or "").strip()
    if display_name:
        sources.append(
            MetadataSource(
                source_id=f"{doc_id}:display_name",
                source_type="display_name",
                text=display_name,
            )
        )

    raw_blocks = (analysis_bundle.get("content_blocks") or [])[:context_block_count]
    title_slot_used = False

    for block in raw_blocks:
        if not isinstance(block, dict):
            continue

        text = analysis_block_text(block)
        if not text:
            continue

        block_id = _normalize_block_id(block.get("block_id"))
        kind = str(block.get("kind") or "")
        order = block.get("order")
        meta = block.get("meta") if isinstance(block.get("meta"), dict) else {}

        if kind == "heading":
            source_type = "heading"
        elif not title_slot_used:
            source_type = "title_block"
            title_slot_used = True
        else:
            source_type = "early_block"

        source_id = f"{doc_id}:{source_type}:{block_id or len(sources)}"
        sources.append(
            MetadataSource(
                source_id=source_id,
                source_type=source_type,
                text=text,
                block_id=block_id or None,
                kind=kind or None,
                order=order if isinstance(order, int) else None,
                meta=dict(meta),
            )
        )

    return sources


def sources_by_type(
    sources: list[MetadataSource],
    source_type: str,
) -> list[MetadataSource]:
    return [s for s in sources if s.source_type == source_type]


def context_block_source_types() -> tuple[str, ...]:
    """Metadata source types derived from analysis_bundle content blocks."""
    return ("title_block", "heading", "early_block")
