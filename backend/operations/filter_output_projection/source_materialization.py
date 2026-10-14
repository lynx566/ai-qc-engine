"""In-memory Projection source materialization from Filter + Prepare inputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.document.block_position import analysis_blocks_by_id
from operations.filter_output_projection.contracts import (
    ProjectionSourceBlock,
    ProjectionSourceSentence,
)

_SOURCE_GROUPS = ("blocks", "table_blocks")


def _block_kind(block: Mapping[str, Any], *, source_group: str) -> str:
    kind = block.get("kind")
    if isinstance(kind, str) and kind.strip():
        return kind.strip()
    if source_group == "table_blocks":
        return "table"
    return "paragraph"


def _heading_path_from_block(block: Mapping[str, Any]) -> tuple[str, ...]:
    heading_path = block.get("heading_path")
    if not isinstance(heading_path, list):
        return ()
    return tuple(str(item) for item in heading_path)


def _iter_selected_zone_blocks(
    zone_match_bundle: Mapping[str, Any],
) -> list[tuple[str, str, Mapping[str, Any]]]:
    """Yield (zone_id, source_group, block) in Filter-selected order."""
    matched_zones = zone_match_bundle.get("matched_zones") or []
    if not isinstance(matched_zones, list):
        raise TypeError("zone_match_bundle.matched_zones must be a list")

    seen_block_ids: set[str] = set()
    ordered: list[tuple[str, str, Mapping[str, Any]]] = []
    for zone in matched_zones:
        if not isinstance(zone, dict):
            continue
        zone_id = str(zone.get("zone_id") or "").strip()
        if not zone_id:
            raise ValueError("matched zone must include zone_id")
        for source_group in _SOURCE_GROUPS:
            blocks = zone.get(source_group) or []
            if not isinstance(blocks, list):
                raise TypeError(
                    f"matched zone {source_group!r} must be a list when present"
                )
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_id = str(block.get("block_id") or "").strip()
                if not block_id or block_id in seen_block_ids:
                    continue
                seen_block_ids.add(block_id)
                ordered.append((zone_id, source_group, block))
    return ordered


def _materialize_sentences(
    analysis_block: Mapping[str, Any],
    *,
    block_id: str,
) -> tuple[ProjectionSourceSentence, ...]:
    raw_sentences = analysis_block.get("sentences")
    if raw_sentences is None:
        return ()
    if not isinstance(raw_sentences, list):
        raise TypeError(
            f"analysis_bundle block {block_id!r} sentences must be a list when present"
        )
    materialized: list[ProjectionSourceSentence] = []
    for index, sentence in enumerate(raw_sentences):
        if not isinstance(sentence, Mapping):
            raise TypeError(
                f"analysis_bundle block {block_id!r} sentences[{index}] must be a mapping"
            )
        sentence_id = sentence.get("sentence_id")
        if not isinstance(sentence_id, str) or not sentence_id.strip():
            raise ValueError(
                f"analysis_bundle block {block_id!r} sentences[{index}].sentence_id "
                "is required"
            )
        analysis_text = sentence.get("analysis_text")
        if not isinstance(analysis_text, str):
            raise TypeError(
                f"analysis_bundle block {block_id!r} sentences[{index}].analysis_text "
                "must be a string"
            )
        materialized.append(
            ProjectionSourceSentence(
                sentence_id=sentence_id,
                text=analysis_text,
            )
        )
    return tuple(materialized)


def materialize_projection_sources(
    *,
    zone_match_bundle: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
) -> tuple[ProjectionSourceBlock, ...]:
    """Join Filter-selected blocks with canonical Prepare analysis payloads."""
    analysis_by_id = analysis_blocks_by_id(analysis_bundle)
    materialized: list[ProjectionSourceBlock] = []
    for zone_id, source_group, zone_block in _iter_selected_zone_blocks(
        zone_match_bundle
    ):
        block_id = str(zone_block.get("block_id") or "").strip()
        analysis_block = analysis_by_id.get(block_id)
        if analysis_block is None:
            raise ValueError(
                f"selected block_id {block_id!r} not found in analysis_bundle"
            )
        analysis_text = analysis_block.get("analysis_text")
        if not isinstance(analysis_text, str):
            raise TypeError(
                f"analysis_bundle block {block_id!r}.analysis_text must be a string"
            )
        materialized.append(
            ProjectionSourceBlock(
                block_id=block_id,
                kind=_block_kind(zone_block, source_group=source_group),
                heading_path=_heading_path_from_block(zone_block),
                source_group=source_group,
                zone_id=zone_id,
                text=analysis_text,
                sentences=_materialize_sentences(
                    analysis_block,
                    block_id=block_id,
                ),
            )
        )
    return tuple(materialized)


__all__ = ["materialize_projection_sources"]
