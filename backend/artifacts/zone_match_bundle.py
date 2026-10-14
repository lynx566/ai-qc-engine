"""
Persisted ``zone_match_bundle.json`` contract.

The Step supplies the public Filter semantic payload; this module owns the
canonical filename, persisted bundle assembly, and structural + privacy validation.
"""

from __future__ import annotations

from typing import Any

from artifacts.privacy_safety import assert_zone_match_public_safe

ZONE_MATCH_BUNDLE_FILENAME = "zone_match_bundle.json"
ZONE_MATCH_BUNDLE_DEBUG_FILENAME = "zone_match_bundle.debug.json"


def build_zone_match_bundle(public_semantic_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Assemble the canonical persisted zone_match_bundle from Step-derived data.

    Does not derive Filter semantics; *public_semantic_payload* must already be
    the privacy-safe public projection from ``steps.filter``.
    """
    if not isinstance(public_semantic_payload, dict):
        raise ValueError("zone_match_bundle payload must be a mapping")
    payload = dict(public_semantic_payload)
    assert_zone_match_bundle_safe(payload)
    return payload


def assert_zone_match_bundle_safe(payload: dict[str, Any]) -> None:
    """Validate structural invariants and delegate privacy checks."""
    if not isinstance(payload, dict):
        raise ValueError("zone_match_bundle must be a mapping")

    matched_zones = payload.get("matched_zones")
    if not isinstance(matched_zones, list):
        raise ValueError("zone_match_bundle.matched_zones must be a list")

    for field in (
        "zone_config_name",
        "zone_config_version",
        "language",
        "resolved_filter_strategy_id",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"zone_match_bundle.{field} must be a non-empty string")

    matched_zone_count = payload.get("matched_zone_count")
    if matched_zone_count is not None:
        if not isinstance(matched_zone_count, int):
            raise ValueError("zone_match_bundle.matched_zone_count must be an int")
        if matched_zone_count != len(matched_zones):
            raise ValueError(
                "zone_match_bundle.matched_zone_count must equal len(matched_zones)"
            )

    seen_zone_ids: set[str] = set()
    for index, zone in enumerate(matched_zones):
        if not isinstance(zone, dict):
            raise ValueError(f"zone_match_bundle.matched_zones[{index}] must be a mapping")
        zone_id = zone.get("zone_id")
        if not isinstance(zone_id, str) or not zone_id.strip():
            raise ValueError(
                f"zone_match_bundle.matched_zones[{index}].zone_id is required"
            )
        if zone_id in seen_zone_ids:
            raise ValueError(f"duplicate zone_id {zone_id!r} in matched_zones")
        seen_zone_ids.add(zone_id)
        for group_key in ("blocks", "table_blocks"):
            for block_index, block in enumerate(zone.get(group_key) or []):
                if not isinstance(block, dict):
                    raise ValueError(
                        f"zone_match_bundle.matched_zones[{index}].{group_key}"
                        f"[{block_index}] must be a mapping"
                    )
                block_id = block.get("block_id")
                if not isinstance(block_id, str) or not str(block_id).strip():
                    raise ValueError(
                        f"zone_match_bundle.matched_zones[{index}].{group_key}"
                        f"[{block_index}].block_id is required"
                    )

    assert_zone_match_public_safe(payload)
