"""Application-facing create-flow result projection for Document Consistency QC."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    validate_flow_run_summary,
)
from runtime.io import load_json

from application.document_consistency_qc.document_type_result import (
    DocumentConsistencyQcApplicationResult,
)


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcCreateFlowResult:
    """Normalized execution transition returned by the product create-flow facade."""

    flow_id: str
    flow_run_id: str
    flow_status: str
    paused_at_candidate_scope: bool
    paused_slot_ids: tuple[str, ...]
    paused_slot_id: str | None
    completed: bool
    flow_run_summary_path: Path


def build_document_consistency_qc_create_flow_result(
    application_result: DocumentConsistencyQcApplicationResult,
) -> DocumentConsistencyQcCreateFlowResult:
    """Project one application result into a create-flow response."""

    flow_report = application_result.flow_report
    summary_path = flow_report.flow_run_summary_path
    summary = load_json(summary_path)
    validate_flow_run_summary(summary)
    flow_status = summary["status"]
    paused_slot_ids = _resolve_paused_slot_ids(summary)
    paused_slot_id = _compat_paused_slot_id(paused_slot_ids)
    paused_at_candidate_scope = flow_report.result.paused_at_candidate_scope
    completed = flow_status == "success" and not paused_at_candidate_scope
    return DocumentConsistencyQcCreateFlowResult(
        flow_id=str(summary["flow_id"]),
        flow_run_id=flow_report.flow_run_id,
        flow_status=flow_status,
        paused_at_candidate_scope=paused_at_candidate_scope,
        paused_slot_ids=paused_slot_ids,
        paused_slot_id=paused_slot_id,
        completed=completed,
        flow_run_summary_path=summary_path,
    )


def create_flow_result_to_mapping(
    result: DocumentConsistencyQcCreateFlowResult,
) -> dict[str, object]:
    """Serialize one create-flow result for transport layers."""

    return {
        "flow_id": result.flow_id,
        "flow_run_id": result.flow_run_id,
        "flow_status": result.flow_status,
        "paused_at_candidate_scope": result.paused_at_candidate_scope,
        "paused_slot_ids": list(result.paused_slot_ids),
        "paused_slot_id": result.paused_slot_id,
        "completed": result.completed,
        "flow_run_summary_path": result.flow_run_summary_path.as_posix(),
    }


def _resolve_paused_slot_ids(summary: dict[str, object]) -> tuple[str, ...]:
    if summary.get("status") != FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        return ()
    slots = summary.get("slots")
    if not isinstance(slots, list):
        return ()
    paused_slot_ids: list[str] = []
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        if slot.get("status") != SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
            continue
        slot_id = slot.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError("paused slot_id must be a non-empty string")
        paused_slot_ids.append(slot_id.strip())
    return tuple(paused_slot_ids)


def _compat_paused_slot_id(paused_slot_ids: tuple[str, ...]) -> str | None:
    """Backward-compatible single-slot projection; not authoritative for multi-slot."""

    if len(paused_slot_ids) == 1:
        return paused_slot_ids[0]
    return None


__all__ = [
    "DocumentConsistencyQcCreateFlowResult",
    "build_document_consistency_qc_create_flow_result",
    "create_flow_result_to_mapping",
]
