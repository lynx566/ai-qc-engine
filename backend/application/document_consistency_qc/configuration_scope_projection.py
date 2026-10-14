"""Deterministic configuration scope display from canonical Extract headings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from application.document_consistency_qc.document_read import (
    DocumentReadValidationError,
)
from core.document.structure.headings import is_heading


def project_configuration_scope_items(
    extract_bundle: Mapping[str, Any],
    anchor_block_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Map persisted selection anchors to report-readable heading paths.

    Order matches ``anchor_block_ids``. Heading paths and document order come from the canonical
    Extract bundle (same source as canonical source projection).
    """

    blocks = extract_bundle.get("content_blocks")
    if not isinstance(blocks, list):
        raise DocumentReadValidationError("Extract bundle missing content_blocks")
    index: dict[str, Mapping[str, Any]] = {}
    for block in blocks:
        if not isinstance(block, Mapping):
            raise DocumentReadValidationError("invalid Extract content block")
        block_id = block.get("block_id")
        if not isinstance(block_id, str) or not block_id.strip():
            raise DocumentReadValidationError("Extract block missing block_id")
        if block_id in index:
            raise DocumentReadValidationError(
                f"duplicate Extract block_id {block_id!r}"
            )
        index[block_id] = block

    items: list[dict[str, Any]] = []
    for anchor_id in anchor_block_ids:
        block = index.get(anchor_id)
        if block is None:
            raise DocumentReadValidationError(
                f"selection anchor {anchor_id!r} is absent from canonical Extract"
            )
        if not is_heading(dict(block)):
            raise DocumentReadValidationError(
                f"selection anchor {anchor_id!r} is not a canonical heading block"
            )
        path = block.get("heading_path", [])
        if not isinstance(path, list) or not path:
            raise DocumentReadValidationError(
                f"selection anchor {anchor_id!r} has no heading_path"
            )
        heading_path = []
        for part in path:
            if not isinstance(part, str) or not part.strip():
                raise DocumentReadValidationError(
                    f"selection anchor {anchor_id!r} has invalid heading_path"
                )
            heading_path.append(part)
        order = block.get("doc_order_index")
        if isinstance(order, bool) or not isinstance(order, int) or order < 0:
            raise DocumentReadValidationError(
                f"selection anchor {anchor_id!r} missing canonical document order"
            )
        items.append(
            {
                "anchor_block_id": anchor_id,
                "heading_path": heading_path,
                "doc_order_index": order,
            }
        )
    return items


def project_configuration_selection_scope_display(
    extract_bundle: Mapping[str, Any],
    *,
    automatic_anchor_block_ids: Sequence[str],
    effective_anchor_block_ids: Sequence[str],
    added_anchor_block_ids: Sequence[str],
    removed_anchor_block_ids: Sequence[str],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "automatic_scope_items": project_configuration_scope_items(
            extract_bundle, automatic_anchor_block_ids
        ),
        "effective_scope_items": project_configuration_scope_items(
            extract_bundle, effective_anchor_block_ids
        ),
        "added_scope_items": project_configuration_scope_items(
            extract_bundle, added_anchor_block_ids
        ),
        "removed_scope_items": project_configuration_scope_items(
            extract_bundle, removed_anchor_block_ids
        ),
    }


__all__ = [
    "project_configuration_scope_items",
    "project_configuration_selection_scope_display",
]
