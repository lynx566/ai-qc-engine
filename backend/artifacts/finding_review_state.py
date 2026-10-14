"""Canonical finding review state artifact contract for Document Consistency QC."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

FINDING_REVIEW_STATE_FILENAME = "review_state.json"
FINDING_REVIEW_OPERATION_DIRNAME = "finding_review"
FINDING_REVIEW_STATE_ARTIFACT_TYPE = "document_consistency_qc_finding_review_state"
FINDING_REVIEW_STATE_SCHEMA_VERSION = "0.3.0"
FINDING_REVIEW_STATE_V020_SCHEMA_VERSION = "0.2.0"
FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION = "0.1.0"
SUPPORTED_FINDING_REVIEW_STATE_SCHEMA_VERSIONS = frozenset(
    {
        FINDING_REVIEW_STATE_SCHEMA_VERSION,
        FINDING_REVIEW_STATE_V020_SCHEMA_VERSION,
        FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION,
    }
)

FINDING_ID_PATTERN = re.compile(r"^L\d{3}$")

LEGACY_REVIEW_STATES = frozenset({"normal", "reviewed", "flagged"})
REVIEW_DECISIONS = frozenset({"pending", "confirmed", "ignored"})


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a boolean")
    return value


def _normalize_note(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("note must be a string when present")
    stripped = value.strip()
    return stripped or None


def _decision_from_resolved(resolved: bool) -> str:
    return "confirmed" if resolved else "pending"


def _migrate_legacy_review_state(review_state: str) -> tuple[str, bool]:
    if review_state == "reviewed":
        return "confirmed", False
    if review_state == "flagged":
        return "pending", True
    return "pending", False


def validate_finding_review_entry(
    payload: Mapping[str, Any],
    *,
    finding_id: str,
) -> dict[str, Any]:
    if FINDING_ID_PATTERN.fullmatch(finding_id) is None:
        raise ValueError(f"finding_id must match {FINDING_ID_PATTERN.pattern!r}")

    updated_at = _require_str(payload.get("updated_at"), field="updated_at")
    note = _normalize_note(payload.get("note"))

    if "review_state" in payload:
        review_state = _require_str(payload.get("review_state"), field="review_state")
        if review_state not in LEGACY_REVIEW_STATES:
            raise ValueError(
                f"review_state must be one of {sorted(LEGACY_REVIEW_STATES)!r}"
            )
        decision, marked = _migrate_legacy_review_state(review_state)
        if review_state == "normal" and note is None:
            raise ValueError("persisted entry with normal review_state requires note")
    elif "decision" in payload:
        decision = _require_str(payload.get("decision"), field="decision")
        if decision not in REVIEW_DECISIONS:
            raise ValueError(
                f"decision must be one of {sorted(REVIEW_DECISIONS)!r}"
            )
        marked = _require_bool(payload.get("marked"), field="marked")
    else:
        resolved = _require_bool(payload.get("resolved"), field="resolved")
        marked = _require_bool(payload.get("marked"), field="marked")
        decision = _decision_from_resolved(resolved)

    if not should_persist_finding_review_entry(
        decision=decision,
        marked=marked,
        note=note,
    ):
        raise ValueError(
            "persisted entry requires decision confirmed/ignored, marked=true, or note"
        )

    normalized: dict[str, Any] = {
        "decision": decision,
        "marked": marked,
        "updated_at": updated_at,
    }
    if note is not None:
        normalized["note"] = note
    return normalized


def should_persist_finding_review_entry(
    *,
    decision: str,
    marked: bool,
    note: str | None,
) -> bool:
    if decision in {"confirmed", "ignored"}:
        return True
    if marked:
        return True
    return note is not None


def validate_finding_review_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("artifact_type") != FINDING_REVIEW_STATE_ARTIFACT_TYPE:
        raise ValueError("finding_review_state.artifact_type mismatch")

    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_FINDING_REVIEW_STATE_SCHEMA_VERSIONS:
        raise ValueError("finding_review_state.schema_version mismatch")

    flow_run_id = _require_str(payload.get("flow_run_id"), field="flow_run_id")
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, Mapping):
        raise TypeError("findings must be an object")

    normalized_findings: dict[str, dict[str, Any]] = {}
    for finding_id, entry in raw_findings.items():
        if not isinstance(finding_id, str) or FINDING_ID_PATTERN.fullmatch(finding_id) is None:
            raise ValueError(f"findings key must match {FINDING_ID_PATTERN.pattern!r}")
        if not isinstance(entry, Mapping):
            raise TypeError(f"findings[{finding_id!r}] must be an object")
        normalized_findings[finding_id] = validate_finding_review_entry(
            entry,
            finding_id=finding_id,
        )

    return {
        "artifact_type": FINDING_REVIEW_STATE_ARTIFACT_TYPE,
        "schema_version": FINDING_REVIEW_STATE_SCHEMA_VERSION,
        "flow_run_id": flow_run_id,
        "findings": normalized_findings,
    }


def build_finding_review_state_payload(
    *,
    flow_run_id: str,
    findings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_findings = {
        finding_id: validate_finding_review_entry(entry, finding_id=finding_id)
        for finding_id, entry in findings.items()
    }
    return validate_finding_review_state(
        {
            "artifact_type": FINDING_REVIEW_STATE_ARTIFACT_TYPE,
            "schema_version": FINDING_REVIEW_STATE_SCHEMA_VERSION,
            "flow_run_id": flow_run_id,
            "findings": normalized_findings,
        }
    )


__all__ = [
    "FINDING_ID_PATTERN",
    "FINDING_REVIEW_OPERATION_DIRNAME",
    "FINDING_REVIEW_STATE_ARTIFACT_TYPE",
    "FINDING_REVIEW_STATE_FILENAME",
    "FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION",
    "FINDING_REVIEW_STATE_SCHEMA_VERSION",
    "FINDING_REVIEW_STATE_V020_SCHEMA_VERSION",
    "LEGACY_REVIEW_STATES",
    "REVIEW_DECISIONS",
    "SUPPORTED_FINDING_REVIEW_STATE_SCHEMA_VERSIONS",
    "build_finding_review_state_payload",
    "should_persist_finding_review_entry",
    "validate_finding_review_entry",
    "validate_finding_review_state",
]
