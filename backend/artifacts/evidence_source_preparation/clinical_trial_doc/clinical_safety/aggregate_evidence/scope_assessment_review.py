"""Scope assessment human-review artifact contract and writer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    validate_assessment_runtime_context,
    validate_scoped_assessment_cross_artifacts,
)

SCOPE_ASSESSMENT_REVIEW_FILENAME = "scope_assessment_review.json"
SCOPE_ASSESSMENT_REVIEW_SCHEMA_VERSION = "0.3.0"
SCOPE_ASSESSMENT_REVIEW_ARTIFACT_TYPE = "scope_assessment_review"

_ASSESSMENT_FIELDS = (
    "product_context_role",
    "unit_form",
    "safety_role",
    "route_qc",
)


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_id_suffix(llm_input_bundle_id: str) -> str:
    if llm_input_bundle_id.startswith("llm_input_"):
        return llm_input_bundle_id.removeprefix("llm_input_")
    return llm_input_bundle_id


def build_scope_assessment_review_id(*, llm_input_bundle_id: str) -> str:
    return f"scope_assessment_review_{_normalize_id_suffix(llm_input_bundle_id)}"


def build_scope_assessments_id(*, llm_input_bundle_id: str) -> str:
    return f"scope_assessments_{_normalize_id_suffix(llm_input_bundle_id)}"


def _source_ref_dict(
    value: Any,
    *,
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return dict(value)


def _append_dedup(values: list[str], token: str) -> None:
    if token and token not in values:
        values.append(token)


def _normalize_scope_sentences(
    unit: Mapping[str, Any],
    *,
    scope_id: str,
    unit_id: str,
) -> list[dict[str, str]]:
    sentences = unit.get("sentences")
    if not isinstance(sentences, list):
        raise ValueError(
            f"scope_review_source_unit_sentences_mismatch: "
            f"scope {scope_id!r} unit {unit_id!r} sentences must be a list"
        )
    normalized: list[dict[str, str]] = []
    for index, sentence in enumerate(sentences):
        if not isinstance(sentence, Mapping):
            raise ValueError(
                f"scope_review_source_unit_sentences_mismatch: "
                f"scope {scope_id!r} unit {unit_id!r} sentences[{index}] must be an object"
            )
        sentence_id = _require_non_empty_str(
            sentence.get("sentence_id"),
            field=f"heading_scopes[{scope_id!r}].units[{unit_id!r}].sentences[{index}].sentence_id",
        )
        text = sentence.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError(
                f"scope_review_source_unit_sentences_mismatch: "
                f"scope {scope_id!r} unit {unit_id!r} sentences[{index}].text must be non-empty string"
            )
        normalized.append({"sentence_id": sentence_id, "text": text})
    return normalized


def build_scope_review_source_block_ids(
    source_units: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Expand unit block IDs in order, deduplicating by first appearance."""
    block_ids: list[str] = []
    for source_unit in source_units:
        unit_block_ids = source_unit.get("source_block_ids")
        if not isinstance(unit_block_ids, list):
            raise ValueError("scope_review_source_block_ids_mismatch: source_block_ids must be list")
        for block_id in unit_block_ids:
            _append_dedup(block_ids, str(block_id or "").strip())
    return block_ids


def build_scope_review_source_units(
    *,
    assessment_scope: Mapping[str, Any],
    runtime_unit_provenance_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build hierarchical source-unit evidence for one Scope review item."""
    scope_id = _require_non_empty_str(assessment_scope.get("scope_id"), field="scope_id")
    units = [
        unit
        for unit in (assessment_scope.get("units") or [])
        if isinstance(unit, Mapping) and str(unit.get("unit_id") or "").strip()
    ]
    if not units:
        raise ValueError(
            f"scope_review_source_unit_missing: scope {scope_id!r} has no member units"
        )

    source_units: list[dict[str, Any]] = []
    for unit in units:
        unit_id = _require_non_empty_str(unit.get("unit_id"), field="heading_scopes.units.unit_id")
        provenance = runtime_unit_provenance_by_id.get(unit_id)
        if not isinstance(provenance, Mapping):
            raise ValueError(
                f"scope_review_source_unit_missing: missing unit_provenance for "
                f"scope {scope_id!r} unit {unit_id!r}"
            )

        candidate_text = provenance.get("candidate_text")
        if not isinstance(candidate_text, str) or not candidate_text:
            raise ValueError(
                f"scope_review_source_unit_text_mismatch: scope {scope_id!r} unit {unit_id!r} "
                "candidate_text must be non-empty string"
            )

        source_block_ids_raw = provenance.get("source_block_ids")
        if not isinstance(source_block_ids_raw, list) or not source_block_ids_raw:
            raise ValueError(
                f"scope_review_source_unit_blocks_mismatch: scope {scope_id!r} unit {unit_id!r} "
                "source_block_ids must be a non-empty list"
            )
        source_block_ids = [str(item) for item in source_block_ids_raw]

        sentences = _normalize_scope_sentences(unit, scope_id=scope_id, unit_id=unit_id)
        source_units.append(
            {
                "unit_id": unit_id,
                "source_block_ids": source_block_ids,
                "text": candidate_text,
                "sentences": sentences,
            }
        )

    return source_units


def _find_assessment_scope(
    *,
    scope_id: str,
    assessment_input: Mapping[str, Any],
) -> Mapping[str, Any]:
    for scope in assessment_input.get("heading_scopes") or []:
        if isinstance(scope, Mapping) and str(scope.get("scope_id") or "") == scope_id:
            return scope
    raise ValueError(
        f"scope_review_source_unit_missing: scope {scope_id!r} not found in assessment_input"
    )


def validate_scope_review_projection(
    *,
    review_item: Mapping[str, Any],
    assessment_scope: Mapping[str, Any],
    runtime_unit_provenance_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    """Validate one review item against assessment_input and runtime provenance."""
    scope_id = _require_non_empty_str(review_item.get("scope_id"), field="scope_id")
    assessment_scope_id = _require_non_empty_str(
        assessment_scope.get("scope_id"),
        field="assessment_scope.scope_id",
    )
    if scope_id != assessment_scope_id:
        raise ValueError(
            f"scope_review_source_unit_ids_mismatch: review scope {scope_id!r} "
            f"!= assessment scope {assessment_scope_id!r}"
        )

    expected_source_units = build_scope_review_source_units(
        assessment_scope=assessment_scope,
        runtime_unit_provenance_by_id=runtime_unit_provenance_by_id,
    )
    expected_source_unit_ids = [unit["unit_id"] for unit in expected_source_units]
    expected_source_block_ids = build_scope_review_source_block_ids(expected_source_units)

    actual_source_unit_ids = review_item.get("source_unit_ids")
    if actual_source_unit_ids != expected_source_unit_ids:
        raise ValueError(
            f"scope_review_source_unit_ids_mismatch: scope {scope_id!r} "
            f"expected source_unit_ids {expected_source_unit_ids!r}, "
            f"got {actual_source_unit_ids!r}"
        )

    actual_source_block_ids = review_item.get("source_block_ids")
    if actual_source_block_ids != expected_source_block_ids:
        raise ValueError(
            f"scope_review_source_block_ids_mismatch: scope {scope_id!r} "
            f"expected source_block_ids {expected_source_block_ids!r}, "
            f"got {actual_source_block_ids!r}"
        )

    evidence = _source_ref_dict(review_item.get("evidence"), field="items[].evidence")
    actual_source_units = evidence.get("source_units")
    if actual_source_units != expected_source_units:
        raise ValueError(
            f"scope_review_source_unit_sentences_mismatch: scope {scope_id!r} "
            "evidence.source_units does not match assessment/runtime projection"
        )

    evidence_obj = assessment_scope.get("assessment_evidence")
    if not isinstance(evidence_obj, Mapping):
        raise ValueError(
            f"scope_review_scope_text_mismatch: scope {scope_id!r} assessment_evidence must be object"
        )
    expected_scope_text = evidence_obj.get("candidate_text")
    if not isinstance(expected_scope_text, str) or not expected_scope_text:
        raise ValueError(
            f"scope_review_scope_text_mismatch: scope {scope_id!r} candidate_text must be non-empty"
        )
    actual_scope_text = evidence.get("text")
    if actual_scope_text != expected_scope_text:
        raise ValueError(
            f"scope_review_scope_text_mismatch: scope {scope_id!r} evidence.text "
            "does not match assessment_evidence.candidate_text"
        )


def _build_review_item(
    *,
    scope_assessment: Mapping[str, Any],
    scope_processing: Mapping[str, Any],
    assessment_scope: Mapping[str, Any],
    runtime_unit_provenance_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    scope_id = _require_non_empty_str(scope_assessment.get("scope_id"), field="scope_id")
    processing_scope_id = _require_non_empty_str(
        scope_processing.get("scope_id"),
        field="scope_processing.scope_id",
    )
    if processing_scope_id != scope_id:
        raise ValueError("scope_assessment_trace scope_id order mismatch with scope_assessments")

    evidence_obj = assessment_scope.get("assessment_evidence")
    if not isinstance(evidence_obj, Mapping):
        raise ValueError(
            f"scope_review_scope_text_mismatch: scope {scope_id!r} assessment_evidence must be object"
        )
    evidence_text = evidence_obj.get("candidate_text")
    if not isinstance(evidence_text, str):
        raise ValueError(
            f"scope_review_scope_text_mismatch: scope {scope_id!r} candidate_text must be string"
        )

    source_units = build_scope_review_source_units(
        assessment_scope=assessment_scope,
        runtime_unit_provenance_by_id=runtime_unit_provenance_by_id,
    )
    source_unit_ids = [unit["unit_id"] for unit in source_units]
    source_block_ids = build_scope_review_source_block_ids(source_units)

    assessment = {field: scope_assessment.get(field) for field in _ASSESSMENT_FIELDS}
    route_qc = assessment.get("route_qc")
    if not isinstance(route_qc, Mapping):
        raise ValueError("scope_assessment.route_qc must be an object")
    route_mismatch = route_qc.get("route_mismatch")
    if not isinstance(route_mismatch, bool):
        raise ValueError("scope_assessment.route_qc.route_mismatch must be boolean")

    flags = scope_assessment.get("post_llm_validation_flags")
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        raise ValueError("scope_assessment.post_llm_validation_flags must be list[str]")

    review_item = {
        "scope_id": scope_id,
        "heading_path": [str(item) for item in (scope_assessment.get("heading_path") or [])],
        "source_unit_ids": source_unit_ids,
        "source_block_ids": source_block_ids,
        "evidence": {
            "text": evidence_text,
            "source_units": source_units,
        },
        "assessment": assessment,
        "review_signals": {
            "post_llm_validation_flags": list(flags),
            "route_mismatch": route_mismatch,
        },
    }
    validate_scope_review_projection(
        review_item=review_item,
        assessment_scope=assessment_scope,
        runtime_unit_provenance_by_id=runtime_unit_provenance_by_id,
    )
    return review_item


def build_scope_assessment_review_envelope(
    *,
    scope_assessments: Mapping[str, Any],
    scope_assessment_trace: Mapping[str, Any],
    scope_assessments_path: str,
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
) -> dict[str, Any]:
    validate_assessment_runtime_context(assessment_runtime_context)
    validate_scoped_assessment_cross_artifacts(assessment_input, assessment_runtime_context)

    source_input_ref = _source_ref_dict(
        scope_assessments.get("source_assessment_input_ref"),
        field="scope_assessments.source_assessment_input_ref",
    )
    llm_input_bundle_id = _require_non_empty_str(
        source_input_ref.get("llm_input_bundle_id"),
        field="source_assessment_input_ref.llm_input_bundle_id",
    )
    source_runtime_context_ref = _source_ref_dict(
        scope_assessments.get("source_assessment_runtime_context_ref"),
        field="scope_assessments.source_assessment_runtime_context_ref",
    )
    _require_non_empty_str(
        source_runtime_context_ref.get("assessment_runtime_context_id"),
        field="source_assessment_runtime_context_ref.assessment_runtime_context_id",
    )

    provenance_map = assessment_runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        raise ValueError("unit_provenance must be an object")
    runtime_unit_provenance_by_id = {
        str(unit_id): provenance
        for unit_id, provenance in provenance_map.items()
        if isinstance(provenance, Mapping)
    }

    scope_items = scope_assessments.get("scope_assessments")
    trace_processing = scope_assessment_trace.get("scope_processing")
    if not isinstance(scope_items, list):
        raise ValueError("scope_assessments.scope_assessments must be a list")
    if not isinstance(trace_processing, list):
        raise ValueError("scope_assessment_trace.scope_processing must be a list")
    if len(scope_items) != len(trace_processing):
        raise ValueError("scope_assessment_trace.scope_processing count mismatch")

    review_items = [
        _build_review_item(
            scope_assessment=scope_assessment,
            scope_processing=scope_processing,
            assessment_scope=_find_assessment_scope(
                scope_id=_require_non_empty_str(
                    scope_assessment.get("scope_id"),
                    field="scope_assessment.scope_id",
                ),
                assessment_input=assessment_input,
            ),
            runtime_unit_provenance_by_id=runtime_unit_provenance_by_id,
        )
        for scope_assessment, scope_processing in zip(scope_items, trace_processing, strict=True)
    ]
    expected_scope_ids = [str(item.get("scope_id") or "") for item in scope_items]
    review_scope_ids = [str(item.get("scope_id") or "") for item in review_items]
    if review_scope_ids != expected_scope_ids:
        raise ValueError("scope_assessment_review item order must match scope_assessments order")

    return {
        "artifact_type": SCOPE_ASSESSMENT_REVIEW_ARTIFACT_TYPE,
        "schema_version": SCOPE_ASSESSMENT_REVIEW_SCHEMA_VERSION,
        "scope_assessment_review_id": build_scope_assessment_review_id(
            llm_input_bundle_id=llm_input_bundle_id
        ),
        "doc_id": scope_assessments.get("doc_id"),
        "assessment_profile_name": scope_assessments.get("assessment_profile_name"),
        "source_assessment_output_ref": {
            "artifact_type": "scope_assessments",
            "scope_assessments_id": build_scope_assessments_id(
                llm_input_bundle_id=llm_input_bundle_id
            ),
            "path": scope_assessments_path,
        },
        "source_assessment_input_ref": source_input_ref,
        "source_assessment_runtime_context_ref": source_runtime_context_ref,
        "items": review_items,
    }


def validate_scope_assessment_review_envelope(payload: Mapping[str, Any]) -> None:
    expected_top_level = {
        "artifact_type",
        "schema_version",
        "scope_assessment_review_id",
        "doc_id",
        "assessment_profile_name",
        "source_assessment_output_ref",
        "source_assessment_input_ref",
        "source_assessment_runtime_context_ref",
        "items",
    }
    keys = set(payload.keys())
    if keys != expected_top_level:
        missing = sorted(expected_top_level - keys)
        extra = sorted(keys - expected_top_level)
        raise ValueError(f"invalid scope_assessment_review fields: missing={missing}, extra={extra}")

    if payload.get("artifact_type") != SCOPE_ASSESSMENT_REVIEW_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {SCOPE_ASSESSMENT_REVIEW_ARTIFACT_TYPE!r}"
        )
    if payload.get("schema_version") != SCOPE_ASSESSMENT_REVIEW_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {SCOPE_ASSESSMENT_REVIEW_SCHEMA_VERSION!r}"
        )
    _require_non_empty_str(
        payload.get("scope_assessment_review_id"),
        field="scope_assessment_review_id",
    )
    _require_non_empty_str(payload.get("doc_id"), field="doc_id")
    _require_non_empty_str(
        payload.get("assessment_profile_name"),
        field="assessment_profile_name",
    )

    output_ref = _source_ref_dict(
        payload.get("source_assessment_output_ref"),
        field="source_assessment_output_ref",
    )
    if set(output_ref.keys()) != {"artifact_type", "scope_assessments_id", "path"}:
        raise ValueError("source_assessment_output_ref has invalid fields")
    if output_ref.get("artifact_type") != "scope_assessments":
        raise ValueError("source_assessment_output_ref.artifact_type must be 'scope_assessments'")
    _require_non_empty_str(
        output_ref.get("scope_assessments_id"),
        field="source_assessment_output_ref.scope_assessments_id",
    )
    _require_non_empty_str(output_ref.get("path"), field="source_assessment_output_ref.path")

    input_ref = _source_ref_dict(
        payload.get("source_assessment_input_ref"),
        field="source_assessment_input_ref",
    )
    _require_non_empty_str(
        input_ref.get("llm_input_bundle_id"),
        field="source_assessment_input_ref.llm_input_bundle_id",
    )

    runtime_ref = _source_ref_dict(
        payload.get("source_assessment_runtime_context_ref"),
        field="source_assessment_runtime_context_ref",
    )
    _require_non_empty_str(
        runtime_ref.get("assessment_runtime_context_id"),
        field="source_assessment_runtime_context_ref.assessment_runtime_context_id",
    )
    _require_non_empty_str(
        runtime_ref.get("path"),
        field="source_assessment_runtime_context_ref.path",
    )

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("items entries must be objects")
        expected_item_fields = {
            "scope_id",
            "heading_path",
            "source_unit_ids",
            "source_block_ids",
            "evidence",
            "assessment",
            "review_signals",
        }
        if set(item.keys()) != expected_item_fields:
            raise ValueError("scope_assessment_review item has invalid fields")
        _require_non_empty_str(item.get("scope_id"), field="items[].scope_id")
        for list_field in (
            "heading_path",
            "source_unit_ids",
            "source_block_ids",
        ):
            value = item.get(list_field)
            if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
                raise ValueError(f"items[].{list_field} must be list[str]")

        evidence = _source_ref_dict(item.get("evidence"), field="items[].evidence")
        if set(evidence.keys()) != {"text", "source_units"}:
            raise ValueError("items[].evidence has invalid fields")
        if not isinstance(evidence.get("text"), str):
            raise ValueError("items[].evidence.text must be string")
        source_units = evidence.get("source_units")
        if not isinstance(source_units, list) or not source_units:
            raise ValueError("items[].evidence.source_units must be a non-empty list")
        for source_unit in source_units:
            if not isinstance(source_unit, Mapping):
                raise ValueError("items[].evidence.source_units entries must be objects")
            if set(source_unit.keys()) != {"unit_id", "source_block_ids", "text", "sentences"}:
                raise ValueError("items[].evidence.source_units entry has invalid fields")
            _require_non_empty_str(
                source_unit.get("unit_id"),
                field="items[].evidence.source_units[].unit_id",
            )
            unit_block_ids = source_unit.get("source_block_ids")
            if not isinstance(unit_block_ids, list) or not unit_block_ids:
                raise ValueError(
                    "items[].evidence.source_units[].source_block_ids must be a non-empty list"
                )
            if not all(isinstance(entry, str) for entry in unit_block_ids):
                raise ValueError(
                    "items[].evidence.source_units[].source_block_ids must be list[str]"
                )
            unit_text = source_unit.get("text")
            if not isinstance(unit_text, str) or not unit_text:
                raise ValueError(
                    "items[].evidence.source_units[].text must be a non-empty string"
                )
            sentences = source_unit.get("sentences")
            if not isinstance(sentences, list):
                raise ValueError("items[].evidence.source_units[].sentences must be list")
            for sentence in sentences:
                if not isinstance(sentence, Mapping):
                    raise ValueError(
                        "items[].evidence.source_units[].sentences entries must be objects"
                    )
                if set(sentence.keys()) != {"sentence_id", "text"}:
                    raise ValueError(
                        "items[].evidence.source_units[].sentences entry has invalid fields"
                    )
                _require_non_empty_str(
                    sentence.get("sentence_id"),
                    field="items[].evidence.source_units[].sentences[].sentence_id",
                )
                if not isinstance(sentence.get("text"), str) or not sentence.get("text"):
                    raise ValueError(
                        "items[].evidence.source_units[].sentences[].text must be non-empty string"
                    )

        source_unit_ids = item.get("source_unit_ids")
        projected_unit_ids = [
            str(source_unit.get("unit_id") or "")
            for source_unit in source_units
            if isinstance(source_unit, Mapping)
        ]
        if source_unit_ids != projected_unit_ids:
            raise ValueError("items[].source_unit_ids must match evidence.source_units unit order")

        projected_block_ids = build_scope_review_source_block_ids(source_units)
        if item.get("source_block_ids") != projected_block_ids:
            raise ValueError(
                "items[].source_block_ids must match deduplicated evidence.source_units block order"
            )

        assessment = _source_ref_dict(item.get("assessment"), field="items[].assessment")
        if set(assessment.keys()) != set(_ASSESSMENT_FIELDS):
            raise ValueError("items[].assessment has invalid fields")

        signals = _source_ref_dict(
            item.get("review_signals"),
            field="items[].review_signals",
        )
        if set(signals.keys()) != {"post_llm_validation_flags", "route_mismatch"}:
            raise ValueError("items[].review_signals has invalid fields")
        flags = signals.get("post_llm_validation_flags")
        if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
            raise ValueError("items[].review_signals.post_llm_validation_flags must be list[str]")
        if not isinstance(signals.get("route_mismatch"), bool):
            raise ValueError("items[].review_signals.route_mismatch must be boolean")


def write_scope_assessment_review(
    output_dir: Path | str,
    payload: Mapping[str, Any],
) -> Path:
    from runtime.io import save_json

    out_path = Path(output_dir).resolve() / SCOPE_ASSESSMENT_REVIEW_FILENAME
    save_json(out_path, payload)
    return out_path
