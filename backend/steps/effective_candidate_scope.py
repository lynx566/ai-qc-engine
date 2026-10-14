"""Build effective candidate scope from automatic Filter output + heading overrides."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from artifacts.candidate_scope_override import assert_candidate_scope_override_safe
from artifacts.candidate_scope_resolution import (
    assert_candidate_scope_resolution_input_safe,
)
from artifacts.coverage_bundle import build_coverage_bundle
from artifacts.zone_match_bundle import build_zone_match_bundle
from core.document.doc_identity import validate_file_hash_format
from core.document.structure.headings import is_heading
from core.filtering.block_universe import BlockUniverse
from core.filtering.heading_zone import materialize_heading_anchor_zone
from steps.filter import (
    derive_block_selection_coverage,
    export_public_zone,
)

_MANUAL_MATCH_TYPE = "manual"
_MANUAL_MATCH_MODE = "user_override"
_MANUAL_MATCHED_TERM = "user_override"

RESOLVED_CANDIDATE_SCOPE_STAGE = "candidate_scope"
RESOLVED_CANDIDATE_SCOPE_INPUT_STAGE = "filter"
RESOLVED_CANDIDATE_SCOPE_PIPELINE = [
    "extract",
    "prepare_analysis",
    "filter",
    "candidate_scope",
]


@dataclass(frozen=True)
class ZoneEnvelopeConfig:
    language: str
    zone_config_name: str
    zone_config_version: str
    heading_match_mode: str


@dataclass(frozen=True)
class EffectiveCandidateScopeResult:
    effective_zone_match_bundle: dict[str, Any]
    effective_coverage_bundle: dict[str, Any]
    applied_operations: tuple[dict[str, str], ...]


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _zone_envelope_from_bundle(bundle: dict[str, Any]) -> ZoneEnvelopeConfig:
    matched_zones = bundle.get("matched_zones") or []
    heading_match_mode = "contains"
    if matched_zones:
        first_match = (matched_zones[0] or {}).get("match") or {}
        mode = first_match.get("match_mode")
        if isinstance(mode, str) and mode.strip():
            heading_match_mode = mode.strip()
    return ZoneEnvelopeConfig(
        language=_require_str(
            bundle.get("language"), field="zone_match_bundle.language"
        ),
        zone_config_name=_require_str(
            bundle.get("zone_config_name"),
            field="zone_match_bundle.zone_config_name",
        ),
        zone_config_version=_require_str(
            bundle.get("zone_config_version"),
            field="zone_match_bundle.zone_config_version",
        ),
        heading_match_mode=heading_match_mode,
    )


def _validate_identity_alignment(
    *,
    automatic_zone_match_bundle: dict[str, Any],
    candidate_scope_override: dict[str, Any],
    block_manifest: dict[str, Any],
    analysis_bundle: dict[str, Any],
) -> str:
    automatic_doc_id = _require_str(
        automatic_zone_match_bundle.get("doc_id"),
        field="zone_match_bundle.doc_id",
    )
    override_doc_id = _require_str(
        candidate_scope_override.get("doc_id"),
        field="candidate_scope_override.doc_id",
    )
    if automatic_doc_id != override_doc_id:
        raise ValueError(
            "candidate_scope_override.doc_id must match zone_match_bundle.doc_id"
        )

    manifest_doc_id = _require_str(
        block_manifest.get("doc_id"), field="block_manifest.doc_id"
    )
    if manifest_doc_id != automatic_doc_id:
        raise ValueError("block_manifest.doc_id must match zone_match_bundle.doc_id")

    analysis_doc_id = analysis_bundle.get("doc_id")
    if analysis_doc_id is not None and str(analysis_doc_id) != automatic_doc_id:
        raise ValueError("analysis_bundle.doc_id must match zone_match_bundle.doc_id")

    automatic_hash = automatic_zone_match_bundle.get("file_hash")
    if not isinstance(automatic_hash, str) or not automatic_hash.strip():
        raise ValueError("zone_match_bundle.file_hash is required")
    normalized_hash = validate_file_hash_format(automatic_hash, field="file_hash")

    manifest_hash = block_manifest.get("file_hash")
    if (
        isinstance(manifest_hash, str)
        and manifest_hash.strip()
        and validate_file_hash_format(manifest_hash, field="file_hash")
        != normalized_hash
    ):
        raise ValueError(
            "block_manifest.file_hash must match zone_match_bundle.file_hash"
        )

    analysis_hash = analysis_bundle.get("file_hash")
    if (
        isinstance(analysis_hash, str)
        and analysis_hash.strip()
        and validate_file_hash_format(analysis_hash, field="file_hash")
        != normalized_hash
    ):
        raise ValueError(
            "analysis_bundle.file_hash must match zone_match_bundle.file_hash"
        )

    return normalized_hash


def _validate_filter_job_alignment(
    *,
    automatic_zone_match_bundle: dict[str, Any],
    candidate_scope_override: dict[str, Any],
) -> None:
    zone_key = _require_str(
        automatic_zone_match_bundle.get("zone_config_name"),
        field="zone_match_bundle.zone_config_name",
    )
    filter_job_id = _require_str(
        candidate_scope_override.get("filter_job_id"),
        field="candidate_scope_override.filter_job_id",
    )
    language = automatic_zone_match_bundle.get("language")
    expected_zone_key = (
        f"{filter_job_id}_{language}"
        if isinstance(language, str) and language.strip()
        else filter_job_id
    )
    if zone_key not in {expected_zone_key, filter_job_id}:
        raise ValueError(
            "candidate_scope_override.filter_job_id is incompatible with "
            f"zone_match_bundle.zone_config_name ({expected_zone_key!r} vs {zone_key!r})"
        )


def _anchor_block_id(zone: dict[str, Any]) -> str:
    match = zone.get("match") or {}
    anchor = match.get("matched_heading_block_id")
    if not isinstance(anchor, str) or not anchor.strip():
        raise ValueError("matched zone must include match.matched_heading_block_id")
    return anchor.strip()


def _zone_block_ids(zone: dict[str, Any]) -> frozenset[str]:
    block_ids: set[str] = set()
    for group_key in ("blocks", "table_blocks"):
        for block in zone.get(group_key) or []:
            if not isinstance(block, dict):
                continue
            block_id = block.get("block_id")
            if block_id:
                block_ids.add(str(block_id))
    return frozenset(block_ids)


def _anchor_level(zone: dict[str, Any]) -> int | None:
    match = zone.get("match") or {}
    level = match.get("matched_heading_level")
    return level if isinstance(level, int) else None


def _anchor_doc_order_index(
    zone: dict[str, Any],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
) -> int:
    anchor_id = _anchor_block_id(zone)
    block = blocks_by_id.get(anchor_id)
    if block is None:
        return 10**9
    value = block.get("doc_order_index")
    if isinstance(value, int):
        return value
    return 10**9


def canonicalize_ancestor_descendant_zones(
    zones: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Drop descendant heading-zones fully covered by a selected ancestor zone.

    Ancestor/descendant is determined by anchor presence inside the ancestor zone
    span and deeper heading level (larger heading_level number).
    """
    if not zones:
        return []

    zone_block_sets = [_zone_block_ids(zone) for zone in zones]
    drop_indices: set[int] = set()

    for ancestor_index, ancestor in enumerate(zones):
        ancestor_anchor = _anchor_block_id(ancestor)
        ancestor_level = _anchor_level(ancestor)
        ancestor_blocks = zone_block_sets[ancestor_index]

        for descendant_index, descendant in enumerate(zones):
            if descendant_index == ancestor_index:
                continue
            if descendant_index in drop_indices:
                continue

            descendant_anchor = _anchor_block_id(descendant)
            if descendant_anchor == ancestor_anchor:
                continue
            if descendant_anchor not in ancestor_blocks:
                continue

            descendant_level = _anchor_level(descendant)
            if (
                ancestor_level is not None
                and descendant_level is not None
                and descendant_level > ancestor_level
            ):
                drop_indices.add(descendant_index)

    return [zone for index, zone in enumerate(zones) if index not in drop_indices]


def _sort_zones_by_doc_order(
    zones: list[dict[str, Any]],
    *,
    blocks_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        zones,
        key=lambda zone: (
            _anchor_doc_order_index(zone, blocks_by_id=blocks_by_id),
            _anchor_block_id(zone),
        ),
    )


def _renumber_zone_ids(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    renumbered: list[dict[str, Any]] = []
    for index, zone in enumerate(zones, start=1):
        updated = deepcopy(zone)
        updated["zone_id"] = f"Z{index:04d}"
        renumbered.append(updated)
    return renumbered


def _assert_heading_anchor_exists(
    *,
    anchor_block_id: str,
    analysis_bundle: dict[str, Any],
) -> None:
    found = False
    for block in analysis_bundle.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        if str(block.get("block_id") or "") != anchor_block_id:
            continue
        if not is_heading(block):
            raise ValueError(
                f"anchor_block_id {anchor_block_id!r} is not a heading block"
            )
        found = True
        break
    if not found:
        raise ValueError(
            f"anchor_block_id {anchor_block_id!r} not found in analysis_bundle"
        )


def _blocks_by_id_from_manifest(
    block_manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    blocks_by_id: dict[str, dict[str, Any]] = {}
    for group_key in ("blocks", "table_blocks"):
        for block in block_manifest.get(group_key) or []:
            if not isinstance(block, dict):
                continue
            block_id = block.get("block_id")
            if block_id:
                blocks_by_id[str(block_id)] = block
    return blocks_by_id


def _apply_resolved_candidate_scope_identity(
    public_payload: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(public_payload)
    updated["stage"] = RESOLVED_CANDIDATE_SCOPE_STAGE
    updated["input_stage"] = RESOLVED_CANDIDATE_SCOPE_INPUT_STAGE
    updated["pipeline"] = list(RESOLVED_CANDIDATE_SCOPE_PIPELINE)
    return updated


def build_effective_candidate_scope(
    *,
    automatic_zone_match_bundle: dict[str, Any],
    candidate_scope_override: dict[str, Any],
    block_manifest: dict[str, Any],
    analysis_bundle: dict[str, Any],
    effective_run_id: str,
) -> EffectiveCandidateScopeResult:
    """
    Compose resolved candidate scope from manual override input.

    Remove on an unselected anchor is a deterministic no-op.
    """
    assert_candidate_scope_override_safe(candidate_scope_override)
    return _build_resolved_candidate_scope(
        automatic_zone_match_bundle=automatic_zone_match_bundle,
        candidate_scope_input=candidate_scope_override,
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
        effective_run_id=effective_run_id,
    )


def build_resolved_candidate_scope(
    *,
    automatic_zone_match_bundle: dict[str, Any],
    candidate_scope_resolution_input: dict[str, Any],
    block_manifest: dict[str, Any],
    analysis_bundle: dict[str, Any],
    effective_run_id: str,
) -> EffectiveCandidateScopeResult:
    """
    Compose resolved candidate scope for flow checkpoint materialization.

    Allows zero operations for automatic-unchanged selections.
    """
    assert_candidate_scope_resolution_input_safe(candidate_scope_resolution_input)
    return _build_resolved_candidate_scope(
        automatic_zone_match_bundle=automatic_zone_match_bundle,
        candidate_scope_input=candidate_scope_resolution_input,
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
        effective_run_id=effective_run_id,
    )


def _build_resolved_candidate_scope(
    *,
    automatic_zone_match_bundle: dict[str, Any],
    candidate_scope_input: dict[str, Any],
    block_manifest: dict[str, Any],
    analysis_bundle: dict[str, Any],
    effective_run_id: str,
) -> EffectiveCandidateScopeResult:
    normalized_hash = _validate_identity_alignment(
        automatic_zone_match_bundle=automatic_zone_match_bundle,
        candidate_scope_override=candidate_scope_input,
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
    )
    _validate_filter_job_alignment(
        automatic_zone_match_bundle=automatic_zone_match_bundle,
        candidate_scope_override=candidate_scope_input,
    )

    envelope = _zone_envelope_from_bundle(automatic_zone_match_bundle)
    zone_key = envelope.zone_config_name

    operations = candidate_scope_input.get("operations") or []
    applied: list[dict[str, str]] = []

    zones_by_anchor: dict[str, dict[str, Any]] = {}
    for zone in automatic_zone_match_bundle.get("matched_zones") or []:
        if not isinstance(zone, dict):
            continue
        zones_by_anchor[_anchor_block_id(zone)] = deepcopy(zone)

    block_universe = BlockUniverse.from_analysis_bundle(analysis_bundle)
    zone_config = type(
        "EffectiveZoneConfig",
        (),
        {
            "language": envelope.language,
            "zone_config_name": envelope.zone_config_name,
            "zone_config_version": envelope.zone_config_version,
            "policy": type(
                "EffectiveZonePolicy",
                (),
                {"heading_match_mode": envelope.heading_match_mode},
            )(),
        },
    )()

    for operation in operations:
        anchor = _require_str(
            operation.get("anchor_block_id"),
            field="candidate_scope_override.operations[].anchor_block_id",
        )
        op = _require_str(
            operation.get("op"), field="candidate_scope_override.operations[].op"
        )
        applied.append({"anchor_block_id": anchor, "op": op})

        if op == "remove":
            zones_by_anchor.pop(anchor, None)
            continue

        _assert_heading_anchor_exists(
            anchor_block_id=anchor,
            analysis_bundle=analysis_bundle,
        )
        if anchor in zones_by_anchor:
            continue

        raw_zone = materialize_heading_anchor_zone(
            anchor_block_id=anchor,
            content_blocks=list(block_universe.content_blocks),
            table_blocks=list(block_universe.table_blocks),
            zone_config=zone_config,
            match_type=_MANUAL_MATCH_TYPE,
            matched_term=_MANUAL_MATCHED_TERM,
            match_mode=_MANUAL_MATCH_MODE,
        )
        public_zone = export_public_zone(
            raw_zone,
            block_manifest=block_manifest,
        )
        zones_by_anchor[anchor] = public_zone

    blocks_by_id = _blocks_by_id_from_manifest(block_manifest)
    working_zones = list(zones_by_anchor.values())
    working_zones = canonicalize_ancestor_descendant_zones(working_zones)
    working_zones = _sort_zones_by_doc_order(working_zones, blocks_by_id=blocks_by_id)
    working_zones = _renumber_zone_ids(working_zones)

    effective_public = {
        key: value
        for key, value in automatic_zone_match_bundle.items()
        if key not in {"matched_zones", "matched_zone_count"}
    }
    effective_public["matched_zones"] = working_zones
    effective_public["matched_zone_count"] = len(working_zones)
    effective_public["file_hash"] = normalized_hash
    effective_public = _apply_resolved_candidate_scope_identity(effective_public)

    effective_zone_match_bundle = build_zone_match_bundle(effective_public)

    coverage_rows = derive_block_selection_coverage(
        block_manifest=block_manifest,
        public_filter_result=effective_zone_match_bundle,
    )
    effective_coverage_bundle = build_coverage_bundle(
        block_manifest=block_manifest,
        coverage=coverage_rows,
        zone_key=zone_key,
        filter_run_id=effective_run_id,
    )

    return EffectiveCandidateScopeResult(
        effective_zone_match_bundle=effective_zone_match_bundle,
        effective_coverage_bundle=effective_coverage_bundle,
        applied_operations=tuple(applied),
    )


__all__ = [
    "EffectiveCandidateScopeResult",
    "RESOLVED_CANDIDATE_SCOPE_INPUT_STAGE",
    "RESOLVED_CANDIDATE_SCOPE_PIPELINE",
    "RESOLVED_CANDIDATE_SCOPE_STAGE",
    "build_effective_candidate_scope",
    "build_resolved_candidate_scope",
    "canonicalize_ancestor_descendant_zones",
]
