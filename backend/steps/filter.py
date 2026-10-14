from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from core.document.structure.headings import get_heading_text_for_match
from core.content.boundary import LLM_TEXT_FIELD, block_analysis_text
from core.filtering.block_universe import BlockUniverse
from core.filtering.jobs import ResolvedFilterJob
from core.filtering.strategies import FilterContext


_ZONE_BLOCK_FIELDS = (
    "block_id",
    "kind",
    "loc",
    "order",
    "page_no",
    "meta",
    "doc_order_index",
    "heading_path",
)

_ZONE_BLOCK_PUBLIC_FIELDS = (
    "block_id",
    "kind",
    "loc",
    "order",
    "page_no",
    "doc_order_index",
)

_PUBLIC_ZONE_META_KEYS: frozenset[str] = frozenset(
    {
        "heading_level",
        "heading_number",
        "row_count",
        "column_count",
        "non_empty_row_count",
    }
)

_MATCH_PUBLIC_KEYS = (
    "match_type",
    "match_mode",
    "matched_term",
    "matched_heading_block_id",
    "matched_heading_level",
)


def heading_paths_from_block_manifest(
    block_manifest: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Masked heading_path index from block_manifest blocks (coverage-safe source)."""
    if not block_manifest:
        return {}
    out: dict[str, list[str]] = {}
    for block in block_manifest.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_id = block.get("block_id")
        if not block_id:
            continue
        heading_path = block.get("heading_path")
        if isinstance(heading_path, list):
            out[str(block_id)] = list(heading_path)
    return out


def _strip_public_zone_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        key: meta[key]
        for key in _PUBLIC_ZONE_META_KEYS
        if key in meta
    }


def _export_match_public(
    match: dict[str, Any],
    *,
    blocks_by_id: dict[Any, dict[str, Any]],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        key: match.get(key)
        for key in _MATCH_PUBLIC_KEYS
        if match.get(key) is not None
    }
    anchor_id = match.get("matched_heading_block_id")
    anchor = blocks_by_id.get(anchor_id) if anchor_id else None
    if anchor:
        analysis_text = block_analysis_text(anchor)
        if analysis_text:
            out["matched_heading_analysis_text"] = analysis_text
    return out


def _original_text_by_block_id(mask_result: dict[str, Any] | None) -> dict[str, str]:
    if not mask_result:
        return {}
    out: dict[str, str] = {}
    for item in mask_result.get("masked_blocks") or []:
        if isinstance(item, dict) and item.get("block_id"):
            out[str(item["block_id"])] = str(item.get("original_text") or "")
    return out


def _export_zone_block(
    block: dict[str, Any],
    *,
    include_original: bool,
    original_by_id: dict[str, str],
    heading_path_by_id: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Zone block export: debug includes raw sidecars; public uses allowlist only."""
    if include_original:
        out: dict[str, Any] = {
            key: block.get(key)
            for key in _ZONE_BLOCK_FIELDS
            if block.get(key) is not None
        }
    else:
        out = {
            key: block.get(key)
            for key in _ZONE_BLOCK_PUBLIC_FIELDS
            if block.get(key) is not None
        }
        meta = block.get("meta")
        if isinstance(meta, dict):
            public_meta = _strip_public_zone_meta(meta)
            if public_meta:
                out["meta"] = public_meta
        block_id = str(block.get("block_id") or "")
        if heading_path_by_id and block_id in heading_path_by_id:
            out["heading_path"] = list(heading_path_by_id[block_id])

    out[LLM_TEXT_FIELD] = block_analysis_text(block)
    if include_original:
        bid = str(block.get("block_id") or "")
        out["original_text"] = original_by_id.get(
            bid, block.get("normalized_text") or block.get("text") or ""
        )
    return out


def _reexport_heading_lineage(
    lineage: list[dict[str, Any]],
    *,
    blocks_by_id: dict[Any, dict[str, Any]],
    for_public_export: bool,
) -> list[dict[str, Any]]:
    """Map lineage block ids to zone blocks for masked vs structural ``text``."""
    out: list[dict[str, Any]] = []
    for item in lineage:
        block = blocks_by_id.get(item.get("block_id"), {})
        meta = block.get("meta") or {}
        analysis_text = block_analysis_text(block) if block else (
            item.get("analysis_text")
            or item.get(LLM_TEXT_FIELD)
            or item.get("text")
            or ""
        )
        structural_text = (
            get_heading_text_for_match(block)
            if block
            else item.get("heading_text_stripped") or item.get("text") or ""
        )
        display_text = analysis_text if for_public_export else structural_text
        entry: dict[str, Any] = {
            "block_id": item.get("block_id"),
            "text": display_text,
            "analysis_text": analysis_text,
            "heading_level": meta.get("heading_level")
            or item.get("heading_level"),
            "heading_number": meta.get("heading_number")
            or item.get("heading_number"),
            "loc": block.get("loc") or item.get("loc"),
        }
        if not for_public_export:
            stripped = meta.get("heading_text_stripped") or item.get(
                "heading_text_stripped"
            )
            if stripped is not None:
                entry["heading_text_stripped"] = stripped
        out.append(entry)
    return out


def _export_nested_matched_heading(
    block: dict[str, Any],
    *,
    matched_term: str | None,
    include_original: bool,
    original_by_id: dict[str, str],
) -> dict[str, Any]:
    meta = block.get("meta") or {}
    out: dict[str, Any] = {
        "block_id": block.get("block_id"),
        LLM_TEXT_FIELD: block_analysis_text(block),
        "matched_term": matched_term,
        "heading_level": meta.get("heading_level"),
        "loc": block.get("loc"),
    }
    if not include_original:
        return out
    out["heading_text_stripped"] = meta.get("heading_text_stripped")
    bid = str(block.get("block_id") or "")
    out["original_text"] = original_by_id.get(
        bid, block.get("normalized_text") or block.get("text") or ""
    )
    return out


def _nested_item_as_block(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "block_id": item.get("block_id"),
        "text": item.get("text"),
        "loc": item.get("loc"),
        "meta": {
            "heading_text_stripped": item.get("heading_text_stripped"),
            "heading_level": item.get("heading_level"),
        },
    }


def _export_filter_payload(
    payload: dict[str, Any],
    *,
    mask_result: dict[str, Any] | None,
    include_original: bool,
    heading_path_by_id: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    original_by_id = _original_text_by_block_id(mask_result)
    out = deepcopy(payload)
    zones: list[dict[str, Any]] = []
    for zone in out.get("matched_zones") or []:
        z = deepcopy(zone)
        raw_blocks = z.get("blocks") or []
        blocks_by_id = {
            b.get("block_id"): b for b in raw_blocks if b.get("block_id")
        }
        for group_key in ("blocks", "table_blocks"):
            z[group_key] = [
                _export_zone_block(
                    b,
                    include_original=include_original,
                    original_by_id=original_by_id,
                    heading_path_by_id=heading_path_by_id,
                )
                for b in z.get(group_key) or []
            ]
        z["nested_matched_headings"] = [
            _export_nested_matched_heading(
                _nested_item_as_block(item),
                matched_term=item.get("matched_term"),
                include_original=include_original,
                original_by_id=original_by_id,
            )
            for item in z.get("nested_matched_headings") or []
        ]
        if z.get("heading_lineage"):
            z["heading_lineage"] = _reexport_heading_lineage(
                z.get("heading_lineage") or [],
                blocks_by_id=blocks_by_id,
                for_public_export=not include_original,
            )
        if include_original:
            anchor_id = (z.get("match") or {}).get("matched_heading_block_id")
            if anchor_id:
                match = deepcopy(z.get("match") or {})
                match["matched_heading_original_text"] = original_by_id.get(
                    str(anchor_id), match.get("matched_heading_text") or ""
                )
                z["match"] = match
        else:
            match = z.get("match") or {}
            if isinstance(match, dict):
                z["match"] = _export_match_public(
                    match,
                    blocks_by_id=blocks_by_id,
                )
        zones.append(z)
    out["matched_zones"] = zones
    return out


def to_public_filter_payload(
    payload: dict[str, Any],
    *,
    mask_result: dict[str, Any] | None = None,
    block_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cloud-safe filter output: zone blocks use ``analysis_text`` only."""
    return _export_filter_payload(
        payload,
        mask_result=mask_result,
        include_original=False,
        heading_path_by_id=heading_paths_from_block_manifest(block_manifest),
    )


def export_public_zone(
    raw_zone: dict[str, Any],
    *,
    block_manifest: dict[str, Any] | None = None,
    mask_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Export one in-memory heading zone to the public zone_match shape."""
    exported = to_public_filter_payload(
        {"matched_zones": [raw_zone]},
        mask_result=mask_result,
        block_manifest=block_manifest,
    )
    zones = exported.get("matched_zones") or []
    if len(zones) != 1:
        raise ValueError("export_public_zone expected exactly one matched zone")
    zone = zones[0]
    if not isinstance(zone, dict):
        raise ValueError("export_public_zone matched zone must be a mapping")
    return zone


def to_debug_filter_payload(
    payload: dict[str, Any],
    *,
    mask_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Local debug filter output: includes ``original_text`` on blocks."""
    return _export_filter_payload(
        payload, mask_result=mask_result, include_original=True
    )


def extract_zones_from_bundle(
    bundle: Mapping[str, Any],
    filter_job: ResolvedFilterJob,
) -> dict[str, Any]:
    """
    filter: target-zone extraction from a Prepare Analysis bundle.

    Content boundary (see ``core.content.boundary``)::

        matching source = raw / original structural metadata
        LLM source      = masked textual content

    Zone heading **matching** uses ``get_heading_text_for_match`` (prefers
    ``meta.heading_text_stripped``). Public export maps zone blocks to
    ``analysis_text`` for tag/LLM; ``match.*`` fields remain matching audit only.
    """
    config = filter_job.config
    strategy = filter_job.strategy
    block_universe = BlockUniverse.from_analysis_bundle(bundle)
    result = strategy.extract(
        block_universe=block_universe,
        zone_config=config,
        context=FilterContext(
            zone_index_start=1,
        ),
    )
    matched_zones = list(result.matched_zones)

    meta = bundle.get("document_meta") or {}
    input_parser_version = meta.get("parser_version") or meta.get("handler_version")
    input_parser_type = meta.get("parser_type")
    if isinstance(input_parser_type, str) and input_parser_type.startswith(
        "docx_handlers_v"
    ):
        input_parser_type = "docx_handlers"

    payload: dict[str, Any] = {
        "doc_id": bundle.get("doc_id"),
        "file_name": bundle.get("file_name"),
        "source_type": bundle.get("source_type"),
        "input_bundle_schema_version": meta.get("bundle_schema_version"),
        "input_parser_type": input_parser_type,
        "input_parser_version": input_parser_version,
        "input_stage": "prepare_analysis",
        "stage": "filter",
        "pipeline": ["extract", "prepare_analysis", "filter"],
        "zone_config_name": config.zone_config_name,
        "zone_config_version": config.zone_config_version,
        "language": config.language,
        "resolved_filter_strategy_id": strategy.strategy_id,
        "matched_zone_count": len(matched_zones),
        "matched_zones": matched_zones,
    }
    file_hash = bundle.get("file_hash")
    if isinstance(file_hash, str) and file_hash.strip():
        payload["file_hash"] = file_hash.strip()
    return payload


INCLUDE_REASON_MATCHED_ZONE = "matched_zone"
EXCLUDE_REASON_NOT_MATCHED = "not_matched_by_zone_filter"


def _matched_terms_from_match(match: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    term = match.get("matched_term")
    if isinstance(term, str) and term.strip():
        terms.append(term.strip())
    return terms


def _zone_match_from_zone(zone: dict[str, Any]) -> dict[str, Any]:
    match = zone.get("match") or {}
    return {
        "zone_id": zone.get("zone_id"),
        "match_type": match.get("match_type"),
        "matched_block_id": match.get("matched_heading_block_id"),
        "matched_terms": _matched_terms_from_match(match),
    }


def _included_blocks_by_id(public_filter_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """First zone that includes a block wins for ``zone_match`` metadata."""
    out: dict[str, dict[str, Any]] = {}
    for zone in public_filter_result.get("matched_zones") or []:
        if not isinstance(zone, dict):
            continue
        zone_match = _zone_match_from_zone(zone)
        for group_key in ("blocks", "table_blocks"):
            for block in zone.get(group_key) or []:
                if not isinstance(block, dict):
                    continue
                block_id = block.get("block_id")
                if not block_id:
                    continue
                key = str(block_id)
                if key not in out:
                    out[key] = zone_match
    return out


def _block_kind_for_content_block(block: dict[str, Any]) -> str:
    return str(block.get("kind") or "paragraph")


def _coverage_entry_from_block_manifest_block(
    block: dict[str, Any],
    *,
    included: bool,
    zone_match: dict[str, Any] | None,
    block_kind: str,
) -> dict[str, Any]:
    zone_ids: list[str] = []
    if included and isinstance(zone_match, dict) and zone_match.get("zone_id"):
        zone_ids.append(str(zone_match["zone_id"]))
    return {
        "block_id": block.get("block_id"),
        "block_kind": block_kind,
        "order": block.get("order"),
        "doc_order_index": block.get("doc_order_index"),
        "heading_path": list(block.get("heading_path") or []),
        "selected_by_filter": included,
        "include_reason": INCLUDE_REASON_MATCHED_ZONE if included else None,
        "exclude_reason": None if included else EXCLUDE_REASON_NOT_MATCHED,
        "zone_match": zone_match,
        "zone_ids": zone_ids,
        "selected_sentence_ids": [],
        "text_ref": dict(block.get("text_ref") or {}),
    }


def derive_block_selection_coverage(
    *,
    block_manifest: dict[str, Any],
    public_filter_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Derive per-block Filter selection ledger rows (in-memory, path-free).

    ``selected_by_filter`` is true when the block appears in at least one public
    matched zone for this Filter job. It does not indicate semantic review
    completeness, clinical relevance, or checked/not-checked status.
    """
    blocks = block_manifest.get("blocks") or []
    if not isinstance(blocks, list):
        raise ValueError("block_manifest.blocks must be a list")
    table_blocks = block_manifest.get("table_blocks") or []
    if not isinstance(table_blocks, list):
        raise ValueError("block_manifest.table_blocks must be a list")

    included_by_id = _included_blocks_by_id(public_filter_result)
    coverage: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("block_id") or "")
        included = block_id in included_by_id
        coverage.append(
            _coverage_entry_from_block_manifest_block(
                block,
                included=included,
                zone_match=included_by_id.get(block_id) if included else None,
                block_kind=_block_kind_for_content_block(block),
            )
        )
    for block in table_blocks:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("block_id") or "")
        included = block_id in included_by_id
        coverage.append(
            _coverage_entry_from_block_manifest_block(
                block,
                included=included,
                zone_match=included_by_id.get(block_id) if included else None,
                block_kind="table",
            )
        )
    return coverage
