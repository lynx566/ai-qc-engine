"""Heading-scope eligibility artifact contract: build and validate."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_ARTIFACT_TYPE,
    SCOPE_ASSESSMENTS_FILENAME,
    SCOPE_ASSESSMENTS_SCHEMA_VERSION,
)

HEADING_SCOPE_ELIGIBILITY_FILENAME = "heading_scope_eligibility.json"
HEADING_SCOPE_ELIGIBILITY_SCHEMA_VERSION = "0.2.0"
HEADING_SCOPE_ELIGIBILITY_ARTIFACT_TYPE = "heading_scope_eligibility"

HEADING_SCOPE_ELIGIBILITY_STATUSES = frozenset(
    {
        "auto_included",
        "excluded_non_aggregate_form",
        "excluded_route_mismatch",
        "excluded_non_primary_safety",
        "excluded_non_target_product",
        "review_ambiguous",
    }
)

_FORBIDDEN_ROOT_KEYS = frozenset(
    {
        "comparison_type",
        "workflow_type",
        "plugin_variant",
        "match_candidate",
        "candidate_id",
        "match_projection",
        "reject_audit",
        "tagged_items",
        "study_context",
        "time_anchor",
        "population_context",
        "post_llm_validation_flags",
        "match_candidates",
        "scope_processing_plan",
        "processing_disposition",
        "processing_disposition_counts",
    }
)

_REASON_FIELD_ORDER = (
    "unit_form",
    "route_qc.route_mismatch",
    "safety_role",
    "product_context_role",
)


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _reject_forbidden_root_keys(payload: Mapping[str, Any]) -> None:
    for key in _FORBIDDEN_ROOT_KEYS:
        if key in payload:
            raise ValueError(f"heading_scope_eligibility must not include {key!r}")


def _validate_eligibility_decision(
    decision: Any,
    *,
    scope_id: str,
) -> dict[str, Any]:
    if not isinstance(decision, dict):
        raise ValueError(f"scope {scope_id!r} eligibility_decision must be an object")
    status = _require_str(decision.get("status"), field="eligibility_decision.status")
    if status not in HEADING_SCOPE_ELIGIBILITY_STATUSES:
        raise ValueError(
            f"scope {scope_id!r} eligibility_decision.status must be one of "
            f"{sorted(HEADING_SCOPE_ELIGIBILITY_STATUSES)!r}, got {status!r}"
        )
    reasons = decision.get("reasons")
    if not isinstance(reasons, list):
        raise ValueError(f"scope {scope_id!r} eligibility_decision.reasons must be a list")
    normalized_reasons = [str(item) for item in reasons]
    expected_prefixes = [f"{field}:" for field in _REASON_FIELD_ORDER]
    if len(normalized_reasons) != len(_REASON_FIELD_ORDER):
        raise ValueError(
            f"scope {scope_id!r} eligibility_decision.reasons must contain exactly "
            f"{len(_REASON_FIELD_ORDER)} entries"
        )
    for index, (reason, prefix) in enumerate(zip(normalized_reasons, expected_prefixes)):
        if not reason.startswith(prefix):
            raise ValueError(
                f"scope {scope_id!r} eligibility_decision.reasons[{index}] "
                f"must start with {prefix!r}, got {reason!r}"
            )
    return {"status": status, "reasons": normalized_reasons}


def _artifact_relative_path(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def build_source_scope_assessments_ref(
    *,
    scope_assessments_payload: Mapping[str, Any],
    scope_assessments_path: Path,
    project_root: Path,
    run_id: str,
) -> dict[str, Any]:
    resolved_path = scope_assessments_path.resolve()
    rel_path = _artifact_relative_path(resolved_path, project_root)
    doc_id = _require_str(scope_assessments_payload.get("doc_id"), field="doc_id")
    zone_key = str(scope_assessments_payload.get("zone_key") or "").strip()
    file_hash = _require_str(scope_assessments_payload.get("file_hash"), field="file_hash")
    if resolved_path.name != SCOPE_ASSESSMENTS_FILENAME:
        raise ValueError(
            f"scope_assessments_path must end with {SCOPE_ASSESSMENTS_FILENAME!r}, "
            f"got {resolved_path.name!r}"
        )
    source_ref: dict[str, Any] = {
        "artifact_type": SCOPE_ASSESSMENTS_ARTIFACT_TYPE,
        "schema_version": str(
            scope_assessments_payload.get("schema_version") or SCOPE_ASSESSMENTS_SCHEMA_VERSION
        ),
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
        "run_id": _require_str(run_id, field="run_id"),
        "doc_id": doc_id,
        "file_hash": file_hash,
        "path": rel_path,
    }
    if zone_key:
        source_ref["zone_key"] = zone_key
    return source_ref


IN_MEMORY_ASSESS_RUN_ID = "in_memory"


def build_in_memory_source_scope_assessments_ref(
    *,
    scope_assessments_payload: Mapping[str, Any],
    run_id: str = IN_MEMORY_ASSESS_RUN_ID,
) -> dict[str, Any]:
    """Build a validated assess provenance ref without filesystem persistence."""
    doc_id = _require_str(scope_assessments_payload.get("doc_id"), field="doc_id")
    zone_key = str(scope_assessments_payload.get("zone_key") or "").strip()
    file_hash = _require_str(scope_assessments_payload.get("file_hash"), field="file_hash")
    resolved_run_id = _require_str(run_id, field="run_id")
    if zone_key:
        rel_path = (
            f"runs/evidence_source_preparation/assess/{resolved_run_id}/doc_{doc_id}/"
            f"{zone_key}/aggregate_evidence/{SCOPE_ASSESSMENTS_FILENAME}"
        )
    else:
        rel_path = (
            f"runs/evidence_source_preparation/assess/{resolved_run_id}/doc_{doc_id}/"
            f"aggregate_evidence/{SCOPE_ASSESSMENTS_FILENAME}"
        )
    source_ref: dict[str, Any] = {
        "artifact_type": SCOPE_ASSESSMENTS_ARTIFACT_TYPE,
        "schema_version": str(
            scope_assessments_payload.get("schema_version") or SCOPE_ASSESSMENTS_SCHEMA_VERSION
        ),
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
        "run_id": resolved_run_id,
        "doc_id": doc_id,
        "file_hash": file_hash,
        "path": rel_path,
    }
    if zone_key:
        source_ref["zone_key"] = zone_key
    return source_ref


def validate_source_scope_assessments_ref(
    source_ref: Mapping[str, Any],
    *,
    scope_assessments_payload: Mapping[str, Any] | None = None,
) -> None:
    if not isinstance(source_ref, dict):
        raise ValueError("source_scope_assessments_ref must be an object")
    artifact_type = _require_str(
        source_ref.get("artifact_type"),
        field="source_scope_assessments_ref.artifact_type",
    )
    if artifact_type != SCOPE_ASSESSMENTS_ARTIFACT_TYPE:
        raise ValueError(
            f"source_scope_assessments_ref.artifact_type must be "
            f"{SCOPE_ASSESSMENTS_ARTIFACT_TYPE!r}, got {artifact_type!r}"
        )
    _require_str(
        source_ref.get("schema_version"),
        field="source_scope_assessments_ref.schema_version",
    )
    stage = _require_str(source_ref.get("stage"), field="source_scope_assessments_ref.stage")
    if stage != EVIDENCE_SOURCE_PREPARATION_STAGE:
        raise ValueError(
            "source_scope_assessments_ref.stage must be "
            f"{EVIDENCE_SOURCE_PREPARATION_STAGE!r}"
        )
    phase = _require_str(source_ref.get("phase"), field="source_scope_assessments_ref.phase")
    if phase != EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE:
        raise ValueError(
            "source_scope_assessments_ref.phase must be "
            f"{EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE!r}"
        )
    _require_str(source_ref.get("run_id"), field="source_scope_assessments_ref.run_id")
    _require_str(source_ref.get("doc_id"), field="source_scope_assessments_ref.doc_id")
    zone_key = source_ref.get("zone_key")
    if zone_key is not None and (
        not isinstance(zone_key, str) or not zone_key.strip()
    ):
        raise ValueError("source_scope_assessments_ref.zone_key must be a non-empty string when present")
    _require_str(source_ref.get("file_hash"), field="source_scope_assessments_ref.file_hash")
    path = _require_str(source_ref.get("path"), field="source_scope_assessments_ref.path")
    if path == SCOPE_ASSESSMENTS_FILENAME or "/" not in path:
        raise ValueError(
            "source_scope_assessments_ref.path must be a project-relative artifact path, "
            f"not bare {SCOPE_ASSESSMENTS_FILENAME!r}"
        )
    if not path.endswith(f"/{SCOPE_ASSESSMENTS_FILENAME}") and path != SCOPE_ASSESSMENTS_FILENAME:
        raise ValueError(
            f"source_scope_assessments_ref.path must reference {SCOPE_ASSESSMENTS_FILENAME!r}"
        )
    if scope_assessments_payload is not None:
        for field in ("doc_id", "file_hash"):
            expected = _require_str(
                scope_assessments_payload.get(field),
                field=field,
            )
            actual = _require_str(source_ref.get(field), field=f"source_scope_assessments_ref.{field}")
            if actual != expected:
                raise ValueError(
                    f"source_scope_assessments_ref.{field} must match source scope_assessments"
                )
        payload_zone_key = scope_assessments_payload.get("zone_key")
        ref_zone_key = source_ref.get("zone_key")
        if isinstance(payload_zone_key, str) and payload_zone_key.strip():
            expected_zone = payload_zone_key.strip()
            actual_zone = str(ref_zone_key or "").strip()
            if actual_zone != expected_zone:
                raise ValueError(
                    "source_scope_assessments_ref.zone_key must match source scope_assessments"
                )
        elif ref_zone_key is not None and str(ref_zone_key).strip():
            raise ValueError(
                "source_scope_assessments_ref.zone_key must be omitted when scope_assessments has no zone_key"
            )


def resolve_source_scope_assessments_path(
    *,
    project_root: Path,
    source_ref: Mapping[str, Any],
) -> Path:
    validate_source_scope_assessments_ref(source_ref)
    rel_path = _require_str(source_ref.get("path"), field="source_scope_assessments_ref.path")
    resolved = (project_root / rel_path).resolve()
    if not resolved.is_file():
        raise ValueError(f"source scope_assessments not found: {resolved}")
    return resolved


def build_heading_scope_eligibility_envelope(
    *,
    scope_assessments_payload: Mapping[str, Any],
    scope_eligibility_entries: Sequence[Mapping[str, Any]],
    source_scope_assessments_ref: Mapping[str, Any],
) -> dict[str, Any]:
    validate_source_scope_assessments_ref(
        source_scope_assessments_ref,
        scope_assessments_payload=scope_assessments_payload,
    )
    source_ref = dict(source_scope_assessments_ref)
    status_counts: Counter[str] = Counter()
    auto_included_scope_ids: list[str] = []
    entries: list[dict[str, Any]] = []

    for entry in scope_eligibility_entries:
        scope_id = _require_str(entry.get("scope_id"), field="scope_id")
        heading_path = entry.get("heading_path")
        if not isinstance(heading_path, list):
            raise ValueError(f"scope {scope_id!r} heading_path must be a list")
        source_unit_ids = entry.get("source_unit_ids")
        if not isinstance(source_unit_ids, list):
            raise ValueError(f"scope {scope_id!r} source_unit_ids must be a list")
        eligibility_decision = _validate_eligibility_decision(
            entry.get("eligibility_decision"),
            scope_id=scope_id,
        )
        status_counts[eligibility_decision["status"]] += 1
        if eligibility_decision["status"] == "auto_included":
            auto_included_scope_ids.append(scope_id)
        entries.append(
            {
                "scope_id": scope_id,
                "heading_path": [str(item) for item in heading_path],
                "source_unit_ids": [str(item) for item in source_unit_ids],
                "eligibility_decision": eligibility_decision,
            }
        )

    scope_count = len(entries)
    auto_included_scope_count = status_counts.get("auto_included", 0)
    review_ambiguous_scope_count = status_counts.get("review_ambiguous", 0)
    excluded_scope_count = scope_count - auto_included_scope_count - review_ambiguous_scope_count

    return {
        "artifact_type": HEADING_SCOPE_ELIGIBILITY_ARTIFACT_TYPE,
        "schema_version": HEADING_SCOPE_ELIGIBILITY_SCHEMA_VERSION,
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE,
        "doc_id": scope_assessments_payload.get("doc_id"),
        "file_hash": scope_assessments_payload.get("file_hash"),
        "document_type": scope_assessments_payload.get("document_type"),
        "zone_key": scope_assessments_payload.get("zone_key"),
        "source_scope_assessments_ref": source_ref,
        "scope_count": scope_count,
        "auto_included_scope_count": auto_included_scope_count,
        "excluded_scope_count": excluded_scope_count,
        "review_ambiguous_scope_count": review_ambiguous_scope_count,
        "eligibility_status_counts": {
            status: status_counts.get(status, 0)
            for status in sorted(HEADING_SCOPE_ELIGIBILITY_STATUSES)
        },
        "auto_included_scope_ids": auto_included_scope_ids,
        "scope_eligibility_entries": entries,
    }


def validate_heading_scope_eligibility(
    payload: Mapping[str, Any],
    *,
    source_scope_assessments_payload: Mapping[str, Any] | None = None,
) -> None:
    _reject_forbidden_root_keys(payload)

    artifact_type = _require_str(payload.get("artifact_type"), field="artifact_type")
    if artifact_type != HEADING_SCOPE_ELIGIBILITY_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {HEADING_SCOPE_ELIGIBILITY_ARTIFACT_TYPE!r}, "
            f"got {artifact_type!r}"
        )

    schema_version = _require_str(payload.get("schema_version"), field="schema_version")
    if schema_version != HEADING_SCOPE_ELIGIBILITY_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported heading_scope_eligibility schema_version {schema_version!r}; "
            f"expected {HEADING_SCOPE_ELIGIBILITY_SCHEMA_VERSION!r}"
        )

    stage = _require_str(payload.get("stage"), field="stage")
    if stage != EVIDENCE_SOURCE_PREPARATION_STAGE:
        raise ValueError(
            f"stage must be {EVIDENCE_SOURCE_PREPARATION_STAGE!r}, got {stage!r}"
        )

    phase = _require_str(payload.get("phase"), field="phase")
    if phase != EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE:
        raise ValueError(
            f"phase must be {EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE!r}, "
            f"got {phase!r}"
        )

    for field in ("doc_id", "file_hash"):
        _require_str(payload.get(field), field=field)

    zone_key = payload.get("zone_key")
    if zone_key is not None and (not isinstance(zone_key, str) or not zone_key.strip()):
        raise ValueError("zone_key must be a non-empty string when present")

    document_type = payload.get("document_type")
    if document_type is not None and (
        not isinstance(document_type, str) or not document_type.strip()
    ):
        raise ValueError("document_type must be a non-empty string when present")

    source_ref = payload.get("source_scope_assessments_ref")
    validate_source_scope_assessments_ref(
        source_ref if isinstance(source_ref, Mapping) else {},
        scope_assessments_payload=source_scope_assessments_payload,
    )

    scope_count = payload.get("scope_count")
    if not isinstance(scope_count, int) or scope_count < 0:
        raise ValueError("scope_count must be a non-negative integer")

    auto_included_scope_count = payload.get("auto_included_scope_count")
    excluded_scope_count = payload.get("excluded_scope_count")
    review_ambiguous_scope_count = payload.get("review_ambiguous_scope_count")
    for name, value in (
        ("auto_included_scope_count", auto_included_scope_count),
        ("excluded_scope_count", excluded_scope_count),
        ("review_ambiguous_scope_count", review_ambiguous_scope_count),
    ):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    eligibility_status_counts = payload.get("eligibility_status_counts")
    if not isinstance(eligibility_status_counts, dict):
        raise ValueError("eligibility_status_counts must be an object")
    unknown_status_keys = sorted(
        key for key in eligibility_status_counts if key not in HEADING_SCOPE_ELIGIBILITY_STATUSES
    )
    if unknown_status_keys:
        raise ValueError(
            "eligibility_status_counts contains unknown status keys: "
            f"{unknown_status_keys!r}"
        )
    for status in HEADING_SCOPE_ELIGIBILITY_STATUSES:
        count = eligibility_status_counts.get(status)
        if not isinstance(count, int) or count < 0:
            raise ValueError(
                f"eligibility_status_counts[{status!r}] must be a non-negative integer"
            )

    auto_included_scope_ids = payload.get("auto_included_scope_ids")
    if not isinstance(auto_included_scope_ids, list):
        raise ValueError("auto_included_scope_ids must be a list")

    scope_eligibility_entries = payload.get("scope_eligibility_entries")
    if not isinstance(scope_eligibility_entries, list):
        raise ValueError("scope_eligibility_entries must be a list")

    if len(scope_eligibility_entries) != scope_count:
        raise ValueError("scope_count must match scope_eligibility_entries length")

    if (
        auto_included_scope_count + excluded_scope_count + review_ambiguous_scope_count
        != scope_count
    ):
        raise ValueError("scope eligibility counts must sum to scope_count")

    counted_statuses: Counter[str] = Counter()
    seen_scope_ids: set[str] = set()
    entry_scope_ids: list[str] = []

    for entry in scope_eligibility_entries:
        if not isinstance(entry, dict):
            raise ValueError("each scope_eligibility_entries item must be an object")
        scope_id = _require_str(entry.get("scope_id"), field="scope_id")
        if scope_id in seen_scope_ids:
            raise ValueError(f"duplicate scope_id in eligibility entries: {scope_id!r}")
        seen_scope_ids.add(scope_id)
        entry_scope_ids.append(scope_id)

        heading_path = entry.get("heading_path")
        if not isinstance(heading_path, list):
            raise ValueError(f"scope {scope_id!r} heading_path must be a list")
        source_unit_ids = entry.get("source_unit_ids")
        if not isinstance(source_unit_ids, list):
            raise ValueError(f"scope {scope_id!r} source_unit_ids must be a list")

        for forbidden in (
            "study_context",
            "time_anchor",
            "population_context",
            "comparison_type",
            "candidate_id",
            "match_projection",
            "reject_audit",
            "tagged_items",
            "route_qc",
            "processing_disposition",
        ):
            if forbidden in entry:
                raise ValueError(f"scope {scope_id!r} must not include {forbidden!r}")

        decision = _validate_eligibility_decision(
            entry.get("eligibility_decision"),
            scope_id=scope_id,
        )
        counted_statuses[decision["status"]] += 1

    if counted_statuses.get("auto_included", 0) != auto_included_scope_count:
        raise ValueError("auto_included_scope_count inconsistent with scope_eligibility_entries")
    if counted_statuses.get("review_ambiguous", 0) != review_ambiguous_scope_count:
        raise ValueError("review_ambiguous_scope_count inconsistent with scope_eligibility_entries")
    excluded_from_entries = scope_count - (
        counted_statuses.get("auto_included", 0)
        + counted_statuses.get("review_ambiguous", 0)
    )
    if excluded_from_entries != excluded_scope_count:
        raise ValueError("excluded_scope_count inconsistent with scope_eligibility_entries")

    for status in HEADING_SCOPE_ELIGIBILITY_STATUSES:
        if eligibility_status_counts.get(status, 0) != counted_statuses.get(status, 0):
            raise ValueError(
                f"eligibility_status_counts[{status!r}] inconsistent with scope_eligibility_entries"
            )

    expected_auto_ids = [
        scope_id
        for scope_id, entry in zip(entry_scope_ids, scope_eligibility_entries)
        if isinstance(entry, dict)
        and isinstance(entry.get("eligibility_decision"), dict)
        and entry["eligibility_decision"].get("status") == "auto_included"
    ]
    if [str(item) for item in auto_included_scope_ids] != expected_auto_ids:
        raise ValueError("auto_included_scope_ids inconsistent with scope_eligibility_entries")

    if source_scope_assessments_payload is not None:
        source_scopes = source_scope_assessments_payload.get("scope_assessments") or []
        if not isinstance(source_scopes, list):
            raise ValueError("source scope_assessments must be a list")
        source_scope_ids = [
            _require_str(item.get("scope_id"), field="scope_id")
            for item in source_scopes
            if isinstance(item, dict)
        ]
        if entry_scope_ids != source_scope_ids:
            raise ValueError(
                "eligibility scope IDs must match source scope_assessments scope IDs in order"
            )
