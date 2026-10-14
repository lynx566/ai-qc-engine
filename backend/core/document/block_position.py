"""Neutral block manifest position keys for document-order comparison."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def block_kind_value(block: Mapping[str, Any]) -> str:
    return str(block.get("kind") or block.get("block_kind") or "paragraph").strip().lower()


def block_position_key(block: Mapping[str, Any]) -> tuple[int, int, int]:
    """Cross-stream document position key aligned with routing block ordering."""
    order = block.get("order")
    doc_idx = block.get("doc_order_index")
    primary = order if order is not None else doc_idx
    if primary is None:
        primary = 10**9
    secondary = doc_idx if doc_idx is not None else (order if order is not None else 0)
    kind = block_kind_value(block)
    if kind == "table_caption":
        kind_rank = 0
    elif kind == "table":
        kind_rank = 1
    elif kind == "table_note":
        kind_rank = 2
    else:
        kind_rank = 3
    return (int(primary), kind_rank, int(secondary))


def blocks_by_id(block_manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for group_key in ("blocks", "table_blocks"):
        blocks = block_manifest.get(group_key) or []
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_id = block.get("block_id")
            if block_id:
                out[str(block_id)] = block
    return out


def analysis_blocks_by_id(
    analysis_bundle: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index Prepare ``analysis_bundle`` blocks by ``block_id`` for sentence payload lookup."""

    out: dict[str, dict[str, Any]] = {}
    for group_key in (
        "content_blocks",
        "table_blocks",
        "front_matter_blocks",
        "format_blocks",
    ):
        blocks = analysis_bundle.get(group_key) or []
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_id = block.get("block_id")
            if block_id:
                out[str(block_id)] = block
    return out


__all__ = [
    "analysis_blocks_by_id",
    "block_kind_value",
    "block_position_key",
    "blocks_by_id",
]
