# ruff: noqa: TRY004
"""Aggregate Evidence semantic preparation business logic."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.routing.types import Route
from artifacts.taggable_units import canonicalize_aggregate_text_unit
from core.document.doc_identity import require_bundle_file_hash
from operations.evidence_source_preparation.stage import ProjectionInputRefRecord
from artifacts.routing.primary_sentence_contract import routed_body_text_from_sentences


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def canonicalize_aggregate_route_units(
    units_by_route: dict[Route, list[dict[str, Any]]],
) -> dict[Route, list[dict[str, Any]]]:
    """Apply aggregate text canonicalization after routing (aggregate prepare layer)."""
    result: dict[Route, list[dict[str, Any]]] = {
        route: list(units) for route, units in units_by_route.items()
    }
    for index, unit in enumerate(result["aggregate"]):
        if str(unit.get("unit_kind") or "") != "text_unit":
            continue
        if unit.get("source_stage") == "overview_decompose":
            component_ids = unit.get("source_component_ids") or []
            component_id = str(component_ids[0]) if component_ids else ""
            source_label = f"overview_component:{component_id or '<unknown>'}"
        else:
            source_label = "coverage_unit"
        canonical = canonicalize_aggregate_text_unit(
            unit,
            source_label=source_label,
        )
        unit_id = unit.get("unit_id")
        if unit_id:
            canonical["unit_id"] = unit_id
        result["aggregate"][index] = canonical
    return result


def build_aggregate_shared_metadata(
    *,
    coverage_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
) -> dict[str, Any]:
    coverage_bundle_id = str(coverage_bundle["coverage_bundle_id"])
    file_hash = require_bundle_file_hash(coverage_bundle, label="coverage_bundle")
    doc_meta = dict(doc_meta_bundle["summary"])
    return {
        "coverage_bundle_id": coverage_bundle_id,
        "doc_id": str(coverage_bundle["doc_id"]),
        "file_hash": file_hash,
        "coverage_bundle_ref": {
            "coverage_bundle_id": coverage_bundle_id,
        },
        "block_manifest_ref": {
            "block_manifest_id": str(block_manifest["block_manifest_id"]),
        },
        "doc_meta_ref": {
            "doc_meta_bundle_id": str(doc_meta_bundle["doc_meta_bundle_id"]),
        },
        "zone_key": str(coverage_bundle["zone_key"]),
        "doc_meta": doc_meta,
    }


@dataclass(frozen=True, slots=True)
class ProjectedFanInPrepareContext:
    semantic_module_id: str
    projection_input_refs: tuple[ProjectionInputRefRecord, ...]


def build_projected_fan_in_shared_metadata(
    *,
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    semantic_module_id: str,
) -> dict[str, Any]:
    file_hash = require_bundle_file_hash(block_manifest, label="block_manifest")
    doc_meta = dict(doc_meta_bundle["summary"])
    return {
        "doc_id": str(block_manifest["doc_id"]),
        "file_hash": file_hash,
        "block_manifest_ref": {
            "block_manifest_id": str(block_manifest["block_manifest_id"]),
        },
        "doc_meta_ref": {
            "doc_meta_bundle_id": str(doc_meta_bundle["doc_meta_bundle_id"]),
        },
        "doc_meta": doc_meta,
        "semantic_module_id": semantic_module_id,
    }


def heading_scope_signature(unit: Mapping[str, Any]) -> tuple[Any, ...]:
    source_zone_key = str(unit.get("source_zone_key") or "")
    heading_path = tuple(str(item) for item in (unit.get("heading_path") or []))
    context_block_ids = tuple(
        str(block_id) for block_id in (unit.get("context_block_ids") or []) if block_id
    )
    if context_block_ids:
        return (source_zone_key, context_block_ids, heading_path)
    return (source_zone_key, heading_path)


def compact_sentences_from_aggregate_unit(unit: Mapping[str, Any]) -> list[dict[str, str]]:
    sentences: list[dict[str, str]] = []
    seen: set[str] = set()
    primary_sentences = unit.get("sentences")
    if not isinstance(primary_sentences, list):
        raise ValueError(
            f"unit {unit.get('unit_id')!r} must include sentences as a list"
        )
    for sentence in primary_sentences:
        if not isinstance(sentence, dict):
            continue
        sentence_id = _require_str(
            sentence.get("sentence_id"),
            field=f"unit {unit.get('unit_id')!r} sentences.sentence_id",
        )
        text = _require_str(
            sentence.get("text"),
            field=f"unit {unit.get('unit_id')!r} sentences[{sentence_id!r}].text",
        )
        if sentence_id in seen:
            raise ValueError(
                f"duplicate sentence_id {sentence_id!r} in unit {unit.get('unit_id')!r}"
            )
        seen.add(sentence_id)
        sentences.append({"sentence_id": sentence_id, "text": text})
    if not sentences:
        raise ValueError(
            f"unit {unit.get('unit_id')!r} must include at least one sentence"
        )
    return sentences


def unit_body_text_from_sentences(unit: Mapping[str, Any]) -> str:
    """Derive one TU body text from routed primary ``sentences[]``."""

    body_text = routed_body_text_from_sentences(
        unit.get("sentences") or [],
        source_stage=str(unit.get("source_stage") or "") or None,
    )
    if not body_text.strip():
        raise ValueError(
            "scope_assessment_evidence_empty_unit_text: "
            f"unit {unit.get('unit_id', '<unknown>')!r} sentences must produce non-empty body text"
        )
    return body_text


def build_heading_scopes_from_aggregate_units(
    aggregate_units: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    scopes: list[dict[str, Any]] = []
    current_signature: tuple[Any, ...] | None = None
    current_scope: dict[str, Any] | None = None
    scope_index = 0

    for unit in aggregate_units:
        if not isinstance(unit, dict):
            raise ValueError("aggregate_units entries must be objects")
        unit_id = _require_str(unit.get("unit_id"), field="aggregate unit.unit_id")
        compact_sentences = compact_sentences_from_aggregate_unit(unit)

        signature = heading_scope_signature(unit)
        heading_path = [str(item) for item in (unit.get("heading_path") or [])]
        if current_scope is None or signature != current_signature:
            scope_index += 1
            current_signature = signature
            current_scope = {
                "scope_id": f"HS{scope_index:04d}",
                "heading_path": heading_path,
                "units": [],
            }
            scopes.append(current_scope)
        else:
            if list(current_scope.get("heading_path") or []) != heading_path:
                raise ValueError(
                    f"unit {unit_id!r}: heading_path changed within the same heading scope signature"
                )

        current_scope["units"].append(
            {
                "unit_id": unit_id,
                "sentences": compact_sentences,
            }
        )

    if not scopes:
        raise ValueError("heading_scopes must be non-empty")
    return scopes


def build_unit_assessment_evidence_text(unit: Mapping[str, Any]) -> str:
    """Build one TU's scope evidence text from routed primary body sentences."""

    return unit_body_text_from_sentences(unit)


def build_scope_assessment_evidence_text(
    *,
    ordered_unit_ids: Sequence[str],
    unit_by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    """Join member TU assessment evidence with ``\\n\\n`` (canonical Scope rule)."""

    seen_unit_ids: set[str] = set()
    parts: list[str] = []
    for unit_id in ordered_unit_ids:
        token = str(unit_id or "").strip()
        if not token:
            raise ValueError("scope_assessment_evidence_missing_unit: unit_id is required")
        if token in seen_unit_ids:
            raise ValueError(
                f"scope_assessment_evidence_duplicate_unit: duplicate unit_id {token!r}"
            )
        seen_unit_ids.add(token)
        unit = unit_by_id.get(token)
        if not isinstance(unit, dict):
            raise ValueError(
                f"scope_assessment_evidence_missing_unit: missing unit_id {token!r}"
            )
        parts.append(build_unit_assessment_evidence_text(unit))
    scope_text = "\n\n".join(parts)
    if not scope_text:
        raise ValueError(
            "scope_assessment_evidence_empty_scope_text: scope candidate_text must be non-empty"
        )
    return scope_text


def build_scope_candidate_text(
    *,
    ordered_unit_ids: Sequence[str],
    unit_candidate_text_by_id: Mapping[str, str],
) -> str:
    """Join member TU candidate_text with ``\\n\\n`` (single canonical Scope rule)."""
    seen_unit_ids: set[str] = set()
    parts: list[str] = []
    for unit_id in ordered_unit_ids:
        token = str(unit_id or "").strip()
        if not token:
            raise ValueError("scope_assessment_evidence_missing_unit: unit_id is required")
        if token in seen_unit_ids:
            raise ValueError(
                f"scope_assessment_evidence_duplicate_unit: duplicate unit_id {token!r}"
            )
        seen_unit_ids.add(token)
        if token not in unit_candidate_text_by_id:
            raise ValueError(
                f"scope_assessment_evidence_missing_unit: missing unit_id {token!r}"
            )
        candidate_text = unit_candidate_text_by_id[token]
        if not isinstance(candidate_text, str):
            raise ValueError(
                "scope_assessment_evidence_invalid_unit_text: "
                f"unit {token!r} candidate_text must be str"
            )
        if not candidate_text:
            raise ValueError(
                "scope_assessment_evidence_empty_unit_text: "
                f"unit {token!r} candidate_text must be non-empty"
            )
        parts.append(candidate_text)
    scope_text = "\n\n".join(parts)
    if not scope_text:
        raise ValueError(
            "scope_assessment_evidence_empty_scope_text: scope candidate_text must be non-empty"
        )
    return scope_text


def attach_assessment_evidence_to_heading_scopes(
    heading_scopes: list[dict[str, Any]],
    aggregate_units: Sequence[Mapping[str, Any]],
) -> None:
    """Populate ``assessment_evidence.candidate_text`` on each heading scope."""
    unit_by_id: dict[str, dict[str, Any]] = {}
    for unit in aggregate_units:
        if not isinstance(unit, dict):
            raise ValueError("aggregate_units entries must be objects")
        unit_id = _require_str(unit.get("unit_id"), field="aggregate unit.unit_id")
        unit_body_text_from_sentences(unit)
        unit_by_id[unit_id] = unit

    for scope in heading_scopes:
        ordered_unit_ids = [
            _require_str(unit.get("unit_id"), field="heading_scopes.units.unit_id")
            for unit in (scope.get("units") or [])
            if isinstance(unit, dict)
        ]
        scope["assessment_evidence"] = {
            "candidate_text": build_scope_assessment_evidence_text(
                ordered_unit_ids=ordered_unit_ids,
                unit_by_id=unit_by_id,
            )
        }


def unit_provenance_from_aggregate_unit(unit: Mapping[str, Any]) -> dict[str, Any]:
    unit_id = _require_str(unit.get("unit_id"), field="unit.unit_id")
    source_block_ids = [
        str(block_id) for block_id in (unit.get("source_block_ids") or []) if block_id
    ]
    if not source_block_ids:
        raise ValueError(f"unit {unit_id!r}: source_block_ids must be non-empty")
    primary_sentences = [
        dict(sentence)
        for sentence in (unit.get("sentences") or [])
        if isinstance(sentence, dict)
    ]
    if not primary_sentences:
        raise ValueError(f"unit {unit_id!r}: sentences must be non-empty")
    body_text = unit_body_text_from_sentences(unit)
    provenance: dict[str, Any] = {
        "source_block_ids": source_block_ids,
        "source_sentence_ids": [
            str(sentence.get("sentence_id") or "")
            for sentence in primary_sentences
            if sentence.get("sentence_id")
        ],
        "sentence_source_block_ids": [
            str(sentence.get("source_block_id") or "")
            for sentence in primary_sentences
            if sentence.get("source_block_id")
        ],
        "context_block_ids": [
            str(block_id) for block_id in (unit.get("context_block_ids") or []) if block_id
        ],
        "all_source_block_ids": [
            str(block_id)
            for block_id in (unit.get("all_source_block_ids") or [])
            if block_id
        ],
        "candidate_block_kinds": list(unit.get("candidate_block_kinds") or []),
        "text_refs": [
            dict(text_ref)
            for text_ref in (unit.get("text_refs") or [])
            if isinstance(text_ref, dict)
        ],
        "source_stage": str(unit.get("source_stage") or ""),
        "source_zone_key": str(unit.get("source_zone_key") or ""),
        "filter_job_id": str(unit.get("filter_job_id") or ""),
        "route_basis": str(unit.get("route_basis") or ""),
        "route_matched_terms": list(unit.get("route_matched_terms") or []),
        "source_component_ids": list(unit.get("source_component_ids") or []),
        "overview_decompose_bundle_id": unit.get("overview_decompose_bundle_id"),
        "candidate_text": body_text,
    }
    return provenance


def build_unit_provenance_map(
    aggregate_units: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    provenance: dict[str, Any] = {}
    for unit in aggregate_units:
        unit_id = _require_str(unit.get("unit_id"), field="aggregate unit.unit_id")
        provenance[unit_id] = unit_provenance_from_aggregate_unit(unit)
    return provenance


def _route_stats_for_aggregate(units: list[dict[str, Any]]) -> dict[str, int]:
    return {"unit_count": len(units)}


def prepare_aggregate_evidence_semantic_result(
    *,
    aggregate_bundle: Mapping[str, Any],
    coverage_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    assessment_profile_ref: str,
    instructions: str,
    projected_fan_in: ProjectedFanInPrepareContext | None = None,
) -> dict[str, Any]:
    """Build unwrapped aggregate prepare semantic result from routed aggregate units."""
    raw_units = [
        dict(unit)
        for unit in (aggregate_bundle.get("units") or [])
        if isinstance(unit, dict)
    ]
    units_by_route: dict[Route, list[dict[str, Any]]] = {
        "aggregate": raw_units,
        "table": [],
        "case": [],
        "unknown": [],
    }
    canonicalized = canonicalize_aggregate_route_units(units_by_route)
    aggregate_units = [dict(unit) for unit in canonicalized["aggregate"]]

    if projected_fan_in is not None:
        base = build_projected_fan_in_shared_metadata(
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
            semantic_module_id=projected_fan_in.semantic_module_id,
        )
    else:
        if coverage_bundle is None:
            raise ValueError("coverage_bundle is required when projected_fan_in is None")
        base = build_aggregate_shared_metadata(
            coverage_bundle=coverage_bundle,
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
        )

    profile_ref = _require_str(assessment_profile_ref, field="assessment_profile_ref")
    resolved_instructions = _require_str(instructions, field="instructions")

    shared_metadata: dict[str, Any] = {
        **{key: base[key] for key in base if key != "coverage_bundle_id"},
        "route": "aggregate",
        "route_stats": _route_stats_for_aggregate(aggregate_units),
        "instructions": resolved_instructions,
        "assessment_profile_ref": profile_ref,
    }
    if "coverage_bundle_id" in base:
        shared_metadata["coverage_bundle_id"] = base["coverage_bundle_id"]

    heading_scopes = build_heading_scopes_from_aggregate_units(aggregate_units)
    attach_assessment_evidence_to_heading_scopes(heading_scopes, aggregate_units)
    unit_provenance = build_unit_provenance_map(aggregate_units)

    return {
        "canonical_aggregate_units": aggregate_units,
        "heading_scopes": heading_scopes,
        "unit_provenance": unit_provenance,
        "shared_metadata": shared_metadata,
    }
