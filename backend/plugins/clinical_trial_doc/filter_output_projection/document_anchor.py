"""Document-order anchors for clinical-trial projected sources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.document.block_position import block_position_key
from operations.filter_output_projection.contracts import (
    ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
    RAW_SOURCE_REPRESENTATION_KIND,
    ProjectedSource,
)

DocumentPositionAnchor = tuple[tuple[int, int, int], int]


def projected_source_document_anchor(
    source: ProjectedSource,
    *,
    blocks_by_id: Mapping[str, Mapping[str, Any]],
) -> DocumentPositionAnchor:
    """Resolve one projected source to a stable document-order anchor."""

    if source.representation_kind == RAW_SOURCE_REPRESENTATION_KIND:
        block_id = source.source_refs[0].refs["block_id"].strip()
        block = blocks_by_id.get(block_id, {})
        return (block_position_key(block), 0)

    if source.representation_kind == ASSEMBLED_SEMANTIC_REPRESENTATION_KIND:
        if not source.sentences:
            raise ValueError(
                "assembled_semantic projected source requires non-empty "
                "sentences for document-order anchor"
            )
        primary_block_id = source.source_refs[0].refs["block_id"].strip()
        anchors: list[DocumentPositionAnchor] = []
        for index, sentence in enumerate(source.sentences):
            if sentence.source_block_id.strip() != primary_block_id:
                continue
            block = blocks_by_id.get(sentence.source_block_id.strip(), {})
            anchors.append((block_position_key(block), index))
        if anchors:
            return min(anchors)
        block = blocks_by_id.get(primary_block_id, {})
        return (block_position_key(block), 0)

    raise ValueError(
        f"unsupported representation_kind for document-order anchor: "
        f"{source.representation_kind!r}"
    )


__all__ = [
    "DocumentPositionAnchor",
    "projected_source_document_anchor",
]
