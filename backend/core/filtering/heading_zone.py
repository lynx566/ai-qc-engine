"""Default heading-anchor zone extraction strategy."""

from __future__ import annotations

from typing import Any

from core.content.boundary import block_analysis_text
from core.document.structure.headings import (
    get_heading_level,
    get_heading_text_for_match,
    is_heading,
    update_heading_stack,
)
from core.filtering.block_universe import BlockUniverse
from core.filtering.strategies import FilterContext, FilterStrategyResult
from core.normalization.matching import match_text

_ZONE_COLLECT_KINDS = frozenset({"paragraph", "list_item", "heading"})


def _export_heading_lineage(
    stack: list[dict[str, Any]],
    *,
    for_public_export: bool,
) -> list[dict[str, Any]]:
    lineage: list[dict[str, Any]] = []
    for heading in stack:
        meta = heading.get("meta") or {}
        analysis_text = block_analysis_text(heading)
        structural_text = get_heading_text_for_match(heading)
        display_text = analysis_text if for_public_export else structural_text
        lineage.append(
            {
                "block_id": heading.get("block_id"),
                "text": display_text,
                "analysis_text": analysis_text,
                "heading_level": meta.get("heading_level"),
                "heading_number": meta.get("heading_number"),
                "heading_text_stripped": meta.get("heading_text_stripped"),
                "loc": heading.get("loc"),
            }
        )
    return lineage


def _collect_nested_matched_headings(
    zone_blocks: list[dict[str, Any]],
    *,
    anchor_block_id: str | None,
    heading_terms: tuple[str, ...],
    match_mode: str,
) -> list[dict[str, Any]]:
    nested: list[dict[str, Any]] = []
    for block in zone_blocks:
        if not is_heading(block):
            continue
        if anchor_block_id is not None and block.get("block_id") == anchor_block_id:
            continue
        heading_text = get_heading_text_for_match(block)
        matched, matched_term = match_text(
            heading_text=heading_text,
            heading_terms=heading_terms,
            match_mode=match_mode,
        )
        if not matched:
            continue
        meta = block.get("meta") or {}
        nested.append(
            {
                "block_id": block.get("block_id"),
                "text": block.get("text"),
                "matched_term": matched_term,
                "heading_text_stripped": meta.get("heading_text_stripped"),
                "heading_level": meta.get("heading_level"),
                "loc": block.get("loc"),
            }
        )
    return nested


def _policy_from_zone_config(zone_config: Any) -> Any:
    """Return executable heading policy from an installed Filter config."""
    policy = getattr(zone_config, "policy", None)
    if policy is None:
        raise ValueError("zone_config.policy is required for heading-zone extraction")
    return policy


def _heading_matches_zone_profile(
    block: dict[str, Any],
    policy: Any,
) -> tuple[bool, str | None, int | None]:
    current_level = get_heading_level(block)
    required_level = getattr(policy, "required_heading_level", None)
    if required_level is not None and current_level != required_level:
        return False, None, current_level

    heading_text = get_heading_text_for_match(block)
    matched, matched_term = match_text(
        heading_text=heading_text,
        heading_terms=policy.heading_terms,
        match_mode=policy.heading_match_mode,
    )
    if not matched:
        return False, None, current_level

    exclude_terms = getattr(policy, "exclude_heading_terms", ())
    if exclude_terms:
        excluded, _ = match_text(
            heading_text=heading_text,
            heading_terms=exclude_terms,
            match_mode=policy.heading_match_mode,
        )
        if excluded:
            return False, None, current_level

    return True, matched_term, current_level


def _block_doc_pos(block: dict[str, Any]) -> int | None:
    value = block.get("doc_order_index")
    if isinstance(value, int):
        return value
    return None


def _heading_stack_at_index(
    content_blocks: list[dict[str, Any]],
    index: int,
) -> list[dict[str, Any]]:
    stack: list[dict[str, Any]] = []
    for position in range(index + 1):
        block = content_blocks[position]
        if is_heading(block):
            stack = update_heading_stack(stack, block)
    return stack


def _materialize_zone_at_heading_index(
    content_blocks: list[dict[str, Any]],
    table_blocks: list[dict[str, Any]],
    index: int,
    zone_config: Any,
    *,
    match_type: str,
    matched_term: str | None,
    match_mode: str,
    zone_id: str,
    nested_matched_headings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one heading-anchor zone at *index* without applying term matching."""
    block = content_blocks[index]
    if not is_heading(block):
        raise ValueError(
            f"content_blocks[{index}] must be a heading block for zone materialization"
        )

    current_level = get_heading_level(block)
    heading_stack = _heading_stack_at_index(content_blocks, index)

    zone_blocks = [block]
    zone_end: int | None = None

    j = index + 1
    while j < len(content_blocks):
        next_block = content_blocks[j]

        if is_heading(next_block):
            next_level = get_heading_level(next_block)

            if (
                current_level is not None
                and next_level is not None
                and next_level <= current_level
            ):
                zone_end = _block_doc_pos(next_block)
                break

        if next_block.get("kind") in _ZONE_COLLECT_KINDS:
            zone_blocks.append(next_block)

        j += 1

    zone_start = _block_doc_pos(block)
    zone_table_blocks = _table_blocks_in_zone_range(
        table_blocks,
        zone_start=zone_start,
        zone_end=zone_end,
    )

    anchor_meta = block.get("meta") or {}
    heading_text = get_heading_text_for_match(block)

    return {
        "zone_id": zone_id,
        "language": zone_config.language,
        "zone_config_name": zone_config.zone_config_name,
        "zone_config_version": zone_config.zone_config_version,
        "match": {
            "match_type": match_type,
            "match_mode": match_mode,
            "matched_term": matched_term,
            "matched_heading_block_id": block.get("block_id"),
            "matched_heading_text": heading_text,
            "matched_heading_text_stripped": anchor_meta.get("heading_text_stripped"),
            "matched_heading_level": current_level,
        },
        "heading_lineage": _export_heading_lineage(
            heading_stack,
            for_public_export=False,
        ),
        "nested_matched_headings": list(nested_matched_headings or ()),
        "blocks": zone_blocks,
        "table_blocks": zone_table_blocks,
    }


def materialize_heading_anchor_zone(
    *,
    anchor_block_id: str,
    content_blocks: list[dict[str, Any]],
    table_blocks: list[dict[str, Any]],
    zone_config: Any,
    match_type: str = "heading",
    matched_term: str | None = None,
    match_mode: str | None = None,
    zone_id: str = "Z0000",
) -> dict[str, Any]:
    """
    Materialize one heading-anchor zone at *anchor_block_id* without term matching.

    Section span follows the same heading-level boundary rules as automatic Filter.
    """
    anchor = str(anchor_block_id or "").strip()
    if not anchor:
        raise ValueError("anchor_block_id is required")

    index: int | None = None
    for position, block in enumerate(content_blocks):
        if str(block.get("block_id") or "") != anchor:
            continue
        if not is_heading(block):
            raise ValueError(f"anchor_block_id {anchor!r} is not a heading block")
        index = position
        break
    if index is None:
        raise ValueError(f"anchor_block_id {anchor!r} not found in content_blocks")

    policy = _policy_from_zone_config(zone_config)
    resolved_match_mode = match_mode or policy.heading_match_mode

    return _materialize_zone_at_heading_index(
        content_blocks,
        table_blocks,
        index,
        zone_config,
        match_type=match_type,
        matched_term=matched_term,
        match_mode=resolved_match_mode,
        zone_id=zone_id,
        nested_matched_headings=[],
    )


def _table_blocks_in_zone_range(
    table_blocks: list[dict[str, Any]],
    *,
    zone_start: int | None,
    zone_end: int | None,
) -> list[dict[str, Any]]:
    if zone_start is None:
        return []

    selected: list[dict[str, Any]] = []
    for table_block in table_blocks:
        pos = _block_doc_pos(table_block)
        if pos is None or pos <= zone_start:
            continue
        if zone_end is not None and pos >= zone_end:
            continue
        selected.append(table_block)

    return sorted(
        selected,
        key=lambda block: (
            _block_doc_pos(block) if _block_doc_pos(block) is not None else 10**9,
            block.get("order") if block.get("order") is not None else 0,
            str(block.get("block_id") or ""),
        ),
    )


def _extract_zones_for_config(
    content_blocks: list[dict[str, Any]],
    table_blocks: list[dict[str, Any]],
    zone_config: Any,
    *,
    zone_index_start: int,
) -> tuple[list[dict[str, Any]], int]:
    matched_zones: list[dict[str, Any]] = []
    heading_stack: list[dict[str, Any]] = []

    i = 0
    zone_index = zone_index_start

    policy = _policy_from_zone_config(zone_config)

    while i < len(content_blocks):
        block = content_blocks[i]

        if not is_heading(block):
            i += 1
            continue

        heading_stack = update_heading_stack(heading_stack, block)

        matched, matched_term, current_level = _heading_matches_zone_profile(
            block, policy
        )
        if not matched:
            i += 1
            continue

        materialized = _materialize_zone_at_heading_index(
            content_blocks,
            table_blocks,
            i,
            zone_config,
            match_type="heading",
            matched_term=matched_term,
            match_mode=policy.heading_match_mode,
            zone_id=f"Z{zone_index:04d}",
            nested_matched_headings=[],
        )
        materialized["nested_matched_headings"] = _collect_nested_matched_headings(
            materialized["blocks"],
            anchor_block_id=block.get("block_id"),
            heading_terms=policy.heading_terms,
            match_mode=policy.heading_match_mode,
        )
        matched_zones.append(materialized)

        j = i + 1
        while j < len(content_blocks):
            next_block = content_blocks[j]
            if is_heading(next_block):
                next_level = get_heading_level(next_block)
                if (
                    current_level is not None
                    and next_level is not None
                    and next_level <= current_level
                ):
                    break
            j += 1

        zone_index += 1
        i = j

    return matched_zones, zone_index


def _selected_block_ids_from_zones(
    matched_zones: list[dict[str, Any]],
) -> frozenset[str]:
    selected: set[str] = set()
    for zone in matched_zones:
        for group_key in ("blocks", "table_blocks"):
            for block in zone.get(group_key) or []:
                block_id = block.get("block_id")
                if block_id:
                    selected.add(str(block_id))
    return frozenset(selected)


class HeadingZoneStrategy:
    """Heading-anchor zone extraction (default filter strategy)."""

    strategy_id = "heading_zone"

    def extract(
        self,
        *,
        block_universe: BlockUniverse,
        zone_config: Any,
        context: FilterContext,
    ) -> FilterStrategyResult:
        content_blocks = list(block_universe.content_blocks)
        table_blocks = list(block_universe.table_blocks)

        matched_zones, next_zone_index = _extract_zones_for_config(
            content_blocks,
            table_blocks,
            zone_config,
            zone_index_start=context.zone_index_start,
        )

        return FilterStrategyResult(
            matched_zones=matched_zones,
            selected_block_ids=_selected_block_ids_from_zones(matched_zones),
            next_zone_index=next_zone_index,
            diagnostics={
                "strategy_id": self.strategy_id,
                "scanned_groups": ("content_blocks", "table_blocks"),
            },
        )


HEADING_ZONE_STRATEGY = HeadingZoneStrategy()

__all__ = [
    "HEADING_ZONE_STRATEGY",
    "HeadingZoneStrategy",
    "materialize_heading_anchor_zone",
]
