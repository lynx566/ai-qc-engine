# ruff: noqa: TRY004
"""Deterministic aggregate-evidence bundle assembly from ESP internal artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    build_aggregate_evidence_source_bundle,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    validate_assessment_runtime_context,
    validate_scoped_assessment_identity,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_STATUSES,
    validate_heading_scope_eligibility,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import validate_assessment_input
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import validate_scope_assessments_envelope

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceAssemblyExecution,
    AggregateEvidenceAssemblyStats,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.document_type import (
    canonicalize_aggregate_evidence_document_type,
)

_IDENTITY_FIELDS = ("doc_id", "file_hash")
_OPTIONAL_IDENTITY_FIELDS = ("zone_key",)
INCLUDED_ELIGIBILITY_STATUSES = frozenset({"auto_included", "review_ambiguous"})


def assemble_aggregate_evidence_source_bundle(
    *,
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
    scope_assessments: Mapping[str, Any],
    heading_scope_eligibility: Mapping[str, Any],
) -> AggregateEvidenceAssemblyExecution:
    """Join four ESP internal artifacts into aggregate_evidence_source_bundle (no LLM)."""
    validate_assessment_input(assessment_input)
    validate_assessment_runtime_context(assessment_runtime_context)
    validate_scoped_assessment_identity(assessment_input, assessment_runtime_context)
    validate_scope_assessments_envelope(scope_assessments)
    validate_heading_scope_eligibility(
        heading_scope_eligibility,
        source_scope_assessments_payload=scope_assessments,
    )

    _validate_cross_identity(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=heading_scope_eligibility,
    )

    assessment_by_scope_id = _index_scope_assessments(scope_assessments)
    eligibility_by_scope_id = _index_eligibility_entries(heading_scope_eligibility)
    provenance_map = _require_unit_provenance(assessment_runtime_context)

    canonical_scopes = assessment_input.get("heading_scopes") or []
    if not isinstance(canonical_scopes, list):
        raise ValueError("assessment_input.heading_scopes must be a list")

    _validate_scope_join(
        canonical_scopes=canonical_scopes,
        assessment_by_scope_id=assessment_by_scope_id,
        eligibility_by_scope_id=eligibility_by_scope_id,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=heading_scope_eligibility,
    )

    assembled_scopes: list[dict[str, Any]] = []
    auto_included_count = 0
    review_ambiguous_count = 0
    excluded_counts: dict[str, int] = {}

    for scope_index, scope in enumerate(canonical_scopes):
        if not isinstance(scope, dict):
            raise ValueError(f"heading_scopes[{scope_index}] must be an object")
        scope_id = _require_str(scope.get("scope_id"), field="heading_scopes.scope_id")
        eligibility_entry = eligibility_by_scope_id[scope_id]
        decision = eligibility_entry.get("eligibility_decision")
        if not isinstance(decision, dict):
            raise ValueError(f"scope {scope_id!r} eligibility_decision must be an object")
        status = _require_str(decision.get("status"), field="eligibility_decision.status")

        if status.startswith("excluded_"):
            excluded_counts[status] = excluded_counts.get(status, 0) + 1
            continue

        if status not in INCLUDED_ELIGIBILITY_STATUSES:
            raise ValueError(
                f"unsupported eligibility status {status!r} for scope {scope_id!r}; "
                f"expected one of {sorted(INCLUDED_ELIGIBILITY_STATUSES | HEADING_SCOPE_ELIGIBILITY_STATUSES)!r}"
            )

        if status == "auto_included":
            auto_included_count += 1
        elif status == "review_ambiguous":
            review_ambiguous_count += 1

        assessment_entry = assessment_by_scope_id[scope_id]
        assembled_scopes.append(
            _build_assembled_scope(
                scope=scope,
                scope_index=scope_index,
                assessment_entry=assessment_entry,
                eligibility_decision=decision,
                provenance_map=provenance_map,
            )
        )

    aggregate_evidence_source_bundle = build_aggregate_evidence_source_bundle(
        doc_id=_require_str(assessment_input.get("doc_id"), field="assessment_input.doc_id"),
        file_hash=_require_str(
            assessment_input.get("file_hash"),
            field="assessment_input.file_hash",
        ),
        document_type=_canonicalize_document_type(assessment_input),
        heading_scopes=assembled_scopes,
    )

    input_heading_scope_count = len(canonical_scopes)
    excluded_heading_scope_count = input_heading_scope_count - len(assembled_scopes)
    stats = AggregateEvidenceAssemblyStats(
        input_heading_scope_count=input_heading_scope_count,
        assembled_heading_scope_count=len(assembled_scopes),
        auto_included_count=auto_included_count,
        review_ambiguous_count=review_ambiguous_count,
        excluded_heading_scope_count=excluded_heading_scope_count,
        excluded_counts_by_status=dict(sorted(excluded_counts.items())),
    )
    return AggregateEvidenceAssemblyExecution(
        aggregate_evidence_source_bundle=aggregate_evidence_source_bundle,
        stats=stats,
    )


def _validate_cross_identity(
    *,
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
    scope_assessments: Mapping[str, Any],
    heading_scope_eligibility: Mapping[str, Any],
) -> None:
    canonical = {
        "doc_id": _require_str(assessment_input.get("doc_id"), field="assessment_input.doc_id"),
        "file_hash": _require_str(
            assessment_input.get("file_hash"),
            field="assessment_input.file_hash",
        ),
    }
    assessment_zone_key = assessment_input.get("zone_key")
    if isinstance(assessment_zone_key, str) and assessment_zone_key.strip():
        canonical["zone_key"] = assessment_zone_key.strip()

    for label, payload in (
        ("assessment_runtime_context", assessment_runtime_context),
        ("scope_assessments", scope_assessments),
        ("heading_scope_eligibility", heading_scope_eligibility),
    ):
        for field in _IDENTITY_FIELDS:
            if field not in payload:
                continue
            actual = payload.get(field)
            if actual is None:
                continue
            if not isinstance(actual, str) or not actual.strip():
                raise ValueError(f"{label}.{field} must be a non-empty string when present")
            if actual.strip() != canonical[field]:
                raise ValueError(
                    f"{label}.{field} mismatch: {actual!r} != {canonical[field]!r}"
                )
        for field in _OPTIONAL_IDENTITY_FIELDS:
            if field not in canonical:
                continue
            if field not in payload:
                continue
            actual = payload.get(field)
            if actual is None:
                continue
            if not isinstance(actual, str) or not actual.strip():
                raise ValueError(f"{label}.{field} must be a non-empty string when present")
            if actual.strip() != canonical[field]:
                raise ValueError(
                    f"{label}.{field} mismatch: {actual!r} != {canonical[field]!r}"
                )


def _index_scope_assessments(scope_assessments: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = scope_assessments.get("scope_assessments") or []
    if not isinstance(entries, list):
        raise ValueError("scope_assessments must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("scope_assessments entries must be objects")
        scope_id = _require_str(entry.get("scope_id"), field="scope_assessments.scope_id")
        if scope_id in indexed:
            raise ValueError(f"duplicate scope_id in scope_assessments: {scope_id!r}")
        indexed[scope_id] = entry
    return indexed


def _index_eligibility_entries(
    heading_scope_eligibility: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    entries = heading_scope_eligibility.get("scope_eligibility_entries") or []
    if not isinstance(entries, list):
        raise ValueError("scope_eligibility_entries must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("scope_eligibility_entries entries must be objects")
        scope_id = _require_str(entry.get("scope_id"), field="scope_eligibility_entries.scope_id")
        if scope_id in indexed:
            raise ValueError(f"duplicate scope_id in scope_eligibility_entries: {scope_id!r}")
        indexed[scope_id] = entry
    return indexed


def _validate_scope_join(
    *,
    canonical_scopes: Sequence[Mapping[str, Any]],
    assessment_by_scope_id: Mapping[str, Mapping[str, Any]],
    eligibility_by_scope_id: Mapping[str, Mapping[str, Any]],
    scope_assessments: Mapping[str, Any],
    heading_scope_eligibility: Mapping[str, Any],
) -> None:
    canonical_scope_ids = [
        _require_str(scope.get("scope_id"), field="heading_scopes.scope_id")
        for scope in canonical_scopes
        if isinstance(scope, dict)
    ]

    assessment_scope_ids = [
        _require_str(entry.get("scope_id"), field="scope_assessments.scope_id")
        for entry in (scope_assessments.get("scope_assessments") or [])
        if isinstance(entry, dict)
    ]
    eligibility_scope_ids = [
        _require_str(entry.get("scope_id"), field="scope_eligibility_entries.scope_id")
        for entry in (heading_scope_eligibility.get("scope_eligibility_entries") or [])
        if isinstance(entry, dict)
    ]

    if assessment_scope_ids != canonical_scope_ids:
        raise ValueError(
            "scope_assessments scope IDs must match assessment_input.heading_scopes order"
        )
    if eligibility_scope_ids != canonical_scope_ids:
        raise ValueError(
            "scope_eligibility_entries scope IDs must match assessment_input.heading_scopes order"
        )

    if set(assessment_by_scope_id) != set(eligibility_by_scope_id):
        raise ValueError("scope_assessments and scope_eligibility_entries scope_id sets must match")
    if set(assessment_by_scope_id) != set(canonical_scope_ids):
        raise ValueError("heading_scopes scope_id set must match assessment and eligibility")

    for scope in canonical_scopes:
        if not isinstance(scope, dict):
            continue
        scope_id = _require_str(scope.get("scope_id"), field="heading_scopes.scope_id")
        canonical_heading_path = [str(item) for item in (scope.get("heading_path") or [])]
        canonical_unit_ids = _unit_ids_from_scope(scope)

        assessment_entry = assessment_by_scope_id[scope_id]
        eligibility_entry = eligibility_by_scope_id[scope_id]

        assessment_heading_path = [
            str(item) for item in (assessment_entry.get("heading_path") or [])
        ]
        if assessment_heading_path != canonical_heading_path:
            raise ValueError(
                f"scope {scope_id!r} heading_path mismatch between assessment_input and scope_assessments"
            )

        eligibility_heading_path = [
            str(item) for item in (eligibility_entry.get("heading_path") or [])
        ]
        if eligibility_heading_path != canonical_heading_path:
            raise ValueError(
                f"scope {scope_id!r} heading_path mismatch between assessment_input and eligibility"
            )

        assessment_unit_ids = [
            str(item) for item in (assessment_entry.get("source_unit_ids") or [])
        ]
        if assessment_unit_ids != canonical_unit_ids:
            raise ValueError(
                f"scope {scope_id!r} source_unit_ids mismatch between assessment_input and scope_assessments"
            )

        eligibility_unit_ids = [
            str(item) for item in (eligibility_entry.get("source_unit_ids") or [])
        ]
        if eligibility_unit_ids != canonical_unit_ids:
            raise ValueError(
                f"scope {scope_id!r} source_unit_ids mismatch between assessment_input and eligibility"
            )


def _build_assembled_scope(
    *,
    scope: Mapping[str, Any],
    scope_index: int,
    assessment_entry: Mapping[str, Any],
    eligibility_decision: Mapping[str, Any],
    provenance_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    scope_id = _require_str(scope.get("scope_id"), field="scope_id")
    _require_str(eligibility_decision.get("status"), field="eligibility_decision.status")

    units: list[dict[str, Any]] = []
    scope_units = scope.get("units") or []
    if not isinstance(scope_units, list):
        raise ValueError(f"scope {scope_id!r} units must be a list")

    for unit_index, unit in enumerate(scope_units):
        if not isinstance(unit, dict):
            raise ValueError(f"scope {scope_id!r} units[{unit_index}] must be an object")
        unit_id = _require_str(unit.get("unit_id"), field="unit_id")
        provenance = provenance_map.get(unit_id)
        if not isinstance(provenance, dict):
            raise ValueError(f"missing unit_provenance for {unit_id!r}")

        candidate_text = provenance.get("candidate_text")
        if not isinstance(candidate_text, str) or not candidate_text:
            raise ValueError(f"unit_provenance[{unit_id!r}].candidate_text must be a non-empty string")

        sentences = _build_assembled_sentences(
            unit=unit,
            unit_id=unit_id,
            provenance=provenance,
        )

        units.append(
            {
                "unit_id": unit_id,
                "unit_order": unit_index,
                "text": candidate_text,
                "source": {
                    "block_ids": [
                        str(item) for item in (provenance.get("source_block_ids") or []) if item
                    ],
                },
                "sentences": sentences,
            }
        )

    return {
        "scope_id": scope_id,
        "scope_order": scope_index,
        "heading_path": [str(item) for item in (scope.get("heading_path") or [])],
        "units": units,
    }


def _build_assembled_sentences(
    *,
    unit: Mapping[str, Any],
    unit_id: str,
    provenance: Mapping[str, Any],
) -> list[dict[str, Any]]:
    compact_sentences = unit.get("sentences") or []
    if not isinstance(compact_sentences, list) or not compact_sentences:
        raise ValueError(f"unit {unit_id!r} must include at least one sentence")

    sentence_source_block_ids = provenance.get("sentence_source_block_ids") or []
    source_sentence_ids = provenance.get("source_sentence_ids") or []
    if not isinstance(sentence_source_block_ids, list):
        raise ValueError(f"unit_provenance[{unit_id!r}].sentence_source_block_ids must be a list")
    if not isinstance(source_sentence_ids, list):
        raise ValueError(f"unit_provenance[{unit_id!r}].source_sentence_ids must be a list")

    if len(compact_sentences) != len(sentence_source_block_ids):
        raise ValueError(
            f"unit {unit_id!r} sentence count ({len(compact_sentences)}) does not match "
            f"sentence_source_block_ids count ({len(sentence_source_block_ids)})"
        )
    if source_sentence_ids and len(compact_sentences) != len(source_sentence_ids):
        raise ValueError(
            f"unit {unit_id!r} sentence count ({len(compact_sentences)}) does not match "
            f"source_sentence_ids count ({len(source_sentence_ids)})"
        )

    assembled: list[dict[str, Any]] = []
    for sentence_index, sentence in enumerate(compact_sentences):
        if not isinstance(sentence, dict):
            raise ValueError(f"unit {unit_id!r} sentences[{sentence_index}] must be an object")
        sentence_id = _require_str(sentence.get("sentence_id"), field="sentence_id")
        text = sentence.get("text")
        if not isinstance(text, str):
            raise ValueError(f"unit {unit_id!r} sentence {sentence_id!r} text must be a string")

        if source_sentence_ids:
            expected_sentence_id = str(source_sentence_ids[sentence_index])
            if expected_sentence_id != sentence_id:
                raise ValueError(
                    f"unit {unit_id!r} sentence[{sentence_index}] sentence_id mismatch: "
                    f"{sentence_id!r} != {expected_sentence_id!r}"
                )

        block_id = str(sentence_source_block_ids[sentence_index]).strip()
        if not block_id:
            raise ValueError(
                f"unit {unit_id!r} sentence {sentence_id!r} has no source block provenance"
            )
        assembled.append(
            {
                "sentence_id": sentence_id,
                "sentence_order": sentence_index,
                "text": text,
                "source_block_ids": [block_id],
            }
        )
    return assembled


def _canonicalize_document_type(assessment_input: Mapping[str, Any]) -> str:
    doc_meta = assessment_input.get("doc_meta")
    if not isinstance(doc_meta, Mapping):
        raise ValueError("assessment_input.doc_meta must be an object")
    raw_document_type = _require_str(
        doc_meta.get("doc_type"),
        field="assessment_input.doc_meta.doc_type",
    )
    return canonicalize_aggregate_evidence_document_type(raw_document_type)


def _unit_ids_from_scope(scope: Mapping[str, Any]) -> list[str]:
    unit_ids: list[str] = []
    for unit in scope.get("units") or []:
        if not isinstance(unit, dict):
            continue
        unit_id = unit.get("unit_id")
        if isinstance(unit_id, str) and unit_id.strip():
            unit_ids.append(unit_id.strip())
    return unit_ids


def _require_unit_provenance(
    assessment_runtime_context: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    provenance_map = assessment_runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        raise ValueError("unit_provenance must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for unit_id, provenance in provenance_map.items():
        if not isinstance(provenance, dict):
            raise ValueError(f"unit_provenance[{unit_id!r}] must be an object")
        normalized[str(unit_id)] = provenance
    return normalized


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()
