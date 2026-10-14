"""Clinical trial document route processor: unit assembly and route fan-out."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from artifacts.routing.types import ROUTES, Route
from core.document.block_position import (
    block_kind_value as _block_kind_value,
    block_position_key as _block_position_key,
    blocks_by_id as _blocks_by_id,
)
from plugins.clinical_trial_doc.routing.inference import (
    RouteDecision,
    infer_route_from_heading,
    is_text_candidate_kind,
    is_text_unit_assembly_kind,
)
from artifacts.routing.primary_sentence_contract import build_text_unit_sentences
from plugins.clinical_trial_doc.routing.projected_sentence_index import (
    ProjectedSentencesByBlockId,
    routed_primary_sentence_from_projected,
)

_ROUTE_UNIT_ID_PREFIX: dict[Route, str] = {
    "aggregate": "TU",
    "table": "TTU",
    "case": "CU",
    "unknown": "UU",
}

_TABLE_BLOCK_KIND = "table"


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _row_block_kind(row: dict[str, Any]) -> str:
    return str(row.get("block_kind") or row.get("kind") or "paragraph")


def _row_source_stage(row: dict[str, Any]) -> str | None:
    token = str(row.get("source_stage") or "").strip()
    return token or None


def _row_source_zone_key(row: dict[str, Any]) -> str | None:
    token = row.get("source_zone_key")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _row_filter_job_id(row: dict[str, Any]) -> str | None:
    token = row.get("filter_job_id")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _contributor_fields_from_rows(rows: list[dict[str, Any]]) -> dict[str, str]:
    source_zone_key: str | None = None
    filter_job_id: str | None = None
    for row in rows:
        if _row_block_kind(row) == "heading":
            continue
        row_zone = _row_source_zone_key(row)
        if row_zone is not None:
            if source_zone_key is not None and source_zone_key != row_zone:
                block_id = row.get("block_id", "<unknown>")
                raise ValueError(
                    "conflicting source_zone_key within one routed unit near block "
                    f"{block_id!r}"
                )
            source_zone_key = row_zone
        row_filter_job = _row_filter_job_id(row)
        if row_filter_job is not None:
            if filter_job_id is not None and filter_job_id != row_filter_job:
                block_id = row.get("block_id", "<unknown>")
                raise ValueError(
                    "conflicting filter_job_id within one routed unit near block "
                    f"{block_id!r}"
                )
            filter_job_id = row_filter_job
    fields: dict[str, str] = {}
    if source_zone_key is not None:
        fields["source_zone_key"] = source_zone_key
    if filter_job_id is not None:
        fields["filter_job_id"] = filter_job_id
    return fields


def _source_stage_from_rows(rows: list[dict[str, Any]], *, fallback: str) -> str:
    for row in rows:
        source_stage = _row_source_stage(row)
        if source_stage:
            return source_stage
    return fallback


def get_zone_id(row: dict[str, Any]) -> str | None:
    zone_match = row.get("zone_match")
    if not isinstance(zone_match, dict):
        return None
    zone_id = zone_match.get("zone_id")
    if zone_id is None:
        return None
    return str(zone_id)


def _sorted_selected_routing_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("selected_by_filter") is True
    ]
    return sorted(
        selected,
        key=lambda row: (
            row.get("doc_order_index")
            if row.get("doc_order_index") is not None
            else 10**9,
            row.get("order") if row.get("order") is not None else 0,
            str(row.get("block_id") or ""),
        ),
    )


def _heading_path_tuple(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in (row.get("heading_path") or []))


def _route_decision_for_row(
    row: dict[str, Any],
    *,
    zone_key: str | None = None,
) -> RouteDecision:
    return infer_route_from_heading(
        heading_path=_heading_path_tuple(row),
        block_kind=_row_block_kind(row),
        zone_key=zone_key,
    )


def _grouping_route_for_row(
    row: dict[str, Any],
    *,
    zone_key: str | None = None,
) -> Route | None:
    block_kind = _row_block_kind(row)
    if block_kind == "heading":
        return None
    if not is_text_candidate_kind(block_kind):
        return None
    return _route_decision_for_row(row, zone_key=zone_key).route


def _is_heading_context_for_candidate(
    heading_row: dict[str, Any],
    candidate_row: dict[str, Any],
) -> bool:
    heading_path = [str(item) for item in (heading_row.get("heading_path") or [])]
    candidate_path = [str(item) for item in (candidate_row.get("heading_path") or [])]
    if not heading_path or not candidate_path:
        return False
    return candidate_path[: len(heading_path)] == heading_path


def _valid_pending_heading_rows_for_candidate(
    pending_heading_rows: list[dict[str, Any]],
    candidate_row: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        row
        for row in pending_heading_rows
        if _is_heading_context_for_candidate(row, candidate_row)
    ]


def _apply_heading_to_active_stack(
    active_heading_rows: list[dict[str, Any]],
    heading_row: dict[str, Any],
) -> None:
    """Keep strict ancestors and replace same-depth / deeper scopes on heading change."""
    heading_path = _heading_path_tuple(heading_row)
    if not heading_path:
        return
    depth = len(heading_path)
    ancestors = [
        row
        for row in active_heading_rows
        if (row_path := _heading_path_tuple(row))
        and len(row_path) < depth
        and heading_path[: len(row_path)] == row_path
    ]
    active_heading_rows[:] = [*ancestors, heading_row]


def _uses_paragraph_first_text_units(route: Route | None) -> bool:
    """Only coverage-origin aggregate text adopts paragraph-first in PR1."""
    return route == "aggregate"


def _can_merge_preexisting_text_route_rows(
    last_candidate_row: dict[str, Any],
    candidate_row: dict[str, Any],
) -> bool:
    prev_order = last_candidate_row.get("order")
    cur_order = candidate_row.get("order")
    order_continuous = (
        prev_order is not None
        and cur_order is not None
        and cur_order == prev_order + 1
    )
    same_zone = get_zone_id(last_candidate_row) == get_zone_id(candidate_row)
    return order_continuous and same_zone


def _group_text_rows_into_units(
    selected_rows: list[dict[str, Any]],
    *,
    consumed_block_ids: set[str],
    zone_key: str | None = None,
) -> list[list[dict[str, Any]]]:
    # Only coverage-origin aggregate text adopts paragraph-first in PR1.
    # Case and table-like text retain pre-existing grouping behavior pending
    # route-specific decomposition design.
    eligible = [
        row
        for row in selected_rows
        if str(row.get("block_id") or "") not in consumed_block_ids
        and is_text_unit_assembly_kind(_row_block_kind(row))
    ]
    if not eligible:
        return []

    groups: list[list[dict[str, Any]]] = []
    active_heading_rows: list[dict[str, Any]] = []
    current_group: list[dict[str, Any]] = []
    current_group_route: Route | None = None
    last_candidate_row: dict[str, Any] | None = None

    def _flush_current_group() -> None:
        if current_group and any(
            is_text_candidate_kind(_row_block_kind(candidate_row))
            for candidate_row in current_group
        ):
            groups.append(list(current_group))

    def _start_merge_group(candidate_row: dict[str, Any], route: Route) -> None:
        nonlocal current_group, current_group_route, last_candidate_row
        current_group = [
            *_valid_pending_heading_rows_for_candidate(
                active_heading_rows,
                candidate_row,
            ),
            candidate_row,
        ]
        current_group_route = route
        last_candidate_row = candidate_row

    for row in eligible:
        block_kind = _row_block_kind(row)
        if block_kind == "heading":
            if last_candidate_row is not None:
                _flush_current_group()
                current_group = []
                current_group_route = None
                last_candidate_row = None
            _apply_heading_to_active_stack(active_heading_rows, row)
            continue

        if not is_text_candidate_kind(block_kind):
            continue

        cur_route = _grouping_route_for_row(row, zone_key=zone_key)
        if cur_route is None:
            continue

        if _uses_paragraph_first_text_units(cur_route):
            if last_candidate_row is not None:
                _flush_current_group()
                current_group = []
                current_group_route = None
                last_candidate_row = None
            context_rows = _valid_pending_heading_rows_for_candidate(
                active_heading_rows,
                row,
            )
            groups.append([*context_rows, row])
            continue

        if not current_group:
            _start_merge_group(row, cur_route)
            continue

        if (
            last_candidate_row is not None
            and current_group_route == cur_route
            and _can_merge_preexisting_text_route_rows(last_candidate_row, row)
        ):
            current_group.append(row)
            last_candidate_row = row
            continue

        _flush_current_group()
        _start_merge_group(row, cur_route)

    _flush_current_group()
    return groups


def _candidate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows if is_text_candidate_kind(_row_block_kind(row))
    ]


def _context_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _row_block_kind(row) == "heading"]


def _heading_path_for_unit(rows: list[dict[str, Any]]) -> list[str]:
    candidate_rows = _candidate_rows(rows)
    path_rows = candidate_rows or rows
    paths = [
        [str(item) for item in (row.get("heading_path") or [])]
        for row in path_rows
        if (row.get("heading_path") or [])
    ]
    if not paths:
        return []
    prefix = paths[0]
    for path in paths[1:]:
        length = sum(1 for a, b in zip(prefix, path) if a == b)
        prefix = prefix[:length]
        if not prefix:
            break
    return prefix


def _heading_path_for_source_block(
    row: dict[str, Any],
    *,
    block: dict[str, Any] | None,
) -> list[str]:
    row_path = row.get("heading_path")
    if row_path:
        return [str(item) for item in row_path]
    if block is not None:
        block_path = block.get("heading_path")
        if block_path:
            return [str(item) for item in block_path]
    return []


def _block_analysis_text(
    block_id: str,
    *,
    blocks_by_id: dict[str, dict[str, Any]],
) -> str:
    block = blocks_by_id.get(block_id)
    if block is None:
        return ""
    analysis_text = str(block.get("analysis_text") or "").strip()
    if analysis_text:
        return analysis_text
    block_kind = str(block.get("kind") or block.get("block_kind") or "").strip().lower()
    if block_kind == "table":
        return str(block.get("text") or "").strip()
    return ""


def _build_primary_sentences(
    rows: list[dict[str, Any]],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
    projected_sentences_by_block_id: ProjectedSentencesByBlockId,
) -> list[dict[str, Any]]:
    primary_sentences: list[dict[str, Any]] = []
    for row in rows:
        block_id = str(row.get("block_id") or "")
        block = blocks_by_id.get(block_id)
        if block is None:
            continue
        block_kind = _row_block_kind(row)
        if block_kind == "heading":
            continue
        if not is_text_candidate_kind(block_kind):
            continue
        projected_sentences = projected_sentences_by_block_id.get(block_id)
        if projected_sentences is None:
            raise ValueError(
                f"projected text-candidate block {block_id!r} is missing from "
                "projected sentence index"
            )
        for sentence in projected_sentences:
            primary_sentences.append(routed_primary_sentence_from_projected(sentence))
    return primary_sentences


def _unit_route_metadata(
    rows: list[dict[str, Any]],
    *,
    zone_key: str | None = None,
) -> RouteDecision:
    text_rows = _candidate_rows(rows)
    if not text_rows:
        return RouteDecision(
            route="unknown",
            route_basis="no_text_candidate_rows",
            route_matched_terms=(),
        )
    decisions = [
        _route_decision_for_row(row, zone_key=zone_key) for row in text_rows
    ]
    routes = {decision.route for decision in decisions}
    if len(routes) != 1:
        route_block_map: dict[str, list[str]] = {}
        for row, decision in zip(text_rows, decisions):
            route_block_map.setdefault(decision.route, []).append(
                str(row.get("block_id") or "")
            )
        detail = "; ".join(
            f"{route}: {', '.join(block_ids)}"
            for route, block_ids in sorted(route_block_map.items())
        )
        raise ValueError(
            f"text unit spans multiple routes: {sorted(routes)!r}; {detail}"
        )
    primary = decisions[0]
    matched: list[str] = []
    for decision in decisions:
        for term in decision.route_matched_terms:
            if term not in matched:
                matched.append(term)
    if matched:
        return RouteDecision(
            route=primary.route,
            route_basis="route_matched_terms",
            route_matched_terms=tuple(matched),
        )
    return RouteDecision(
        route=primary.route,
        route_basis=primary.route_basis,
        route_matched_terms=(),
    )


def _candidate_block_kinds(rows: list[dict[str, Any]]) -> list[str]:
    return [_row_block_kind(row) for row in _candidate_rows(rows)]


def _unit_source_block_fields(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_rows = _candidate_rows(rows)
    context_rows = _context_rows(rows)
    return {
        "source_block_ids": [
            str(row.get("block_id") or "") for row in candidate_rows
        ],
        "context_block_ids": [
            str(row.get("block_id") or "") for row in context_rows
        ],
        "all_source_block_ids": [
            str(row.get("block_id") or "") for row in rows
        ],
        "candidate_block_kinds": _candidate_block_kinds(rows),
    }


def _build_text_unit(
    rows: list[dict[str, Any]],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
    projected_sentences_by_block_id: ProjectedSentencesByBlockId,
    zone_key: str | None = None,
) -> dict[str, Any]:
    route_meta = _unit_route_metadata(rows, zone_key=zone_key)
    block_fields = _unit_source_block_fields(rows)
    text_refs = [dict(row.get("text_ref") or {}) for row in rows]
    primary_sentences = _build_primary_sentences(
        rows,
        blocks_by_id=blocks_by_id,
        projected_sentences_by_block_id=projected_sentences_by_block_id,
    )
    source_stage = _source_stage_from_rows(rows, fallback="filter")
    heading_path = _heading_path_for_unit(rows)
    body_fields = {"sentences": build_text_unit_sentences(primary_sentences)}
    contributor_fields = _contributor_fields_from_rows(rows)
    resolved_zone_key = contributor_fields.get("source_zone_key") or (
        str(zone_key) if zone_key is not None else None
    )
    unit: dict[str, Any] = {
        "unit_kind": "text_unit",
        "route": route_meta.route,
        "route_basis": route_meta.route_basis,
        "route_matched_terms": list(route_meta.route_matched_terms),
        "heading_path": heading_path,
        **body_fields,
        **block_fields,
        "text_refs": text_refs,
        "source_stage": source_stage,
        "source_zone_key": resolved_zone_key,
    }
    if "filter_job_id" in contributor_fields:
        unit["filter_job_id"] = contributor_fields["filter_job_id"]
    return unit


def _manifest_blocks_list(block_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for group_key in ("blocks", "table_blocks"):
        for block in block_manifest.get(group_key) or []:
            if isinstance(block, dict):
                blocks.append(block)
    return blocks


def _share_heading_context(
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> bool:
    if not left or not right:
        return False
    shared = sum(1 for a, b in zip(left, right) if a == b)
    return shared >= min(len(left), len(right))


def _heading_level_of_block(block: dict[str, Any]) -> int | None:
    """Return the heading level stored on the block, or infer from heading_path depth."""
    level = block.get("heading_level")
    if isinstance(level, int):
        return level
    return None


def _table_heading_depth(table_block: dict[str, Any]) -> int:
    """The depth of the heading subtree the table belongs to (1-based path length)."""
    path = table_block.get("heading_path") or []
    return len(path)


def _blocks_sorted_by_position(block_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """All blocks from block_manifest sorted by document position."""
    blocks = _manifest_blocks_list(block_manifest)
    return sorted(blocks, key=_block_position_key)


def _intervening_heading_blocks(
    from_key: tuple[int, int, int],
    to_key: tuple[int, int, int],
    *,
    sorted_blocks: list[dict[str, Any]],
    table_heading_depth: int,
) -> bool:
    """
    Return True if there is a heading between *from_key* and *to_key* that would
    break the caption/note → table association.

    A "breaking heading" is any heading whose path depth is <= the depth of the
    table's own heading path (i.e. it is a sibling or ancestor heading, meaning
    it starts a new section at the same or higher level).
    """
    lo, hi = (from_key, to_key) if from_key < to_key else (to_key, from_key)
    for block in sorted_blocks:
        bk = _block_position_key(block)
        if bk <= lo:
            continue
        if bk >= hi:
            break
        if _block_kind_value(block) != "heading":
            continue
        block_path_depth = len(block.get("heading_path") or [])
        # A heading that is at the same depth or shallower than the table's
        # heading path separates sections → caption/note should not cross it.
        if block_path_depth <= table_heading_depth:
            return True
    return False


def _pseudo_row_from_block(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "block_id": block.get("block_id"),
        "block_kind": _block_kind_value(block),
        "heading_path": block.get("heading_path"),
        "order": block.get("order"),
        "doc_order_index": block.get("doc_order_index"),
    }


def _find_caption_block_for_table(
    table_block: dict[str, Any],
    *,
    block_manifest: dict[str, Any],
    consumed_block_ids: set[str] | None = None,
    sorted_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    skip_ids = consumed_block_ids or set()
    table_key = _block_position_key(table_block)
    table_heading = tuple(str(item) for item in (table_block.get("heading_path") or []))
    table_depth = _table_heading_depth(table_block)
    _sorted = sorted_blocks if sorted_blocks is not None else _blocks_sorted_by_position(block_manifest)
    best: dict[str, Any] | None = None
    best_key: tuple[int, int, int] | None = None
    for block in _sorted:
        block_id = str(block.get("block_id") or "")
        if not block_id or block_id in skip_ids:
            continue
        if _block_kind_value(block) != "table_caption":
            continue
        block_heading = tuple(str(item) for item in (block.get("heading_path") or []))
        if not _share_heading_context(table_heading, block_heading):
            continue
        block_key = _block_position_key(block)
        if block_key >= table_key:
            continue
        # Reject if a section-breaking heading intervenes between this candidate
        # and the table.
        if _intervening_heading_blocks(
            block_key,
            table_key,
            sorted_blocks=_sorted,
            table_heading_depth=table_depth,
        ):
            continue
        if best_key is None or block_key > best_key:
            best = block
            best_key = block_key
    return best


def _find_note_block_for_table(
    table_block: dict[str, Any],
    *,
    block_manifest: dict[str, Any],
    consumed_block_ids: set[str] | None = None,
    sorted_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    skip_ids = consumed_block_ids or set()
    table_key = _block_position_key(table_block)
    table_heading = tuple(str(item) for item in (table_block.get("heading_path") or []))
    table_depth = _table_heading_depth(table_block)
    _sorted = sorted_blocks if sorted_blocks is not None else _blocks_sorted_by_position(block_manifest)
    best: dict[str, Any] | None = None
    best_key: tuple[int, int, int] | None = None
    for block in _sorted:
        block_id = str(block.get("block_id") or "")
        if not block_id or block_id in skip_ids:
            continue
        if _block_kind_value(block) != "table_note":
            continue
        block_heading = tuple(str(item) for item in (block.get("heading_path") or []))
        if not _share_heading_context(table_heading, block_heading):
            continue
        block_key = _block_position_key(block)
        if block_key <= table_key:
            continue
        # Reject if a section-breaking heading intervenes between the table
        # and this candidate note.
        if _intervening_heading_blocks(
            table_key,
            block_key,
            sorted_blocks=_sorted,
            table_heading_depth=table_depth,
        ):
            continue
        if best_key is None or block_key < best_key:
            best = block
            best_key = block_key
    return best


def _component_for_row(
    row: dict[str, Any],
    *,
    component_role: str,
    blocks_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    block_id = str(row.get("block_id") or "")
    block_kind = _row_block_kind(row)
    component: dict[str, Any] = {
        "ref_id": block_id,
        "block_kind": block_kind,
        "component_role": component_role,
    }
    text = _block_analysis_text(block_id, blocks_by_id=blocks_by_id)
    if text:
        component["text"] = text
    return component


def _table_shape_from_meta(meta: dict[str, Any], raw_rows: list | None) -> dict[str, Any]:
    row_count = meta.get("row_count")
    column_count = meta.get("column_count")
    if row_count is None and isinstance(raw_rows, list) and raw_rows:
        row_count = len(raw_rows)
    if column_count is None and isinstance(raw_rows, list) and raw_rows:
        column_count = max(
            (len(row) for row in raw_rows if isinstance(row, list)),
            default=0,
        )
    return {
        "row_count": row_count,
        "column_count": column_count,
    }


def _table_body_component(
    table_row: dict[str, Any],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    table_block_id = str(table_row.get("block_id") or "")
    table_block = blocks_by_id.get(table_block_id) or {}
    meta = table_block.get("meta") or {}
    raw_rows = meta.get("raw_rows")
    has_raw_rows = isinstance(raw_rows, list) and len(raw_rows) > 0
    component: dict[str, Any] = {
        "ref_id": table_block_id,
        "block_kind": _row_block_kind(table_row),
        "component_role": "table_body",
        "structured_rows_available": has_raw_rows,
        "table_shape": _table_shape_from_meta(meta, raw_rows if has_raw_rows else None),
        "header_rows": list(meta.get("header_rows") or []),
        "rows": list(raw_rows) if has_raw_rows else [],
    }
    text = _block_analysis_text(table_block_id, blocks_by_id=blocks_by_id)
    if text:
        component["text"] = text
    return component


def _component_status_from_components(components: list[dict[str, Any]]) -> dict[str, bool]:
    roles = {str(component.get("component_role") or "") for component in components}
    return {
        "has_caption": "caption" in roles,
        "has_note": "note" in roles,
    }


def _all_source_refs_from_components(
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for component in components:
        ref_id = str(component.get("ref_id") or "")
        if not ref_id:
            continue
        block_kind = str(component.get("block_kind") or "")
        if block_kind == "table":
            refs.append({"ref_type": "table", "ref_id": ref_id})
        else:
            entry: dict[str, Any] = {"ref_type": "block", "ref_id": ref_id}
            if block_kind:
                entry["block_kind"] = block_kind
            refs.append(entry)
    return refs


def _build_table_unit(
    table_row: dict[str, Any],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
    caption_block: dict[str, Any] | None,
    note_block: dict[str, Any] | None,
    zone_key: str | None = None,
) -> dict[str, Any]:
    table_block_id = str(table_row.get("block_id") or "")
    table_block = blocks_by_id.get(table_block_id)
    if table_block is None:
        raise ValueError(
            f"block_manifest missing block_id {table_block_id!r} for table unit"
        )

    components: list[dict[str, Any]] = []
    source_block_ids: list[str] = []
    if caption_block is not None:
        caption_row = _pseudo_row_from_block(caption_block)
        components.append(
            _component_for_row(
                caption_row,
                component_role="caption",
                blocks_by_id=blocks_by_id,
            )
        )
        source_block_ids.append(str(caption_block.get("block_id") or ""))
    components.append(
        _table_body_component(table_row, blocks_by_id=blocks_by_id)
    )
    if note_block is not None:
        note_row = _pseudo_row_from_block(note_block)
        components.append(
            _component_for_row(
                note_row,
                component_role="note",
                blocks_by_id=blocks_by_id,
            )
        )
        source_block_ids.append(str(note_block.get("block_id") or ""))

    heading_path = _heading_path_for_source_block(table_row, block=table_block)
    route_meta = _route_decision_for_row(table_row, zone_key=zone_key)
    if caption_block is not None:
        caption_route = _route_decision_for_row(
            _pseudo_row_from_block(caption_block),
            zone_key=zone_key,
        )
        if caption_route.route_matched_terms:
            route_meta = caption_route
    unit: dict[str, Any] = {
        "unit_kind": "table_unit",
        "route": route_meta.route,
        "route_basis": route_meta.route_basis,
        "route_matched_terms": list(route_meta.route_matched_terms),
        "heading_path": heading_path,
        "components": components,
        "component_status": _component_status_from_components(components),
        "source_block_ids": source_block_ids,
        "context_block_ids": [],
        "source_table_ids": [table_block_id],
        "all_source_refs": _all_source_refs_from_components(components),
    }
    return unit


def _build_orphan_table_structure_unit(
    row: dict[str, Any],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
    zone_key: str | None = None,
) -> dict[str, Any]:
    block_kind = _row_block_kind(row)
    block_id = str(row.get("block_id") or "")
    route_meta = _route_decision_for_row(row, zone_key=zone_key)
    role = "caption" if block_kind == "table_caption" else "note"
    component = _component_for_row(
        row,
        component_role=role,
        blocks_by_id=blocks_by_id,
    )
    components = [component]
    return {
        "unit_kind": "table_unit",
        "route": route_meta.route,
        "route_basis": route_meta.route_basis,
        "route_matched_terms": list(route_meta.route_matched_terms),
        "heading_path": _heading_path_for_source_block(
            row,
            block=blocks_by_id.get(block_id),
        ),
        "components": components,
        "component_status": _component_status_from_components(components),
        "source_block_ids": [block_id],
        "context_block_ids": [],
        "source_table_ids": [],
        "all_source_refs": _all_source_refs_from_components(components),
    }


def _build_unknown_structure_unit(
    row: dict[str, Any],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
    projected_sentences_by_block_id: ProjectedSentencesByBlockId,
    zone_key: str | None = None,
) -> dict[str, Any]:
    block_id = str(row.get("block_id") or "")
    route_meta = _route_decision_for_row(row, zone_key=zone_key)
    projected_sentences = projected_sentences_by_block_id.get(block_id)
    if projected_sentences is None:
        raise ValueError(
            f"projected unknown-structure block {block_id!r} is missing from "
            "projected sentence index"
        )
    primary_sentences = [
        routed_primary_sentence_from_projected(sentence)
        for sentence in projected_sentences
    ]
    block_kind = _row_block_kind(row)
    source_stage = _row_source_stage(row) or "filter"
    resolved_zone_key = _row_source_zone_key(row) or (
        str(zone_key) if zone_key is not None else None
    )
    unit: dict[str, Any] = {
        "unit_kind": "text_unit",
        "route": route_meta.route,
        "route_basis": route_meta.route_basis,
        "route_matched_terms": list(route_meta.route_matched_terms),
        "heading_path": _heading_path_for_source_block(
            row,
            block=blocks_by_id.get(block_id),
        ),
        "source_block_ids": [block_id],
        "context_block_ids": [],
        "all_source_block_ids": [block_id],
        "candidate_block_kinds": [block_kind],
        "sentences": build_text_unit_sentences(primary_sentences),
        "text_refs": [dict(row.get("text_ref") or {})],
        "source_stage": source_stage,
        "source_zone_key": resolved_zone_key,
    }
    row_filter_job_id = _row_filter_job_id(row)
    if row_filter_job_id is not None:
        unit["filter_job_id"] = row_filter_job_id
    return unit


def _assemble_units_from_routing_rows(
    *,
    rows: Sequence[dict[str, Any]],
    zone_key: str | None,
    block_manifest: dict[str, Any],
    projected_sentences_by_block_id: ProjectedSentencesByBlockId,
) -> list[dict[str, Any]]:
    blocks_by_id = _blocks_by_id(block_manifest)
    selected_rows = _sorted_selected_routing_rows(rows)
    resolved_zone_key = str(zone_key or "").strip() or None
    consumed_block_ids: set[str] = set()

    sorted_blocks = _blocks_sorted_by_position(block_manifest)
    table_units: list[dict[str, Any]] = []
    for row in selected_rows:
        if _row_block_kind(row) != _TABLE_BLOCK_KIND:
            continue
        table_block_id = str(row.get("block_id") or "")
        table_block = blocks_by_id.get(table_block_id)
        if table_block is None:
            continue
        caption_block = _find_caption_block_for_table(
            table_block,
            block_manifest=block_manifest,
            consumed_block_ids=consumed_block_ids,
            sorted_blocks=sorted_blocks,
        )
        note_block = _find_note_block_for_table(
            table_block,
            block_manifest=block_manifest,
            consumed_block_ids=consumed_block_ids,
            sorted_blocks=sorted_blocks,
        )
        for attached in (caption_block, note_block):
            if attached is not None:
                consumed_block_ids.add(str(attached.get("block_id") or ""))
        consumed_block_ids.add(table_block_id)
        table_units.append(
            _build_table_unit(
                row,
                blocks_by_id=blocks_by_id,
                caption_block=caption_block,
                note_block=note_block,
                zone_key=resolved_zone_key,
            )
        )

    for row in selected_rows:
        block_id = str(row.get("block_id") or "")
        if block_id in consumed_block_ids:
            continue
        block_kind = _row_block_kind(row)
        if block_kind not in {"table_caption", "table_note"}:
            continue
        consumed_block_ids.add(block_id)
        table_units.append(
            _build_orphan_table_structure_unit(
                row,
                blocks_by_id=blocks_by_id,
                zone_key=resolved_zone_key,
            )
        )

    text_unit_groups = _group_text_rows_into_units(
        selected_rows,
        consumed_block_ids=consumed_block_ids,
        zone_key=resolved_zone_key,
    )
    text_units = [
        _build_text_unit(
            group,
            blocks_by_id=blocks_by_id,
            projected_sentences_by_block_id=projected_sentences_by_block_id,
            zone_key=resolved_zone_key,
        )
        for group in text_unit_groups
    ]

    for row in selected_rows:
        block_id = str(row.get("block_id") or "")
        if block_id in consumed_block_ids:
            continue
        block_kind = _row_block_kind(row)
        if block_kind in {"heading", "paragraph", "list_item"}:
            continue
        if block_kind in {_TABLE_BLOCK_KIND, "table_caption", "table_note"}:
            continue
        consumed_block_ids.add(block_id)
        text_units.append(
            _build_unknown_structure_unit(
                row,
                blocks_by_id=blocks_by_id,
                projected_sentences_by_block_id=projected_sentences_by_block_id,
                zone_key=resolved_zone_key,
            )
        )

    return text_units + table_units


def _group_units_by_route(all_units: list[dict[str, Any]]) -> dict[Route, list[dict[str, Any]]]:
    grouped: dict[Route, list[dict[str, Any]]] = {route: [] for route in ROUTES}
    for unit in all_units:
        route = str(unit.get("route") or "unknown")
        if route not in grouped:
            route = "unknown"
        grouped[route].append(dict(unit))  # type: ignore[index]
    return grouped


def _assign_route_unit_ids(units_by_route: dict[Route, list[dict[str, Any]]]) -> None:
    for route in ROUTES:
        prefix = _ROUTE_UNIT_ID_PREFIX[route]
        for index, unit in enumerate(units_by_route[route], start=1):
            unit["unit_id"] = f"{prefix}{index:04d}"


def _route_counts(units_by_route: dict[Route, list[dict[str, Any]]]) -> dict[str, int]:
    counts = {f"{route}_unit_count": len(units_by_route[route]) for route in ROUTES}
    counts["total_routed_unit_count"] = sum(counts.values())
    return counts
