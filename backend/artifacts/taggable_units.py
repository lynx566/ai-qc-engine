"""Canonical aggregate text-unit contract shared from Route through ESP prepare."""

from __future__ import annotations

from typing import Any, Literal

from artifacts.routing.primary_sentence_contract import (
    routed_body_text_from_sentences,
    validate_text_unit_body_consistency,
)

TaggableUnitIssueSeverity = Literal["error", "warning"]

CANONICAL_AGGREGATE_CORE_FIELDS = frozenset(
    {
        "unit_kind",
        "route",
        "route_basis",
        "sentences",
        "source_block_ids",
        "context_block_ids",
        "heading_path",
        "text_refs",
        "source_stage",
        "source_zone_key",
    }
)

_OPTIONAL_PROVENANCE_FIELDS = (
    "filter_job_id",
    "overview_decompose_bundle_id",
    "source_component_ids",
    "source_component_types",
    "source_component_sentences",
    "route_matched_terms",
)


def _ordered_unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_primary_sentences(sentences: Any) -> list[dict[str, Any]]:
    if not isinstance(sentences, list):
        raise ValueError("sentences must be a list")
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for sentence in sentences:
        if not isinstance(sentence, dict):
            continue
        sentence_id = str(sentence.get("sentence_id") or "").strip()
        if not sentence_id:
            raise ValueError("sentences entries must include sentence_id")
        if sentence_id in seen_ids:
            raise ValueError(f"duplicate source sentence id within unit: {sentence_id}")
        seen_ids.add(sentence_id)
        text = str(sentence.get("text") or "")
        source_block_id = str(sentence.get("source_block_id") or "").strip()
        if not source_block_id:
            raise ValueError(
                f"sentences entry {sentence_id!r} must include source_block_id"
            )
        out.append(
            {
                "sentence_id": sentence_id,
                "text": text,
                "source_block_id": source_block_id,
            }
        )
    return out


def canonicalize_aggregate_text_unit(
    unit: dict[str, Any],
    *,
    source_label: str,
) -> dict[str, Any]:
    """Validate and normalize one aggregate text unit into canonical contract."""
    unit_kind = str(unit.get("unit_kind") or "text_unit").strip() or "text_unit"
    if unit_kind != "text_unit":
        raise ValueError(f"{source_label}: unit_kind must be text_unit")
    route = str(unit.get("route") or "").strip()
    if route != "aggregate":
        raise ValueError(f"{source_label}: route must be aggregate")
    route_basis = str(unit.get("route_basis") or "").strip()
    if not route_basis:
        raise ValueError(f"{source_label}: route_basis is required")

    validate_text_unit_body_consistency(unit, unit_path=source_label)

    sentences = _normalize_primary_sentences(unit.get("sentences"))
    if not sentences:
        raise ValueError(f"{source_label}: sentences must be non-empty")

    body_text = routed_body_text_from_sentences(
        sentences,
        source_stage=str(unit.get("source_stage") or "") or None,
    )
    if not body_text.strip():
        raise ValueError(f"{source_label}: sentences must produce non-empty body text")

    source_block_ids = _ordered_unique_strings(unit.get("source_block_ids") or [])
    if not source_block_ids:
        source_block_ids = _ordered_unique_strings(
            [sentence.get("source_block_id") for sentence in sentences]
        )
    if not source_block_ids:
        raise ValueError(f"{source_label}: source_block_ids must be non-empty")

    context_block_ids = _ordered_unique_strings(unit.get("context_block_ids") or [])

    all_source_block_ids = _ordered_unique_strings(
        unit.get("all_source_block_ids") or (source_block_ids + context_block_ids)
    )
    if not all_source_block_ids:
        all_source_block_ids = list(source_block_ids)

    heading_path = [str(item) for item in (unit.get("heading_path") or [])]
    text_refs = [
        dict(text_ref)
        for text_ref in (unit.get("text_refs") or [])
        if isinstance(text_ref, dict)
    ]
    candidate_block_kinds = [
        str(kind)
        for kind in (unit.get("candidate_block_kinds") or [])
        if str(kind or "").strip()
    ]
    source_stage_raw = unit.get("source_stage")
    source_zone_key_raw = unit.get("source_zone_key")

    canonical: dict[str, Any] = {
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": route_basis,
        "heading_path": heading_path,
        "sentences": sentences,
        "source_block_ids": source_block_ids,
        "context_block_ids": context_block_ids,
        "all_source_block_ids": all_source_block_ids,
        "candidate_block_kinds": candidate_block_kinds,
        "text_refs": text_refs,
        "source_stage": (
            str(source_stage_raw).strip()
            if source_stage_raw is not None and str(source_stage_raw).strip()
            else None
        ),
        "source_zone_key": (
            str(source_zone_key_raw).strip()
            if source_zone_key_raw is not None and str(source_zone_key_raw).strip()
            else None
        ),
    }
    for key in _OPTIONAL_PROVENANCE_FIELDS:
        if key in unit:
            canonical[key] = unit[key]
    return canonical


def single_component_provenance(unit: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return optional single-component debug provenance from a canonical unit."""
    component_ids = [
        str(value).strip()
        for value in (unit.get("source_component_ids") or [])
        if str(value).strip()
    ]
    if not component_ids:
        return None, None
    component_id = component_ids[0]
    component_types = [
        str(value).strip()
        for value in (unit.get("source_component_types") or [])
        if str(value).strip()
    ]
    component_type = component_types[0] if component_types else None
    return component_id, component_type


def validate_optional_provenance_metadata(
    unit: dict[str, Any],
    *,
    unit_id: str = "",
) -> list[dict[str, Any]]:
    """Validate optional source metadata does not imply multi-item fan-out."""
    issues: list[dict[str, Any]] = []
    raw_component_ids = [
        str(value).strip()
        for value in (unit.get("source_component_ids") or [])
        if str(value).strip()
    ]
    if len(raw_component_ids) > 1:
        issues.append(
            {
                "code": "aggregate_multiple_source_component_ids",
                "severity": "error",
                "unit_id": unit_id or None,
                "source_component_ids": raw_component_ids,
            }
        )
    elif len(raw_component_ids) != len(set(raw_component_ids)):
        issues.append(
            {
                "code": "aggregate_duplicate_source_component_id",
                "severity": "error",
                "unit_id": unit_id or None,
                "source_component_ids": raw_component_ids,
            }
        )

    raw_component_types = [
        str(value).strip()
        for value in (unit.get("source_component_types") or [])
        if str(value).strip()
    ]
    if raw_component_ids and raw_component_types and len(raw_component_types) != len(
        raw_component_ids
    ):
        issues.append(
            {
                "code": "aggregate_source_component_types_length_mismatch",
                "severity": "warning",
                "unit_id": unit_id or None,
                "source_component_id_count": len(raw_component_ids),
                "source_component_type_count": len(raw_component_types),
            }
        )

    source_sentence_ids = {
        str(sentence.get("sentence_id") or "").strip()
        for sentence in (unit.get("sentences") or [])
        if isinstance(sentence, dict) and str(sentence.get("sentence_id") or "").strip()
    }
    component_sentences = unit.get("source_component_sentences")
    if isinstance(component_sentences, list) and component_sentences:
        for sentence in component_sentences:
            if not isinstance(sentence, dict):
                issues.append(
                    {
                        "code": "aggregate_source_component_sentence_invalid",
                        "severity": "error",
                        "unit_id": unit_id or None,
                    }
                )
                continue
            sentence_id = str(sentence.get("sentence_id") or "").strip()
            if not sentence_id:
                issues.append(
                    {
                        "code": "aggregate_source_component_sentence_missing_id",
                        "severity": "error",
                        "unit_id": unit_id or None,
                    }
                )
                continue
            if sentence_id not in source_sentence_ids:
                issues.append(
                    {
                        "code": "aggregate_source_component_sentence_not_in_unit",
                        "severity": "error",
                        "unit_id": unit_id or None,
                        "sentence_id": sentence_id,
                    }
                )
            if len(raw_component_ids) == 1:
                component_id = raw_component_ids[0]
                if not sentence_id.startswith(f"{component_id}:"):
                    issues.append(
                        {
                            "code": "aggregate_source_component_sentence_prefix_mismatch",
                            "severity": "warning",
                            "unit_id": unit_id or None,
                            "component_id": component_id,
                            "sentence_id": sentence_id,
                        }
                    )
    return issues


def validate_aggregate_text_unit_contract(
    unit: dict[str, Any],
    *,
    unit_id: str = "",
    source_label: str = "aggregate_unit",
) -> list[dict[str, Any]]:
    """Return issue dicts for aggregate text units that violate canonical contract."""
    unit_kind = str(unit.get("unit_kind") or "text_unit").strip() or "text_unit"
    route = str(unit.get("route") or "").strip()
    if unit_kind != "text_unit" or route != "aggregate":
        return []

    issues: list[dict[str, Any]] = []
    try:
        canonicalize_aggregate_text_unit(unit, source_label=source_label)
    except ValueError as exc:
        issues.append(
            {
                "code": "aggregate_unit_contract_violation",
                "severity": "error",
                "unit_id": unit_id or None,
                "detail": str(exc),
            }
        )
    issues.extend(
        validate_optional_provenance_metadata(unit, unit_id=unit_id),
    )
    return issues
