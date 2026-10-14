"""Neutral projection of analysis-text heading ancestry for artifact packaging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisHeadingProjection:
    content: dict[str, tuple[str, ...]]
    tables: dict[str, tuple[str, ...]]


def _doc_order(block: dict[str, Any]) -> int:
    value = block.get("doc_order_index")
    if value is None:
        value = block.get("order")
    return int(value) if value is not None else 10**9


def _apply_heading(stack: list[str], block: dict[str, Any]) -> list[str]:
    if block.get("kind") != "heading":
        return stack
    level = (block.get("meta") or {}).get("heading_level")
    if not isinstance(level, int):
        return stack
    return stack[: max(level - 1, 0)] + [str(block.get("analysis_text") or "")]


def project_analysis_heading_paths(
    analysis_bundle: dict[str, Any],
) -> AnalysisHeadingProjection:
    """Create the masked/analysis representation without re-parsing source structure."""

    content_blocks = sorted(
        (b for b in analysis_bundle.get("content_blocks") or [] if isinstance(b, dict)),
        key=lambda b: (_doc_order(b), str(b.get("block_id") or "")),
    )
    table_blocks = sorted(
        (b for b in analysis_bundle.get("table_blocks") or [] if isinstance(b, dict)),
        key=lambda b: (_doc_order(b), str(b.get("block_id") or "")),
    )

    stack: list[str] = []
    content_paths: dict[str, tuple[str, ...]] = {}
    for block in content_blocks:
        stack = _apply_heading(stack, block)
        block_id = str(block.get("block_id") or "")
        if block_id:
            content_paths[block_id] = tuple(stack)

    timeline = [(_doc_order(block), 0, block) for block in content_blocks]
    timeline.extend((_doc_order(block), 1, block) for block in table_blocks)
    timeline.sort(key=lambda item: (item[0], item[1], str(item[2].get("block_id") or "")))
    stack = []
    table_paths: dict[str, tuple[str, ...]] = {}
    for _, kind_rank, block in timeline:
        if kind_rank == 0:
            stack = _apply_heading(stack, block)
            continue
        block_id = str(block.get("block_id") or "")
        if block_id:
            table_paths[block_id] = tuple(stack)

    return AnalysisHeadingProjection(content=content_paths, tables=table_paths)


__all__ = ["AnalysisHeadingProjection", "project_analysis_heading_paths"]
