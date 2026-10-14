"""Small view helpers for candidate-scope zone bundles."""

from __future__ import annotations

from typing import Any


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


__all__ = ["anchor_ids_from_zone_bundle"]
