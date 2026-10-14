"""Compact heading-scoped assessment_input helpers (PR2A)."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from runtime.io import load_json

ASSESSMENT_RUNTIME_CONTEXT_FILENAME = "assessment_runtime_context.json"
ASSESSMENT_RUNTIME_CONTEXT_SCHEMA_VERSION = "0.3.0"

_FORBIDDEN_ASSESSMENT_RUNTIME_CONTEXT_KEYS = frozenset(
    {"temporal_context", "temporal_context_debug"}
)

_SCOPE_ID_PATTERN = re.compile(r"^HS\d{4}$")

_FORBIDDEN_COMPACT_UNIT_KEYS = frozenset(
    {
        "unit_kind",
        "route",
        "route_basis",
        "heading_path",
        "candidate_text",
        "candidate_sentences",
        "source_sentence_ids",
        "source_block_ids",
        "context_sentences",
        "context_block_ids",
        "all_source_block_ids",
        "candidate_block_kinds",
        "text_refs",
        "source_stage",
        "source_zone_key",
        "route_matched_terms",
        "source_component_ids",
        "overview_decompose_bundle_id",
    }
)

_PROVENANCE_KEYS = (
    "source_block_ids",
    "source_sentence_ids",
    "context_block_ids",
    "all_source_block_ids",
    "candidate_block_kinds",
    "text_refs",
    "source_stage",
    "source_zone_key",
    "filter_job_id",
    "route_basis",
    "route_matched_terms",
    "source_component_ids",
    "overview_decompose_bundle_id",
    "candidate_text",
)


def build_assessment_runtime_context_id(*, llm_input_bundle_id: str) -> str:
    token = str(llm_input_bundle_id or "").strip()
    if token.startswith("llm_input_"):
        suffix = token[len("llm_input_") :]
    else:
        suffix = token
    return f"assessment_runtime_{suffix}"


_ASSESSMENT_EVIDENCE_ALLOWED_KEYS = frozenset({"candidate_text"})


def _build_unit_assessment_evidence_text_for_validation(
    unit: Mapping[str, Any],
) -> str:
    from artifacts.routing.primary_sentence_contract import routed_body_text_from_sentences

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


def _join_scope_assessment_evidence_for_validation(
    *,
    ordered_unit_ids: Sequence[str],
    unit_by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    """Contract validation mirror of plugin scope assessment evidence join rule."""
    parts = [
        _build_unit_assessment_evidence_text_for_validation(unit_by_id[unit_id])
        for unit_id in ordered_unit_ids
    ]
    return "\n\n".join(parts)


def _join_scope_candidate_text_for_validation(
    *,
    ordered_unit_ids: Sequence[str],
    unit_candidate_text_by_id: Mapping[str, str],
) -> str:
    """Contract validation mirror of plugin scope candidate_text join rule."""
    parts = [unit_candidate_text_by_id[unit_id] for unit_id in ordered_unit_ids]
    return "\n\n".join(parts)


def build_scope_assessment_task_manifest(
    assessment_input: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Deterministic Scope task manifest from compact assessment_input."""
    tasks: list[dict[str, Any]] = []
    for scope_index, scope in enumerate(assessment_input.get("heading_scopes") or []):
        if not isinstance(scope, dict):
            raise ValueError(f"heading_scopes[{scope_index}] must be an object")
        scope_id = _require_str(scope.get("scope_id"), field="heading_scopes.scope_id")
        heading_path = scope.get("heading_path")
        if not isinstance(heading_path, list):
            raise ValueError(f"heading_scopes[{scope_id!r}].heading_path must be a list")
        evidence = scope.get("assessment_evidence")
        if not isinstance(evidence, dict):
            raise ValueError(
                f"heading_scopes[{scope_id!r}].assessment_evidence must be an object"
            )
        candidate_text = evidence.get("candidate_text")
        if not isinstance(candidate_text, str) or not candidate_text.strip():
            raise ValueError(
                f"heading_scopes[{scope_id!r}].assessment_evidence.candidate_text "
                "must be a non-empty string"
            )
        tasks.append(
            {
                "scope_id": scope_id,
                "heading_path": [str(item) for item in heading_path],
                "candidate_text": candidate_text,
            }
        )
    return tasks


def _handoff_issue(code: str, *, severity: str = "error", **details: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, **details}


def _compact_unit_ids_in_order(assessment_input: Mapping[str, Any]) -> list[str]:
    return [unit_id for unit_id, _unit in iter_compact_assessment_units(assessment_input)]


def _route_aggregate_unit_ids_in_order(
    aggregate_units: Sequence[Mapping[str, Any]],
) -> list[str]:
    unit_ids: list[str] = []
    for unit in aggregate_units:
        if not isinstance(unit, dict):
            continue
        unit_id = str(unit.get("unit_id") or "").strip()
        if unit_id:
            unit_ids.append(unit_id)
    return unit_ids


def _compact_unit_by_id(assessment_input: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {unit_id: unit for unit_id, unit in iter_compact_assessment_units(assessment_input)}


def collect_scoped_assessment_identity_issues(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        validate_scoped_assessment_identity(assessment_input, runtime_context)
    except ValueError as exc:
        issues.append(_handoff_issue("scoped_assessment_identity_mismatch", message=str(exc)))
    return issues


def collect_compact_runtime_unit_provenance_issues(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    compact_unit_ids = set(_compact_unit_ids_in_order(assessment_input))
    provenance_map = runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        return [
            _handoff_issue(
                "runtime_unit_provenance_invalid",
                message="runtime_context.unit_provenance must be an object",
            )
        ]
    provenance_ids = {str(unit_id) for unit_id in provenance_map if unit_id}
    if compact_unit_ids != provenance_ids:
        missing = sorted(compact_unit_ids - provenance_ids)
        extra = sorted(provenance_ids - compact_unit_ids)
        issues.append(
            _handoff_issue(
                "compact_runtime_unit_provenance_mismatch",
                missing_unit_ids=missing,
                extra_unit_ids=extra,
            )
        )
    return issues


def collect_route_compact_handoff_issues(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    aggregate_units: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate Route aggregate units ↔ compact assessment units ↔ runtime provenance."""
    issues: list[dict[str, Any]] = []
    provenance_map = runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        return [
            _handoff_issue(
                "runtime_unit_provenance_invalid",
                message="runtime_context.unit_provenance must be an object",
            )
        ]

    route_unit_ids = _route_aggregate_unit_ids_in_order(aggregate_units)
    compact_unit_ids = _compact_unit_ids_in_order(assessment_input)
    compact_by_id = _compact_unit_by_id(assessment_input)

    route_id_counts: dict[str, int] = {}
    for unit_id in route_unit_ids:
        route_id_counts[unit_id] = route_id_counts.get(unit_id, 0) + 1
    for unit_id, count in sorted(route_id_counts.items()):
        if count <= 1:
            continue
        issues.append(
            _handoff_issue(
                "aggregate_route_duplicate_unit_id",
                unit_id=unit_id,
                duplicate_count=count,
            )
        )

    compact_id_counts: dict[str, int] = {}
    for unit_id in compact_unit_ids:
        compact_id_counts[unit_id] = compact_id_counts.get(unit_id, 0) + 1
    for unit_id, count in sorted(compact_id_counts.items()):
        if count <= 1:
            continue
        issues.append(
            _handoff_issue(
                "assessment_input_duplicate_unit_id",
                unit_id=unit_id,
                duplicate_count=count,
            )
        )

    route_id_set = set(route_unit_ids)
    compact_id_set = set(compact_unit_ids)
    for unit_id in sorted(route_id_set - compact_id_set):
        issues.append(
            _handoff_issue(
                "aggregate_route_unit_missing_from_assessment_input",
                unit_id=unit_id,
            )
        )
    for unit_id in sorted(compact_id_set - route_id_set):
        issues.append(
            _handoff_issue(
                "assessment_input_unit_not_in_aggregate_route",
                unit_id=unit_id,
            )
        )
    if route_unit_ids != compact_unit_ids and route_id_set == compact_id_set:
        issues.append(
            _handoff_issue(
                "aggregate_route_unit_order_mismatch",
                expected_unit_ids=route_unit_ids,
                actual_unit_ids=compact_unit_ids,
            )
        )

    for unit in aggregate_units:
        if not isinstance(unit, dict):
            issues.append(_handoff_issue("aggregate_unit_invalid_shape"))
            continue
        unit_id = str(unit.get("unit_id") or "").strip()
        if not unit_id or unit_id not in compact_by_id:
            continue
        compact_unit = compact_by_id[unit_id]
        route_sentences = [
            sentence
            for sentence in (unit.get("sentences") or [])
            if isinstance(sentence, dict)
        ]
        compact_sentences = [
            sentence
            for sentence in (compact_unit.get("sentences") or [])
            if isinstance(sentence, dict)
        ]
        if len(route_sentences) != len(compact_sentences):
            issues.append(
                _handoff_issue(
                    "route_compact_sentence_count_mismatch",
                    unit_id=unit_id,
                    expected_count=len(route_sentences),
                    actual_count=len(compact_sentences),
                )
            )
        for index, route_sentence in enumerate(route_sentences):
            if index >= len(compact_sentences):
                break
            compact_sentence = compact_sentences[index]
            route_sentence_id = str(route_sentence.get("sentence_id") or "")
            compact_sentence_id = str(compact_sentence.get("sentence_id") or "")
            if route_sentence_id != compact_sentence_id:
                issues.append(
                    _handoff_issue(
                        "route_compact_sentence_id_mismatch",
                        unit_id=unit_id,
                        sentence_index=index,
                        expected_sentence_id=route_sentence_id,
                        actual_sentence_id=compact_sentence_id,
                    )
                )
            route_text = str(route_sentence.get("text") or "")
            compact_text = str(compact_sentence.get("text") or "")
            if route_text != compact_text:
                issues.append(
                    _handoff_issue(
                        "route_compact_sentence_text_mismatch",
                        unit_id=unit_id,
                        sentence_index=index,
                        sentence_id=route_sentence_id or compact_sentence_id,
                    )
                )

        provenance = provenance_map.get(unit_id)
        if not isinstance(provenance, dict):
            issues.append(
                _handoff_issue(
                    "runtime_unit_provenance_missing",
                    unit_id=unit_id,
                )
            )
            continue

        expected_sentence_ids = [
            str(sentence.get("sentence_id") or "")
            for sentence in route_sentences
            if sentence.get("sentence_id")
        ]
        runtime_sentence_ids = [
            str(sentence_id)
            for sentence_id in (provenance.get("source_sentence_ids") or [])
            if sentence_id
        ]
        if runtime_sentence_ids != expected_sentence_ids:
            issues.append(
                _handoff_issue(
                    "runtime_source_sentence_id_mismatch",
                    unit_id=unit_id,
                    expected_source_sentence_ids=expected_sentence_ids,
                    actual_source_sentence_ids=runtime_sentence_ids,
                )
            )

        expected_block_ids = [
            str(sentence.get("source_block_id") or "")
            for sentence in route_sentences
            if sentence.get("source_block_id")
        ]
        runtime_block_ids = [
            str(block_id)
            for block_id in (provenance.get("sentence_source_block_ids") or [])
            if block_id
        ]
        if runtime_block_ids != expected_block_ids:
            issues.append(
                _handoff_issue(
                    "runtime_sentence_source_block_mismatch",
                    unit_id=unit_id,
                    expected_sentence_source_block_ids=expected_block_ids,
                    actual_sentence_source_block_ids=runtime_block_ids,
                )
            )

    return issues


def collect_scope_assessment_evidence_issues(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    *,
    aggregate_units: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Cross-check Scope evidence against runtime unit provenance (and optional aggregate units)."""
    issues: list[dict[str, Any]] = []
    provenance_map = runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        return [
            _handoff_issue(
                "runtime_unit_provenance_invalid",
                message="runtime_context.unit_provenance must be an object",
            )
        ]

    if aggregate_units is not None:
        for unit in aggregate_units:
            if not isinstance(unit, dict):
                issues.append(_handoff_issue("aggregate_unit_invalid_shape"))
                continue
            unit_id = str(unit.get("unit_id") or "").strip()
            if not unit_id:
                issues.append(_handoff_issue("aggregate_unit_missing_unit_id"))
                continue
            aggregate_text = _build_unit_assessment_evidence_text_for_validation(unit)
            provenance = provenance_map.get(unit_id)
            if not isinstance(provenance, dict):
                issues.append(
                    _handoff_issue(
                        "scope_assessment_evidence_missing_unit",
                        unit_id=unit_id,
                    )
                )
                continue
            provenance_text = provenance.get("candidate_text")
            if not isinstance(provenance_text, str) or not provenance_text:
                issues.append(
                    _handoff_issue(
                        "scope_assessment_evidence_empty_unit_text",
                        unit_id=unit_id,
                    )
                )
                continue
            if aggregate_text != provenance_text:
                issues.append(
                    _handoff_issue(
                        "scope_assessment_evidence_unit_text_mismatch",
                        unit_id=unit_id,
                    )
                )

    for scope_index, scope in enumerate(assessment_input.get("heading_scopes") or []):
        if not isinstance(scope, dict):
            issues.append(
                _handoff_issue(
                    "heading_scope_invalid_shape",
                    scope_index=scope_index,
                )
            )
            continue
        scope_id = str(scope.get("scope_id") or "").strip()
        if not scope_id:
            issues.append(
                _handoff_issue(
                    "heading_scope_missing_scope_id",
                    scope_index=scope_index,
                )
            )
            continue
        ordered_unit_ids = [
            str(unit.get("unit_id") or "").strip()
            for unit in (scope.get("units") or [])
            if isinstance(unit, dict) and str(unit.get("unit_id") or "").strip()
        ]

        evidence = scope.get("assessment_evidence")
        if not isinstance(evidence, dict):
            issues.append(
                _handoff_issue(
                    "scope_assessment_evidence_missing",
                    scope_id=scope_id,
                )
            )
            continue
        stored_scope_text = evidence.get("candidate_text")
        if not isinstance(stored_scope_text, str) or not stored_scope_text.strip():
            issues.append(
                _handoff_issue(
                    "scope_assessment_evidence_empty_scope_text",
                    scope_id=scope_id,
                )
            )
            continue

        if aggregate_units is not None:
            unit_by_id = {
                str(unit.get("unit_id") or "").strip(): unit
                for unit in aggregate_units
                if isinstance(unit, dict) and str(unit.get("unit_id") or "").strip()
            }
            for unit_id in ordered_unit_ids:
                if unit_id not in unit_by_id:
                    issues.append(
                        _handoff_issue(
                            "scope_assessment_evidence_missing_unit",
                            scope_id=scope_id,
                            unit_id=unit_id,
                        )
                    )
            missing_scope_units = [
                unit_id for unit_id in ordered_unit_ids if unit_id not in unit_by_id
            ]
            if missing_scope_units:
                continue
            expected_scope_text = _join_scope_assessment_evidence_for_validation(
                ordered_unit_ids=ordered_unit_ids,
                unit_by_id=unit_by_id,
            )
            if expected_scope_text != stored_scope_text:
                issues.append(
                    _handoff_issue(
                        "scope_assessment_evidence_candidate_text_mismatch",
                        scope_id=scope_id,
                    )
                )

    return issues


def validate_scope_assessment_evidence_cross_artifact(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    *,
    aggregate_units: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    issues = collect_scope_assessment_evidence_issues(
        assessment_input,
        runtime_context,
        aggregate_units=aggregate_units,
    )
    if issues:
        first = issues[0]
        code = str(first.get("code") or "scope_assessment_evidence_mismatch")
        raise ValueError(f"{code}: handoff validation failed")


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def build_assessment_runtime_context_envelope(
    *,
    llm_input_bundle_id: str,
    runtime_context_id: str,
    doc_id: str,
    file_hash: str,
    route_stats: Mapping[str, Any],
    unit_provenance: Mapping[str, Any],
    source_routed_unit_bundle_ref: Mapping[str, Any],
    source_routing_manifest_ref: Mapping[str, Any],
    coverage_bundle_ref: Mapping[str, Any] | None = None,
    block_manifest_ref: Mapping[str, Any] | None = None,
    doc_meta_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_refs: dict[str, Any] = {
        "source_routed_unit_bundle_ref": dict(source_routed_unit_bundle_ref),
        "source_routing_manifest_ref": dict(source_routing_manifest_ref),
    }
    if coverage_bundle_ref is not None:
        source_refs["coverage_bundle_ref"] = dict(coverage_bundle_ref)
    if block_manifest_ref is not None:
        source_refs["block_manifest_ref"] = dict(block_manifest_ref)
    if doc_meta_ref is not None:
        source_refs["doc_meta_ref"] = dict(doc_meta_ref)

    runtime_context: dict[str, Any] = {
        "schema_version": ASSESSMENT_RUNTIME_CONTEXT_SCHEMA_VERSION,
        "runtime_context_id": runtime_context_id,
        "llm_input_bundle_id": llm_input_bundle_id,
        "doc_id": _require_str(doc_id, field="doc_id"),
        "file_hash": _require_str(file_hash, field="file_hash"),
        "source_refs": source_refs,
        "route_stats": dict(route_stats or {}),
        "unit_provenance": dict(unit_provenance),
    }
    return runtime_context


def iter_compact_assessment_units(
    assessment_input: Mapping[str, Any],
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for scope in assessment_input.get("heading_scopes") or []:
        if not isinstance(scope, dict):
            continue
        for unit in scope.get("units") or []:
            if not isinstance(unit, dict):
                continue
            unit_id = str(unit.get("unit_id") or "").strip()
            if unit_id:
                yield unit_id, unit


def compact_assessment_units_for_integrity(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    provenance_map = runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        raise ValueError("runtime_context.unit_provenance must be an object")
    actual_units: list[dict[str, Any]] = []
    for unit_id, compact_unit in iter_compact_assessment_units(assessment_input):
        provenance = provenance_map.get(unit_id)
        if not isinstance(provenance, dict):
            raise ValueError(f"missing unit_provenance for {unit_id!r}")
        source_block_ids = [
            str(block_id)
            for block_id in (provenance.get("source_block_ids") or [])
            if block_id
        ]
        actual_units.append(
            {
                "unit_id": unit_id,
                "source_block_ids": source_block_ids,
            }
        )
    return actual_units


def collect_scoped_assessment_handoff_issues(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    *,
    aggregate_units: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Collect Route→compact→provenance→assessment_evidence handoff issues."""
    issues: list[dict[str, Any]] = []
    issues.extend(
        collect_scoped_assessment_identity_issues(assessment_input, runtime_context)
    )
    issues.extend(
        collect_compact_runtime_unit_provenance_issues(assessment_input, runtime_context)
    )
    if aggregate_units is not None:
        issues.extend(
            collect_route_compact_handoff_issues(
                assessment_input,
                runtime_context,
                aggregate_units,
            )
        )
    issues.extend(
        collect_scope_assessment_evidence_issues(
            assessment_input,
            runtime_context,
            aggregate_units=aggregate_units,
        )
    )
    return issues


def validate_scoped_assessment_cross_artifacts(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    *,
    aggregate_units: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Cross-artifact checks between compact assessment_input and runtime context."""
    issues = collect_scoped_assessment_handoff_issues(
        assessment_input,
        runtime_context,
        aggregate_units=aggregate_units,
    )
    if not issues:
        return
    first = issues[0]
    code = str(first.get("code") or "scoped_assessment_handoff_mismatch")
    message = str(first.get("message") or code.replace("_", " "))
    raise ValueError(f"{code}: {message}")


def validate_scoped_assessment_identity(
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
) -> None:
    runtime_ref = assessment_input.get("runtime_context_ref") or {}
    if not isinstance(runtime_ref, dict):
        raise ValueError("assessment_input.runtime_context_ref must be an object")
    expected_runtime_id = _require_str(
        runtime_ref.get("runtime_context_id"),
        field="runtime_context_ref.runtime_context_id",
    )
    actual_runtime_id = _require_str(
        runtime_context.get("runtime_context_id"),
        field="runtime_context.runtime_context_id",
    )
    if expected_runtime_id != actual_runtime_id:
        raise ValueError(
            "runtime_context_id mismatch between assessment_input and runtime context"
        )

    input_bundle_id = _require_str(
        assessment_input.get("llm_input_bundle_id"),
        field="assessment_input.llm_input_bundle_id",
    )
    runtime_bundle_id = _require_str(
        runtime_context.get("llm_input_bundle_id"),
        field="runtime_context.llm_input_bundle_id",
    )
    if input_bundle_id != runtime_bundle_id:
        raise ValueError("llm_input_bundle_id mismatch between assessment_input and runtime context")

    for field in ("doc_id",):
        input_value = _require_str(assessment_input.get(field), field=f"assessment_input.{field}")
        runtime_value = _require_str(runtime_context.get(field), field=f"runtime_context.{field}")
        if input_value != runtime_value:
            raise ValueError(f"{field} mismatch between assessment_input and runtime context")


def validate_assessment_runtime_context(
    runtime_context: Mapping[str, Any],
) -> None:
    schema_version = _require_str(
        runtime_context.get("schema_version"),
        field="schema_version",
    )
    if schema_version != ASSESSMENT_RUNTIME_CONTEXT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported assessment_runtime_context schema_version {schema_version!r}; "
            f"expected {ASSESSMENT_RUNTIME_CONTEXT_SCHEMA_VERSION!r}"
        )
    forbidden = sorted(
        key for key in _FORBIDDEN_ASSESSMENT_RUNTIME_CONTEXT_KEYS if key in runtime_context
    )
    if forbidden:
        raise ValueError(
            f"assessment_runtime_context must not include legacy fields: {forbidden!r}"
        )
    _require_str(runtime_context.get("runtime_context_id"), field="runtime_context_id")
    _require_str(runtime_context.get("llm_input_bundle_id"), field="llm_input_bundle_id")
    _require_str(runtime_context.get("doc_id"), field="doc_id")
    _require_str(runtime_context.get("file_hash"), field="file_hash")

    provenance_map = runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        raise ValueError("unit_provenance must be an object")

    for unit_id, provenance in provenance_map.items():
        if not isinstance(provenance, dict):
            raise ValueError(f"unit_provenance[{unit_id!r}] must be an object")
        source_block_ids = provenance.get("source_block_ids") or []
        if not source_block_ids:
            raise ValueError(f"unit_provenance[{unit_id!r}].source_block_ids must be non-empty")


def resolve_assessment_runtime_context_path(
    assessment_input_path: Path | str,
    *,
    override_path: Path | str | None = None,
) -> Path:
    if override_path is not None:
        resolved = Path(override_path).resolve()
        if not resolved.is_file():
            raise ValueError(
                f"assessment runtime context must be a file: {resolved}"
            )
        return resolved
    sibling = Path(assessment_input_path).resolve().parent / ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    if not sibling.is_file():
        raise ValueError(
            f"missing sibling assessment runtime context: {ASSESSMENT_RUNTIME_CONTEXT_FILENAME}"
        )
    return sibling


def load_assessment_runtime_context(
    assessment_input_path: Path | str,
    *,
    override_path: Path | str | None = None,
) -> dict[str, Any]:
    path = resolve_assessment_runtime_context_path(
        assessment_input_path,
        override_path=override_path,
    )
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("assessment_runtime_context must be a JSON object")
    return payload


def count_compact_assessment_stats(
    assessment_input: Mapping[str, Any],
) -> dict[str, int]:
    heading_scopes = assessment_input.get("heading_scopes") or []
    unit_count = 0
    sentence_count = 0
    for scope in heading_scopes:
        if not isinstance(scope, dict):
            continue
        for unit in scope.get("units") or []:
            if not isinstance(unit, dict):
                continue
            unit_count += 1
            sentence_count += len(unit.get("sentences") or [])
    return {
        "heading_scope_count": len(heading_scopes),
        "assessment_unit_count": unit_count,
        "assessment_sentence_count": sentence_count,
    }


def validate_compact_assessment_input_shape(payload: Mapping[str, Any]) -> None:
    if "units" in payload:
        raise ValueError("assessment_input must not include legacy top-level units")

    heading_scopes = payload.get("heading_scopes")
    if not isinstance(heading_scopes, list) or not heading_scopes:
        raise ValueError("heading_scopes must be a non-empty list")

    seen_scope_ids: set[str] = set()
    seen_unit_ids: set[str] = set()
    for scope_index, scope in enumerate(heading_scopes):
        if not isinstance(scope, dict):
            raise ValueError(f"heading_scopes[{scope_index}] must be an object")
        scope_id = _require_str(scope.get("scope_id"), field=f"heading_scopes[{scope_index}].scope_id")
        if scope_id in seen_scope_ids:
            raise ValueError(f"duplicate scope_id {scope_id!r}")
        if not _SCOPE_ID_PATTERN.fullmatch(scope_id):
            raise ValueError(f"invalid scope_id {scope_id!r}; expected HSdddd")
        seen_scope_ids.add(scope_id)

        units = scope.get("units")
        if not isinstance(units, list) or not units:
            raise ValueError(f"heading_scopes[{scope_index}].units must be a non-empty list")
        if not isinstance(scope.get("heading_path"), list):
            raise ValueError(f"heading_scopes[{scope_index}].heading_path must be a list")

        evidence = scope.get("assessment_evidence")
        if not isinstance(evidence, dict):
            raise ValueError(
                f"heading_scopes[{scope_index}].assessment_evidence must be an object"
            )
        extra_evidence_keys = set(evidence) - _ASSESSMENT_EVIDENCE_ALLOWED_KEYS
        if extra_evidence_keys:
            raise ValueError(
                f"heading_scopes[{scope_index}].assessment_evidence includes forbidden fields: "
                f"{sorted(extra_evidence_keys)!r}"
            )
        candidate_text = evidence.get("candidate_text")
        if not isinstance(candidate_text, str) or not candidate_text.strip():
            raise ValueError(
                f"heading_scopes[{scope_index}].assessment_evidence.candidate_text "
                "must be a non-empty string"
            )

        for unit_index, unit in enumerate(units):
            if not isinstance(unit, dict):
                raise ValueError(
                    f"heading_scopes[{scope_index}].units[{unit_index}] must be an object"
                )
            unit_id = _require_str(
                unit.get("unit_id"),
                field=f"heading_scopes[{scope_index}].units[{unit_index}].unit_id",
            )
            if unit_id in seen_unit_ids:
                raise ValueError(f"duplicate unit_id {unit_id!r}")
            seen_unit_ids.add(unit_id)
            for forbidden in _FORBIDDEN_COMPACT_UNIT_KEYS:
                if forbidden in unit:
                    raise ValueError(
                        f"compact unit {unit_id!r} must not include forbidden field {forbidden!r}"
                    )
            sentences = unit.get("sentences")
            if not isinstance(sentences, list) or not sentences:
                raise ValueError(f"unit {unit_id!r} must include at least one sentence")
            seen_sentence_ids: set[str] = set()
            for sentence_index, sentence in enumerate(sentences):
                if not isinstance(sentence, dict):
                    raise ValueError(
                        f"unit {unit_id!r} sentences[{sentence_index}] must be an object"
                    )
                allowed = {"sentence_id", "text"}
                extra = set(sentence) - allowed
                if extra:
                    raise ValueError(
                        f"unit {unit_id!r} sentence includes forbidden fields: {sorted(extra)!r}"
                    )
                sentence_id = _require_str(
                    sentence.get("sentence_id"),
                    field=f"unit {unit_id!r} sentences[{sentence_index}].sentence_id",
                )
                if sentence_id in seen_sentence_ids:
                    raise ValueError(
                        f"duplicate sentence_id {sentence_id!r} within unit {unit_id!r}"
                    )
                seen_sentence_ids.add(sentence_id)
                _require_str(
                    sentence.get("text"),
                    field=f"unit {unit_id!r} sentences[{sentence_index}].text",
                )
