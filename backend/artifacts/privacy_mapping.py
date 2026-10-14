"""Formal mapping.json packaging for Prepare Analysis privacy results."""
# ruff: noqa: TRY004 -- schema validators consistently report contract violations as values.

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from privacy.schemas import EntityType, MaskHit

MAPPING_FILENAME = "mapping.json"
MAPPING_ARTIFACT_SCHEMA_VERSION = "0.2.0"

_SOURCE_SORT_ORDER: dict[str, int] = {
    "registry": 0,
    "regex": 1,
    "uie": 2,
}


def _sort_sources(sources: Iterable[str]) -> list[str]:
    unique = {source for source in sources if source}
    if not unique:
        return ["unknown"]
    return sorted(unique, key=lambda source: (_SOURCE_SORT_ORDER.get(source, 99), source))


def _group_key(hit: MaskHit) -> tuple[str, EntityType, str, str | None]:
    if hit.canonical_id:
        return ("canonical", hit.entity_type, hit.canonical_id, hit.token)
    return ("text", hit.entity_type, hit.token, hit.original_text)


def _sort_group_key(
    key: tuple[str, EntityType, str, str | None],
) -> tuple[str, str, str, str]:
    kind, entity_type, part_a, part_b = key
    if kind == "canonical":
        return (entity_type, part_a, part_b or "", "")
    return (entity_type, "", part_a, part_b or "")


def validate_privacy_mapping_artifact(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != MAPPING_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("mapping.schema_version is unsupported")
    if not isinstance(payload.get("doc_id"), str) or not payload["doc_id"].strip():
        raise ValueError("mapping.doc_id is required")
    mappings = payload.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("mapping.mappings must be a list")
    for index, row in enumerate(mappings):
        if not isinstance(row, Mapping):
            raise ValueError(f"mapping.mappings[{index}] must be an object")
        for field in ("entity_type", "token"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"mapping.mappings[{index}].{field} is required")
        if not isinstance(row.get("original_texts"), list):
            raise ValueError(f"mapping.mappings[{index}].original_texts must be a list")
        if not isinstance(row.get("sources"), list):
            raise ValueError(f"mapping.mappings[{index}].sources must be a list")
        if not isinstance(row.get("occurrence_count"), int) or row["occurrence_count"] < 1:
            raise ValueError(
                f"mapping.mappings[{index}].occurrence_count must be a positive integer"
            )


def build_privacy_mapping_artifact(
    *,
    doc_id: str,
    mask_hits: Iterable[MaskHit],
) -> dict[str, Any]:
    """Package already-produced mask hits into the stable mapping contract."""

    groups: dict[tuple[str, EntityType, str, str | None], dict[str, Any]] = {}
    for hit in mask_hits:
        key = _group_key(hit)
        group = groups.get(key)
        if group is None:
            group = {
                "entity_type": hit.entity_type,
                "canonical_id": hit.canonical_id,
                "parent_canonical_id": hit.parent_canonical_id,
                "token": hit.token,
                "original_texts": [],
                "_original_texts_seen": set(),
                "sources": set(),
                "occurrence_count": 0,
            }
            groups[key] = group
        elif group["token"] != hit.token:
            raise ValueError(
                f"inconsistent token for group {key!r}: "
                f"{group['token']!r} vs {hit.token!r}"
            )
        group["occurrence_count"] += 1
        group["sources"].update(hit.sources if hit.sources else (hit.source,))
        if hit.original_text not in group["_original_texts_seen"]:
            group["_original_texts_seen"].add(hit.original_text)
            group["original_texts"].append(hit.original_text)

    rows: list[dict[str, Any]] = []
    for key in sorted(groups, key=_sort_group_key):
        group = groups[key]
        row: dict[str, Any] = {
            "entity_type": group["entity_type"],
            "token": group["token"],
            "original_texts": list(group["original_texts"]),
            "sources": _sort_sources(group["sources"]),
            "occurrence_count": group["occurrence_count"],
        }
        if group["canonical_id"]:
            row["canonical_id"] = group["canonical_id"]
        if group.get("parent_canonical_id"):
            row["parent_canonical_id"] = group["parent_canonical_id"]
        rows.append(row)

    artifact = {
        "schema_version": MAPPING_ARTIFACT_SCHEMA_VERSION,
        "doc_id": doc_id,
        "mappings": rows,
    }
    validate_privacy_mapping_artifact(artifact)
    return artifact


__all__ = [
    "MAPPING_ARTIFACT_SCHEMA_VERSION",
    "MAPPING_FILENAME",
    "build_privacy_mapping_artifact",
    "validate_privacy_mapping_artifact",
]
