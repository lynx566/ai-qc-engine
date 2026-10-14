"""Neutral Candidate Scope selection helpers for canonical flow resume."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.document.structure.headings import get_heading_level, is_heading
from runtime.effective_candidate_scope import canonicalize_ancestor_descendant_zones


def anchor_ids_from_zone_bundle(bundle: dict[str, Any]) -> list[str]:
    anchors: list[str] = []
    for zone in bundle.get("matched_zones") or []:
        if not isinstance(zone, dict):
            continue
        match = zone.get("match") or {}
        anchor = match.get("matched_heading_block_id")
        if isinstance(anchor, str) and anchor.strip():
            anchors.append(anchor.strip())
    return anchors


def derive_operations(
    automatic_anchors: set[str],
    desired_anchors: set[str],
) -> list[dict[str, str]]:
    operations: list[dict[str, str]] = []
    for anchor in sorted(automatic_anchors):
        if anchor not in desired_anchors:
            operations.append({"anchor_block_id": anchor, "op": "remove"})
    for anchor in sorted(desired_anchors):
        if anchor not in automatic_anchors:
            operations.append({"anchor_block_id": anchor, "op": "add"})
    return operations


def sort_anchor_block_ids(
    anchor_ids: set[str],
    *,
    analysis_bundle: dict[str, Any],
) -> list[str]:
    order_by_anchor: dict[str, int] = {}
    for block in analysis_bundle.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        anchor = str(block.get("block_id") or "").strip()
        if not anchor:
            continue
        value = block.get("doc_order_index")
        if isinstance(value, int) and value >= 0:
            order_by_anchor[anchor] = value
    return sorted(anchor_ids, key=lambda item: (order_by_anchor.get(item, 10**9), item))


def canonicalize_anchor_ids_for_job(
    *,
    anchor_ids: set[str],
    analysis_bundle: dict[str, Any],
) -> set[str]:
    blocks_by_id = {
        str(block.get("block_id")): block
        for block in (analysis_bundle.get("content_blocks") or [])
        if isinstance(block, dict) and block.get("block_id")
    }
    zones: list[dict[str, Any]] = []
    for anchor in sorted(anchor_ids):
        block = blocks_by_id.get(anchor)
        if block is None or not is_heading(block):
            continue
        level = get_heading_level(block)
        zones.append(
            {
                "zone_id": f"Z_{anchor}",
                "match": {
                    "matched_heading_block_id": anchor,
                    "matched_heading_level": level,
                },
                "blocks": _pseudo_zone_blocks(anchor, blocks_by_id),
                "table_blocks": [],
            }
        )
    canonical = canonicalize_ancestor_descendant_zones(zones)
    return {
        str((zone.get("match") or {}).get("matched_heading_block_id"))
        for zone in canonical
        if (zone.get("match") or {}).get("matched_heading_block_id")
    }


def _pseudo_zone_blocks(
    anchor: str,
    blocks_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    anchor_block = blocks_by_id.get(anchor)
    if anchor_block is None:
        return [{"block_id": anchor}]
    anchor_level = get_heading_level(anchor_block)
    anchor_path = anchor_block.get("heading_path") or []
    path_prefix = (
        [str(item) for item in anchor_path] if isinstance(anchor_path, list) else []
    )
    blocks = [anchor_block]
    for block_id, block in blocks_by_id.items():
        if block_id == anchor:
            continue
        block_path = block.get("heading_path") or []
        if not isinstance(block_path, list):
            continue
        normalized = [str(item) for item in block_path]
        if len(normalized) < len(path_prefix):
            continue
        if normalized[: len(path_prefix)] != path_prefix:
            continue
        if is_heading(block):
            level = get_heading_level(block)
            if (
                anchor_level is not None
                and level is not None
                and level <= anchor_level
                and block_id != anchor
            ):
                continue
        blocks.append(block)
    return [
        {"block_id": str(item.get("block_id"))}
        for item in blocks
        if item.get("block_id")
    ]


def build_automatic_heading_ownership(
    automatic_by_job: Mapping[str, set[str]],
    *,
    heading_titles: Mapping[str, str] | None = None,
    heading_paths: Mapping[str, list[str]] | None = None,
) -> dict[str, str]:
    owners_by_anchor: dict[str, set[str]] = {}
    for filter_job_id, anchor_ids in automatic_by_job.items():
        for anchor in anchor_ids:
            owners_by_anchor.setdefault(anchor, set()).add(filter_job_id)

    ownership: dict[str, str] = {}
    for anchor, owners in owners_by_anchor.items():
        if len(owners) == 1:
            ownership[anchor] = next(iter(owners))
            continue
        title = (heading_titles or {}).get(anchor, anchor)
        path = (heading_paths or {}).get(anchor, [])
        raise ValueError(
            "Candidate heading has multiple automatic processing owners: "
            f"anchor_block_id={anchor!r}, title={title!r}, "
            f"heading_path={path!r}, "
            f"conflicting_filter_job_ids={sorted(owners)!r}"
        )
    return ownership


def heading_anchor_block_ids_from_analysis_bundle(
    analysis_bundle: dict[str, Any],
) -> set[str]:
    anchor_ids: set[str] = set()
    for block in analysis_bundle.get("content_blocks") or []:
        if not isinstance(block, dict) or not is_heading(block):
            continue
        anchor = str(block.get("block_id") or "").strip()
        if anchor:
            anchor_ids.add(anchor)
    return anchor_ids


def heading_metadata_from_analysis_bundle(
    analysis_bundle: dict[str, Any],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    titles: dict[str, str] = {}
    paths: dict[str, list[str]] = {}
    for block in analysis_bundle.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        anchor = str(block.get("block_id") or "").strip()
        if not anchor:
            continue
        analysis_text = block.get("analysis_text")
        if isinstance(analysis_text, str) and analysis_text.strip():
            titles[anchor] = analysis_text.strip()
        else:
            text = block.get("text")
            titles[anchor] = (
                text.strip() if isinstance(text, str) and text.strip() else anchor
            )
        heading_path = block.get("heading_path")
        paths[anchor] = (
            [str(item) for item in heading_path]
            if isinstance(heading_path, list)
            else []
        )
    return titles, paths


def build_review_heading_ownership(
    automatic_by_job: Mapping[str, set[str]],
    *,
    analysis_bundle: dict[str, Any],
    manual_default_filter_job_id: str | None,
) -> dict[str, str]:
    heading_titles, heading_paths = heading_metadata_from_analysis_bundle(
        analysis_bundle
    )
    automatic_ownership = build_automatic_heading_ownership(
        automatic_by_job,
        heading_titles=heading_titles,
        heading_paths=heading_paths,
    )
    ownership = dict(automatic_ownership)
    if manual_default_filter_job_id is None:
        return ownership

    for anchor in heading_anchor_block_ids_from_analysis_bundle(analysis_bundle):
        if anchor not in ownership:
            ownership[anchor] = manual_default_filter_job_id
    return ownership


def validate_selection_ownership(
    *,
    selections_by_job: Mapping[str, set[str]],
    automatic_by_job: Mapping[str, set[str]],
    analysis_bundle: dict[str, Any],
    manual_default_filter_job_id: str | None,
) -> None:
    review_heading_ownership = build_review_heading_ownership(
        automatic_by_job,
        analysis_bundle=analysis_bundle,
        manual_default_filter_job_id=manual_default_filter_job_id,
    )
    for filter_job_id, desired_anchors in selections_by_job.items():
        for anchor in desired_anchors:
            if anchor not in review_heading_ownership:
                raise ValueError(f"anchor_block_id {anchor!r} is not a known heading")
            owner = review_heading_ownership[anchor]
            if owner != filter_job_id:
                raise ValueError(
                    "candidate heading ownership mismatch: "
                    f"anchor_block_id={anchor!r}, requested_filter_job_id="
                    f"{filter_job_id!r}, canonical_owner={owner!r}"
                )


__all__ = [
    "anchor_ids_from_zone_bundle",
    "build_automatic_heading_ownership",
    "build_review_heading_ownership",
    "canonicalize_anchor_ids_for_job",
    "derive_operations",
    "heading_anchor_block_ids_from_analysis_bundle",
    "heading_metadata_from_analysis_bundle",
    "sort_anchor_block_ids",
    "validate_selection_ownership",
]
