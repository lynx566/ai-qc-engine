"""Application read/write boundary for persisted finding review state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.finding_review_state import (
    FINDING_REVIEW_OPERATION_DIRNAME,
    FINDING_REVIEW_STATE_FILENAME,
    REVIEW_DECISIONS,
    build_finding_review_state_payload,
    should_persist_finding_review_entry,
    validate_finding_review_state,
)
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    resolve_flow_run_output_dir,
)
from runtime.io import load_json, save_json_atomic
from runtime.run_layout import utc_now_iso

_UNSET = object()


class FindingReviewError(Exception):
    """Base error for finding review persistence."""


class FindingReviewNotFoundError(FindingReviewError):
    """Flow or required persisted target could not be located."""


class FindingReviewValidationError(FindingReviewError):
    """Request or persisted review state failed validation."""


class FindingReviewPersistenceError(FindingReviewError):
    """Review state could not be persisted safely."""


@dataclass(frozen=True, slots=True)
class FindingReviewEntryReadModel:
    finding_id: str
    decision: str
    marked: bool
    note: str | None
    updated_at: str


@dataclass(frozen=True, slots=True)
class FindingReviewStateReadModel:
    flow_run_id: str
    findings: tuple[FindingReviewEntryReadModel, ...]


def resolve_finding_review_state_path(*, flow_root: Path) -> Path:
    return flow_root / FINDING_REVIEW_OPERATION_DIRNAME / FINDING_REVIEW_STATE_FILENAME


def _finding_review_state_to_read_model(
    *,
    flow_run_id: str,
    findings: Mapping[str, Mapping[str, Any]],
) -> FindingReviewStateReadModel:
    entries = tuple(
        FindingReviewEntryReadModel(
            finding_id=finding_id,
            decision=str(entry["decision"]),
            marked=bool(entry["marked"]),
            note=entry.get("note"),
            updated_at=str(entry["updated_at"]),
        )
        for finding_id, entry in sorted(findings.items())
    )
    return FindingReviewStateReadModel(flow_run_id=flow_run_id, findings=entries)


def finding_review_state_to_mapping(
    model: FindingReviewStateReadModel,
) -> dict[str, object]:
    return {
        "flow_run_id": model.flow_run_id,
        "findings": {
            entry.finding_id: {
                "finding_id": entry.finding_id,
                "decision": entry.decision,
                "marked": entry.marked,
                **({"note": entry.note} if entry.note else {}),
                "updated_at": entry.updated_at,
            }
            for entry in model.findings
        },
    }


def _resolve_flow_root(*, project_root: Path, flow_run_id: str) -> Path:
    try:
        return resolve_flow_run_output_dir(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except FlowResumeError as exc:
        raise FindingReviewNotFoundError(str(exc)) from exc


def _load_validated_artifact(
    *,
    path: Path,
    flow_run_id: str,
) -> dict[str, Any]:
    if not path.is_file():
        return build_finding_review_state_payload(flow_run_id=flow_run_id, findings={})

    payload = load_json(path)
    validated = validate_finding_review_state(payload)
    if validated["flow_run_id"] != flow_run_id:
        raise FindingReviewValidationError(
            "finding review artifact flow_run_id does not match request"
        )
    return validated


def _load_read_model_from_path(
    *,
    path: Path,
    flow_run_id: str,
) -> FindingReviewStateReadModel:
    validated = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    return _finding_review_state_to_read_model(
        flow_run_id=validated["flow_run_id"],
        findings=validated["findings"],
    )


def _entry_map_from_artifact(artifact: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    findings = artifact.get("findings")
    if not isinstance(findings, Mapping):
        return {}
    return {str(key): dict(value) for key, value in findings.items()}


def _normalize_requested_note(note: str | None | object) -> tuple[bool, str | None]:
    if note is _UNSET:
        return False, None
    if note is None:
        return True, None
    if not isinstance(note, str):
        raise FindingReviewValidationError("note must be a string when provided")
    stripped = note.strip()
    return True, stripped or None


def _effective_entry_state(
    *,
    entries: Mapping[str, Mapping[str, Any]],
    finding_id: str,
) -> tuple[str, bool, str | None]:
    existing = entries.get(finding_id)
    if existing is None:
        return "pending", False, None
    decision = str(existing.get("decision", "pending"))
    if decision not in REVIEW_DECISIONS:
        decision = "pending"
    return (
        decision,
        bool(existing.get("marked", False)),
        existing.get("note"),
    )


def _normalize_decision_patch(
    *,
    decision: str | object = _UNSET,
    resolved: bool | object = _UNSET,
) -> str | object:
    if decision is not _UNSET and resolved is not _UNSET:
        raise FindingReviewValidationError(
            "provide decision or resolved, not both"
        )
    if decision is not _UNSET:
        if not isinstance(decision, str) or decision not in REVIEW_DECISIONS:
            raise FindingReviewValidationError(
                f"decision must be one of {sorted(REVIEW_DECISIONS)!r} when provided"
            )
        return decision
    if resolved is not _UNSET:
        if not isinstance(resolved, bool):
            raise FindingReviewValidationError("resolved must be a boolean when provided")
        return "confirmed" if resolved else "pending"
    return _UNSET


def _persist_artifact(
    *,
    path: Path,
    artifact: Mapping[str, Any],
) -> None:
    findings = artifact.get("findings")
    if not isinstance(findings, Mapping) or not findings:
        if path.is_file():
            path.unlink()
        return

    try:
        save_json_atomic(path, dict(artifact))
    except OSError as exc:
        raise FindingReviewPersistenceError(str(exc)) from exc


def load_finding_review_state(
    *,
    project_root: Path,
    flow_run_id: str,
) -> FindingReviewStateReadModel:
    """Load persisted review state for one flow; missing artifact is empty."""

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_finding_review_state_path(flow_root=flow_root)
    return _load_read_model_from_path(path=path, flow_run_id=flow_run_id)


def persist_finding_review_entry(
    *,
    project_root: Path,
    flow_run_id: str,
    finding_id: str,
    decision: str | object = _UNSET,
    resolved: bool | object = _UNSET,
    marked: bool | object = _UNSET,
    note: str | None | object = _UNSET,
) -> FindingReviewStateReadModel:
    """Merge an already admitted review mutation into the Flow artifact."""

    if decision is _UNSET and resolved is _UNSET and marked is _UNSET and note is _UNSET:
        raise FindingReviewValidationError(
            "at least one of decision, resolved, marked, or note must be provided"
        )

    normalized_decision = _normalize_decision_patch(decision=decision, resolved=resolved)
    if marked is not _UNSET and not isinstance(marked, bool):
        raise FindingReviewValidationError("marked must be a boolean when provided")

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_finding_review_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _entry_map_from_artifact(artifact)

    current_decision, current_marked, current_note = _effective_entry_state(
        entries=entries,
        finding_id=finding_id,
    )
    next_decision = (
        current_decision if normalized_decision is _UNSET else normalized_decision
    )
    next_marked = current_marked if marked is _UNSET else marked
    note_provided, requested_note = _normalize_requested_note(note)
    next_note = current_note if not note_provided else requested_note

    if (
        next_decision == current_decision
        and next_marked == current_marked
        and next_note == current_note
    ):
        return _finding_review_state_to_read_model(
            flow_run_id=flow_run_id,
            findings=entries,
        )

    if should_persist_finding_review_entry(
        decision=next_decision,
        marked=next_marked,
        note=next_note,
    ):
        entry: dict[str, Any] = {
            "decision": next_decision,
            "marked": next_marked,
            "updated_at": utc_now_iso(),
        }
        if next_note is not None:
            entry["note"] = next_note
        entries[finding_id] = entry
    else:
        entries.pop(finding_id, None)

    next_artifact = build_finding_review_state_payload(
        flow_run_id=flow_run_id,
        findings=entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)
    return _finding_review_state_to_read_model(
        flow_run_id=flow_run_id,
        findings=entries,
    )


__all__ = [
    "FindingReviewEntryReadModel",
    "FindingReviewError",
    "FindingReviewNotFoundError",
    "FindingReviewPersistenceError",
    "FindingReviewStateReadModel",
    "FindingReviewValidationError",
    "finding_review_state_to_mapping",
    "load_finding_review_state",
    "persist_finding_review_entry",
    "resolve_finding_review_state_path",
]
