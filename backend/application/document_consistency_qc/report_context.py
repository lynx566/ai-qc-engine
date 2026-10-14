"""Formal persisted Flow context for Task report composition, no EC output reads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from application.document_consistency_qc.document_read import (
    DocumentReadIdentityError,
    load_document_read_execution,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    validate_flow_run_summary,
)
from runtime.io import load_json


@dataclass(frozen=True, slots=True)
class ReportFlowContext:
    flow_id: str
    flow_run_id: str
    capability_id: str
    outcome: str
    created_at: str
    completed_at: str | None
    participants: tuple[tuple[str, str, str], ...]  # slot, doc, semantic module
    route_modules: tuple[tuple[str, str], ...]


def load_report_flow_context(
    *, project_root: Path, flow_run_id: str
) -> ReportFlowContext:
    execution = load_document_read_execution(
        project_root=project_root, flow_run_id=flow_run_id
    )
    summary = load_json(execution.output_dir / FLOW_RUN_SUMMARY_FILENAME)
    validate_flow_run_summary(summary)
    if (
        summary["flow_run_id"] != execution.flow_run_id
        or summary["capability_id"] != execution.capability_id
    ):
        raise DocumentReadIdentityError("Flow summary identity changed during read")
    comparison = summary.get("evidence_comparison") or {}
    if (
        comparison.get("capability_id", execution.capability_id)
        != execution.capability_id
    ):
        raise DocumentReadIdentityError("comparison capability does not match Flow")
    slots = {slot.slot_id: slot for slot in execution.slot_provenance}
    participants = []
    for participant in comparison.get("participants") or []:
        slot_id = participant["slot_id"]
        if slot_id not in slots or not slots[slot_id].doc_id:
            raise DocumentReadIdentityError(
                "comparison participant not in Flow membership"
            )
        participants.append(
            (slot_id, slots[slot_id].doc_id, participant["semantic_module_id"])
        )
    return ReportFlowContext(
        execution.flow_id,
        execution.flow_run_id,
        execution.capability_id,
        summary["status"],
        summary["created_at"],
        summary.get("completed_at"),
        tuple(participants),
        tuple(
            (slot.slot_id, module.semantic_module_id)
            for slot in execution.slot_provenance
            for module in slot.route_semantic_modules
        ),
    )
