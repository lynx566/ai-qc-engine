"""Expand analysis_bundle block groups for filter strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _as_block_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [b for b in value if isinstance(b, dict)]


def _block_doc_order_key(block: dict[str, Any]) -> tuple[int, int, str]:
    doc_order = block.get("doc_order_index")
    order = block.get("order")
    return (
        doc_order if isinstance(doc_order, int) else 10**9,
        order if isinstance(order, int) else 0,
        str(block.get("block_id") or ""),
    )


@dataclass(frozen=True)
class BlockUniverse:
    """
    All block groups from an analysis_bundle, indexed for filter strategies.

    Strategies choose which groups to scan; the filter stage always builds a
    full universe so future strategies can use front matter / format without
    changing the stage entrypoint.
    """

    front_matter_blocks: tuple[dict[str, Any], ...]
    content_blocks: tuple[dict[str, Any], ...]
    table_blocks: tuple[dict[str, Any], ...]
    format_blocks: tuple[dict[str, Any], ...]

    @classmethod
    def from_analysis_bundle(cls, bundle: dict[str, Any]) -> BlockUniverse:
        return cls(
            front_matter_blocks=tuple(
                _as_block_list(bundle.get("front_matter_blocks"))
            ),
            content_blocks=tuple(_as_block_list(bundle.get("content_blocks"))),
            table_blocks=tuple(_as_block_list(bundle.get("table_blocks"))),
            format_blocks=tuple(_as_block_list(bundle.get("format_blocks"))),
        )

    @property
    def all_blocks_by_doc_order(self) -> list[dict[str, Any]]:
        combined = list(
            self.front_matter_blocks
            + self.content_blocks
            + self.table_blocks
            + self.format_blocks
        )
        return sorted(combined, key=_block_doc_order_key)

    @property
    def blocks_by_id(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for block in self.all_blocks_by_doc_order:
            block_id = block.get("block_id")
            if block_id:
                out[str(block_id)] = block
        return out
