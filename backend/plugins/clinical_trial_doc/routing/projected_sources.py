"""Route unit preparation from Filter-output ProjectedSource values."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from artifacts.routing.types import ROUTES, RoutedUnitSet
from operations.filter_output_projection.contracts import (
    ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
    RAW_SOURCE_REPRESENTATION_KIND,
    ProjectedSource,
)

from plugins.clinical_trial_doc.routing.processor import (
    _assemble_units_from_routing_rows,
    _assign_route_unit_ids,
    _block_kind_value,
    _block_position_key,
    _blocks_by_id,
    _blocks_sorted_by_position,
    _group_units_by_route,
    _route_counts,
)
from artifacts.routing.primary_sentence_contract import build_text_unit_sentences
from plugins.clinical_trial_doc.routing.projected_sentence_index import (
    build_projected_sentences_by_block_id,
    routed_primary_sentence_from_projected,
)

RAW_PROJECTED_SOURCE_STAGE = "filter_projection"


def _source_lineage(source: ProjectedSource) -> dict[str, str]:
    lineage = source.lineage
    if not isinstance(lineage, dict):
        return {}
    return {str(key): str(value) for key, value in lineage.items()}


def _source_zone_key(source: ProjectedSource) -> str | None:
    zone_key = _source_lineage(source).get("zone_key")
    if isinstance(zone_key, str) and zone_key.strip():
        return zone_key.strip()
    return None


def _source_filter_job_id(source: ProjectedSource) -> str | None:
    filter_job_id = _source_lineage(source).get("filter_job_id")
    if isinstance(filter_job_id, str) and filter_job_id.strip():
        return filter_job_id.strip()
    return None


def _source_zone_id(source: ProjectedSource) -> str | None:
    zone_id = _source_lineage(source).get("zone_id")
    if isinstance(zone_id, str) and zone_id.strip():
        return zone_id.strip()
    return None


def _block_kind_from_block(block: dict[str, Any]) -> str:
    kind = block.get("kind") or block.get("block_kind")
    if isinstance(kind, str) and kind.strip():
        return kind.strip()
    return "paragraph"


def _heading_path_from_block(block: dict[str, Any]) -> list[str]:
    heading_path = block.get("heading_path")
    if not isinstance(heading_path, list):
        return []
    return [str(item) for item in heading_path]


def _position_fields_from_block(block: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    order = block.get("order")
    if order is not None:
        fields["order"] = order
    doc_order_index = block.get("doc_order_index")
    if doc_order_index is not None:
        fields["doc_order_index"] = doc_order_index
    return fields


def _routing_row_from_block(
    block: dict[str, Any],
    *,
    source_stage: str = RAW_PROJECTED_SOURCE_STAGE,
    zone_match: dict[str, str] | None = None,
) -> dict[str, Any]:
    block_id = str(block.get("block_id") or "")
    row: dict[str, Any] = {
        "block_id": block_id,
        "block_kind": _block_kind_from_block(block),
        "heading_path": _heading_path_from_block(block),
        "selected_by_filter": True,
        "source_stage": source_stage,
        "text_ref": dict(block.get("text_ref") or {"block_id": block_id}),
        **_position_fields_from_block(block),
    }
    if zone_match is not None:
        row["zone_match"] = dict(zone_match)
    return row


def validate_projected_sources_semantic_module(
    projected_sources: Sequence[ProjectedSource],
    *,
    expected_semantic_module_id: str,
) -> None:
    """Reject projected sources whose semantic module does not match the expected module."""

    if not isinstance(expected_semantic_module_id, str) or not expected_semantic_module_id.strip():
        raise ValueError("expected_semantic_module_id must be a non-empty string")
    expected = expected_semantic_module_id.strip()
    for index, source in enumerate(projected_sources):
        if source.semantic_module_id != expected:
            raise ValueError(
                f"projected_sources[{index}].semantic_module_id="
                f"{source.semantic_module_id!r} does not match expected "
                f"semantic_module_id={expected!r}"
            )


def _require_raw_payload(source: ProjectedSource) -> dict[str, Any]:
    return dict(source.payload) if isinstance(source.payload, dict) else {}


def _primary_block_id(source: ProjectedSource) -> str:
    if not source.source_refs:
        raise ValueError("projected source must include at least one source_ref")
    block_id = source.source_refs[0].refs.get("block_id")
    if not isinstance(block_id, str) or not block_id.strip():
        raise ValueError("projected source source_ref must include block_id")
    return block_id.strip()


def _require_assembled_sentences(source: ProjectedSource) -> tuple:
    if not source.sentences:
        raise ValueError(
            "assembled_semantic projected source requires non-empty sentences"
        )
    return source.sentences


def _heading_path_from_projected_source(source: ProjectedSource) -> list[str]:
    payload = dict(source.payload) if isinstance(source.payload, dict) else {}
    heading_path = payload.get("heading_path")
    if isinstance(heading_path, list) and heading_path:
        return [str(item) for item in heading_path]
    return []


def _routing_row_from_raw_projected_source(
    source: ProjectedSource,
    *,
    blocks_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Map one raw projected source to a routing row using manifest structure."""
    payload = _require_raw_payload(source)
    block_id = _primary_block_id(source)
    block = blocks_by_id.get(block_id)

    if block is not None:
        row = _routing_row_from_block(
            block,
            source_stage=RAW_PROJECTED_SOURCE_STAGE,
        )
        payload_heading_path = payload.get("heading_path")
        if (
            not row.get("heading_path")
            and isinstance(payload_heading_path, list)
            and payload_heading_path
        ):
            row["heading_path"] = [str(item) for item in payload_heading_path]
    else:
        block_kind = str(payload.get("block_kind") or "paragraph")
        heading_path = payload.get("heading_path")
        if not isinstance(heading_path, list):
            heading_path = []
        row = {
            "block_id": block_id,
            "block_kind": block_kind,
            "heading_path": [str(item) for item in heading_path],
            "selected_by_filter": True,
            "source_stage": RAW_PROJECTED_SOURCE_STAGE,
            "text_ref": {"block_id": block_id},
        }

    zone_id = _source_zone_id(source)
    if zone_id is not None:
        row["zone_match"] = {"zone_id": zone_id}

    zone_key = _source_zone_key(source)
    if zone_key is not None:
        row["source_zone_key"] = zone_key
    filter_job_id = _source_filter_job_id(source)
    if filter_job_id is not None:
        row["filter_job_id"] = filter_job_id
    return row


def _heading_is_context_for_projected_blocks(
    heading_block: dict[str, Any],
    *,
    projected_block_ids: set[str],
    blocks_by_id: dict[str, dict[str, Any]],
    routing_rows_by_id: dict[str, dict[str, Any]] | None = None,
) -> bool:
    heading_path = tuple(_heading_path_from_block(heading_block))
    if not heading_path:
        return False
    for block_id in projected_block_ids:
        candidate_path: tuple[str, ...]
        routing_row = (routing_rows_by_id or {}).get(block_id)
        if isinstance(routing_row, dict) and routing_row.get("heading_path"):
            candidate_path = tuple(str(item) for item in routing_row["heading_path"])
        else:
            block = blocks_by_id.get(block_id)
            if block is None:
                continue
            candidate_path = tuple(_heading_path_from_block(block))
        if candidate_path[: len(heading_path)] == heading_path:
            return True
    return False


def _zone_match_for_heading_enrichment(
    rows: list[dict[str, Any]],
) -> dict[str, str] | None:
    for row in rows:
        zone_match = row.get("zone_match")
        if isinstance(zone_match, dict):
            zone_id = zone_match.get("zone_id")
            if isinstance(zone_id, str) and zone_id.strip():
                return {"zone_id": zone_id.strip()}
    return None


def _enrich_routing_rows_with_manifest_headings(
    rows: list[dict[str, Any]],
    *,
    projected_block_ids: set[str],
    block_manifest: dict[str, Any],
    blocks_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add manifest heading blocks within the projected span for grouping context."""
    if not rows or not projected_block_ids:
        return rows

    row_ids = {str(row.get("block_id") or "") for row in rows}
    projected_keys = [
        _block_position_key(blocks_by_id[block_id])
        for block_id in projected_block_ids
        if block_id in blocks_by_id
    ]
    if not projected_keys:
        return rows

    span_lo = min(projected_keys)
    span_hi = max(projected_keys)
    zone_match = _zone_match_for_heading_enrichment(rows)
    routing_rows_by_id = {str(row.get("block_id") or ""): row for row in rows}
    enriched = list(rows)

    for block in _blocks_sorted_by_position(block_manifest):
        block_id = str(block.get("block_id") or "")
        if not block_id or block_id in row_ids:
            continue
        if block_id in projected_block_ids:
            continue
        block_key = _block_position_key(block)
        if block_key > span_hi:
            continue
        if _block_kind_value(block) != "heading":
            continue
        if block_key < span_lo and not _heading_is_context_for_projected_blocks(
            block,
            projected_block_ids=projected_block_ids,
            blocks_by_id=blocks_by_id,
            routing_rows_by_id=routing_rows_by_id,
        ):
            continue
        enriched.append(
            _routing_row_from_block(
                block,
                source_stage=RAW_PROJECTED_SOURCE_STAGE,
                zone_match=zone_match,
            )
        )
        row_ids.add(block_id)

    return enriched


def _build_assembled_projected_source_unit(
    source: ProjectedSource,
) -> dict[str, Any]:
    sentences = _require_assembled_sentences(source)
    heading_path = _heading_path_from_projected_source(source)
    primary_sentences = [
        routed_primary_sentence_from_projected(sentence) for sentence in sentences
    ]
    source_block_ids = [
        str(sentence.get("source_block_id") or "")
        for sentence in primary_sentences
        if sentence.get("source_block_id")
    ]
    all_source_block_ids = list(
        dict.fromkeys([*source_block_ids, _primary_block_id(source)])
    )
    unit: dict[str, Any] = {
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": "projected_assembled_semantic",
        "route_matched_terms": [],
        "heading_path": heading_path,
        "sentences": build_text_unit_sentences(primary_sentences),
        "source_block_ids": source_block_ids or [_primary_block_id(source)],
        "context_block_ids": [],
        "all_source_block_ids": all_source_block_ids,
        "candidate_block_kinds": ["paragraph"],
        "text_refs": [],
        "source_stage": RAW_PROJECTED_SOURCE_STAGE,
    }
    zone_key = _source_zone_key(source)
    if zone_key is not None:
        unit["source_zone_key"] = zone_key
    filter_job_id = _source_filter_job_id(source)
    if filter_job_id is not None:
        unit["filter_job_id"] = filter_job_id
    return unit


def _build_units_from_raw_projected_sources(
    projected_sources: Sequence[ProjectedSource],
    *,
    block_manifest: dict[str, Any],
    zone_key: str | None,
) -> list[dict[str, Any]]:
    if not projected_sources:
        return []

    blocks_by_id = _blocks_by_id(block_manifest)
    projected_sentences_by_block_id = build_projected_sentences_by_block_id(
        projected_sources
    )
    projected_block_ids = {_primary_block_id(source) for source in projected_sources}
    routing_rows = [
        _routing_row_from_raw_projected_source(
            source,
            blocks_by_id=blocks_by_id,
        )
        for source in projected_sources
    ]
    routing_rows = _enrich_routing_rows_with_manifest_headings(
        routing_rows,
        projected_block_ids=projected_block_ids,
        block_manifest=block_manifest,
        blocks_by_id=blocks_by_id,
    )
    return _assemble_units_from_routing_rows(
        rows=routing_rows,
        zone_key=zone_key,
        block_manifest=block_manifest,
        projected_sentences_by_block_id=projected_sentences_by_block_id,
    )


def _segment_selected_sources(
    projected_sources: Sequence[ProjectedSource],
) -> list[tuple[str, tuple[ProjectedSource, ...]]]:
    segments: list[tuple[str, tuple[ProjectedSource, ...]]] = []
    current_rep: str | None = None
    current_items: list[ProjectedSource] = []

    def flush() -> None:
        nonlocal current_rep, current_items
        if current_rep is None or not current_items:
            current_rep = None
            current_items = []
            return
        if current_rep == ASSEMBLED_SEMANTIC_REPRESENTATION_KIND:
            for item in current_items:
                segments.append((current_rep, (item,)))
        else:
            segments.append((current_rep, tuple(current_items)))
        current_rep = None
        current_items = []

    for source in projected_sources:
        rep = source.representation_kind
        if rep == ASSEMBLED_SEMANTIC_REPRESENTATION_KIND:
            flush()
            segments.append((rep, (source,)))
            continue
        if current_rep == RAW_SOURCE_REPRESENTATION_KIND:
            current_items.append(source)
        else:
            flush()
            current_rep = rep
            current_items = [source]
    flush()
    return segments


def route_prepare_units_from_projected_sources(
    *,
    projected_sources: Sequence[ProjectedSource],
    block_manifest: dict[str, Any],
    analysis_bundle: dict[str, Any],
    expected_semantic_module_id: str,
    doc_id: str,
    file_hash: str,
) -> RoutedUnitSet:
    """Assemble route units from already-selected projected sources."""

    validate_projected_sources_semantic_module(
        projected_sources,
        expected_semantic_module_id=expected_semantic_module_id,
    )

    all_units: list[dict[str, Any]] = []
    for representation, segment_sources in _segment_selected_sources(projected_sources):
        if representation == ASSEMBLED_SEMANTIC_REPRESENTATION_KIND:
            for source in segment_sources:
                all_units.append(_build_assembled_projected_source_unit(source))
            continue
        segment_zone_key = _source_zone_key(segment_sources[0])
        all_units.extend(
            _build_units_from_raw_projected_sources(
                segment_sources,
                block_manifest=block_manifest,
                zone_key=segment_zone_key,
            )
        )

    units_by_route = _group_units_by_route(all_units)
    _assign_route_unit_ids(units_by_route)
    route_counts = _route_counts(units_by_route)
    flat_units = tuple(unit for route in ROUTES for unit in units_by_route[route])
    return RoutedUnitSet(
        units_by_route={route: list(units_by_route[route]) for route in ROUTES},
        route_counts=route_counts,
        all_units=flat_units,
    )


__all__ = [
    "route_prepare_units_from_projected_sources",
    "validate_projected_sources_semantic_module",
]
