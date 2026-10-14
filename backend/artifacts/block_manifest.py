"""
Build block_manifest artifact view from prepare_analysis ``analysis_bundle``.

Artifact builder only — not a pipeline stage. No zone matching or filter logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.document.doc_identity import require_bundle_file_hash
from core.document.structure.analysis_heading_projection import (
    AnalysisHeadingProjection,
)

BLOCK_MANIFEST_FILENAME = "block_manifest.json"

_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "normalized_text",
        "span_map",
        "source_ref",
        "document_meta",
        "privacy_transforms",
        "sentences",
        "raw_rows",
        "raw_text_before_normalize",
        "raw_text",
        "table_ref_candidates",
    }
)

_CONTENT_BLOCK_META_ALLOWLIST = frozenset(
    {
        "heading_level",
        "heading_number",
    }
)

_TABLE_BLOCK_META_ALLOWLIST = frozenset(
    {
        "row_count",
        "column_count",
        "non_empty_row_count",
    }
)

_TABLE_BLOCK_ROW_PAYLOAD_KEYS = ("analysis_rows", "masked_rows")


def _sorted_content_blocks(analysis_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = analysis_bundle.get("content_blocks") or []
    return sorted(
        (b for b in blocks if isinstance(b, dict)),
        key=lambda b: (b.get("order") if b.get("order") is not None else 0, str(b.get("block_id") or "")),
    )


def _sorted_table_blocks(analysis_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = analysis_bundle.get("table_blocks") or []
    return sorted(
        (b for b in blocks if isinstance(b, dict)),
        key=lambda b: (
            b.get("doc_order_index")
            if b.get("doc_order_index") is not None
            else 10**9,
            b.get("order") if b.get("order") is not None else 0,
            str(b.get("block_id") or ""),
        ),
    )


def _block_to_manifest_entry(
    block: dict[str, Any],
    *,
    analysis_bundle_id: str,
    heading_path: list[str],
) -> dict[str, Any]:
    meta = block.get("meta") or {}
    block_id = str(block.get("block_id") or "")
    out_meta = {
        key: meta.get(key)
        for key in _CONTENT_BLOCK_META_ALLOWLIST
        if meta.get(key) is not None
    }
    entry: dict[str, Any] = {
        "block_id": block_id,
        "kind": block.get("kind"),
        "order": block.get("order"),
        "heading_path": heading_path,
        "heading_level": out_meta.get("heading_level"),
        "heading_number": out_meta.get("heading_number"),
        "analysis_text": str(block.get("analysis_text") or ""),
        "text_ref": {
            "analysis_bundle_id": analysis_bundle_id,
            "block_id": block_id,
        },
    }
    return entry


def _table_block_to_manifest_entry(
    block: dict[str, Any],
    *,
    analysis_bundle_id: str,
    heading_path: list[str],
) -> dict[str, Any]:
    meta = block.get("meta") or {}
    block_id = str(block.get("block_id") or "")
    table_meta: dict[str, Any] = {
        key: meta.get(key)
        for key in _TABLE_BLOCK_META_ALLOWLIST
        if meta.get(key) is not None
    }
    # Preserve masked table rows only when explicitly present; never copy raw_rows.
    for key in _TABLE_BLOCK_ROW_PAYLOAD_KEYS:
        rows = meta.get(key)
        if isinstance(rows, list):
            table_meta[key] = rows
    return {
        "block_id": block_id,
        "kind": block.get("kind"),
        "text": str(block.get("analysis_text") or block.get("text") or ""),
        "doc_order_index": block.get("doc_order_index"),
        "heading_path": heading_path,
        "meta": table_meta,
        "text_ref": {
            "analysis_bundle_id": analysis_bundle_id,
            "block_id": block_id,
        },
    }


def build_block_manifest_id(*, analysis_bundle_id: str) -> str:
    return f"block_manifest_{analysis_bundle_id}"


def build_block_manifest(
    analysis_bundle: dict[str, Any],
    *,
    heading_projection: AnalysisHeadingProjection,
) -> dict[str, Any]:
    """
    Convert ``analysis_bundle`` to the block_manifest artifact contract.

    Uses ``analysis_text`` for content blocks and ``text`` for table blocks;
    does not copy normalized text, span maps, source refs, sentence payloads,
    or raw table rows.
    Table blocks are sorted by ``doc_order_index``. Heading paths must already
    have been projected from semantic values by the caller.
    """
    analysis_bundle_id = analysis_bundle.get("analysis_bundle_id")
    if not isinstance(analysis_bundle_id, str) or not analysis_bundle_id.strip():
        raise ValueError("analysis_bundle.analysis_bundle_id is required")

    doc_id = analysis_bundle.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError("analysis_bundle.doc_id is required")

    content_blocks = _sorted_content_blocks(analysis_bundle)
    sorted_table_blocks = _sorted_table_blocks(analysis_bundle)
    blocks = [
        _block_to_manifest_entry(
            block,
            analysis_bundle_id=analysis_bundle_id,
            heading_path=list(
                heading_projection.content.get(str(block.get("block_id") or ""), ())
            ),
        )
        for block in content_blocks
    ]

    table_blocks = [
        _table_block_to_manifest_entry(
            block,
            analysis_bundle_id=analysis_bundle_id,
            heading_path=list(
                heading_projection.tables.get(str(block.get("block_id") or ""), ())
            ),
        )
        for block in sorted_table_blocks
    ]

    manifest = {
        "block_manifest_id": build_block_manifest_id(
            analysis_bundle_id=analysis_bundle_id,
        ),
        "doc_id": doc_id,
        "file_hash": require_bundle_file_hash(
            analysis_bundle,
            label="analysis_bundle",
        ),
        "analysis_bundle_ref": {
            "analysis_bundle_id": analysis_bundle_id,
        },
        "blocks": blocks,
        "table_blocks": table_blocks,
    }
    _validate_block_manifest_blocks(manifest)
    return manifest


def _validate_block_manifest_blocks(payload: Mapping[str, Any]) -> None:
    """Validate ``block_manifest.blocks`` is a list of objects."""

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("block_manifest.blocks must be a list")
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise ValueError(f"block_manifest.blocks[{index}] must be an object")


def assert_block_manifest_safe(payload: dict[str, Any]) -> None:
    """Raise ``ValueError`` if *payload* contains forbidden analysis fields."""

    def _walk(value: Any, *, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _FORBIDDEN_OUTPUT_KEYS:
                    raise ValueError(f"forbidden key {key!r} at {path}")
                _walk(item, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, path=f"{path}[{index}]")

    _walk(payload, path="block_manifest")
    _validate_block_manifest_blocks(payload)
