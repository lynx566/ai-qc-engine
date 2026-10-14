"""Load persisted canonical document_consistency_qc flow execution state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    validate_flow_run_summary,
)
from artifacts.request_file_intake import (
    REQUEST_FILE_INTAKE_RESULT_FILENAME,
    validate_request_file_intake_result,
)
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.io import load_json

from execution_flow.document_consistency_qc.contracts import (
    CandidateScopeDecisionMode,
    DocumentConsistencyQcCapabilityConfig,
    FilterJobCandidateScopeSelection,
)
from execution_flow.document_consistency_qc.execution_provenance import (
    DOCUMENT_CONSISTENCY_QC_FLOW_STAGE,
    FlowRunExecution,
    FlowRunFilterJobProvenance,
    FlowRunProjectionJobProvenance,
    FlowRunRouteSemanticModuleProvenance,
    FlowRunSlotProvenance,
    resolve_flow_status,
)


class FlowResumeError(ValueError):
    """Raised when a canonical flow resume request is invalid."""


def resolve_flow_run_output_dir(*, project_root: Path, flow_run_id: str) -> Path:
    prefix = f"{DOCUMENT_CONSISTENCY_QC_FLOW_STAGE}_"
    if not flow_run_id.startswith(prefix):
        raise FlowResumeError(
            f"flow_run_id must start with {prefix!r}, got {flow_run_id!r}"
        )
    session_dir = flow_run_id.removeprefix(prefix)
    output_dir = (
        project_root / "runs" / DOCUMENT_CONSISTENCY_QC_FLOW_STAGE / session_dir
    )
    if not output_dir.is_dir():
        raise FlowResumeError(
            f"canonical flow output directory not found for flow_run_id={flow_run_id!r}"
        )
    return output_dir


def _filter_job_provenance_from_record(
    record: dict[str, Any],
) -> FlowRunFilterJobProvenance:
    return FlowRunFilterJobProvenance(
        filter_job_id=record["filter_job_id"],
        source_language=record["source_language"],
        zone_config_name=record["zone_config_name"],
        zone_config_version=record["zone_config_version"],
        filter_run_id=record["filter_run_id"],
        output_dir=record["output_dir"],
        zone_match_bundle_path=record["zone_match_bundle_path"],
        coverage_bundle_path=record["coverage_bundle_path"],
        run_summary_path=record["run_summary_path"],
    )


def _projection_job_provenance_from_record(
    record: dict[str, Any],
) -> FlowRunProjectionJobProvenance:
    return FlowRunProjectionJobProvenance(
        filter_job_id=record["filter_job_id"],
        projection_run_id=record["projection_run_id"],
        output_dir=record["output_dir"],
        projection_bundle_path=record["projection_bundle_path"],
        run_summary_path=record["run_summary_path"],
        projected_source_count=record["projected_source_count"],
        semantic_outcome_count=record["semantic_outcome_count"],
    )


def _route_module_provenance_from_record(
    record: dict[str, Any],
) -> FlowRunRouteSemanticModuleProvenance:
    return FlowRunRouteSemanticModuleProvenance(
        semantic_module_id=record["semantic_module_id"],
        selected_projected_source_count=record["selected_projected_source_count"],
        route_invoked=record["route_invoked"],
        route_run_id=record.get("route_run_id"),
        output_dir=record.get("output_dir"),
        routing_manifest_path=record.get("routing_manifest_path"),
        run_summary_path=record.get("run_summary_path"),
        evidence_source_preparation_invoked=record[
            "evidence_source_preparation_invoked"
        ],
        evidence_source_preparation_run_id=record.get(
            "evidence_source_preparation_run_id"
        ),
        evidence_source_preparation_stage_executor_id=record.get(
            "evidence_source_preparation_stage_executor_id"
        ),
        evidence_source_preparation_declared_output_path=record.get(
            "evidence_source_preparation_declared_output_path"
        ),
        evidence_source_preparation_run_summary_path=record.get(
            "evidence_source_preparation_run_summary_path"
        ),
    )


def _slot_provenance_from_record(record: dict[str, Any]) -> FlowRunSlotProvenance:
    filter_job_ids = tuple(record.get("filter_job_ids") or ())
    filter_jobs = [
        _filter_job_provenance_from_record(job)
        for job in (record.get("filter_jobs") or [])
    ]
    projection_jobs = [
        _projection_job_provenance_from_record(job)
        for job in (record.get("projection_jobs") or [])
    ]
    route_semantic_modules = [
        _route_module_provenance_from_record(module)
        for module in (record.get("route_semantic_modules") or [])
    ]
    return FlowRunSlotProvenance(
        slot_id=record["slot_id"],
        extract_config_id=record["extract_config_id"],
        prepare_analysis_config_id=PrepareAnalysisConfigId(
            value=record["prepare_analysis_config_id"]
        ),
        filter_job_ids=filter_job_ids,
        status=record["status"],
        intake_run_id=record.get("intake_run_id"),
        file_hash=record.get("file_hash"),
        original_file_name=record.get("original_file_name"),
        doc_id=record.get("doc_id"),
        extract_run_id=record.get("extract_run_id"),
        prepare_analysis_run_id=record.get("prepare_analysis_run_id"),
        analysis_bundle_path=record.get("analysis_bundle_path"),
        block_manifest_path=record.get("block_manifest_path"),
        prepare_analysis_run_summary_path=record.get(
            "prepare_analysis_run_summary_path"
        ),
        doc_meta_run_id=record.get("doc_meta_run_id"),
        doc_meta_output_dir=record.get("doc_meta_output_dir"),
        doc_meta_bundle_path=record.get("doc_meta_bundle_path"),
        doc_meta_run_summary_path=record.get("doc_meta_run_summary_path"),
        filter_jobs=filter_jobs,
        projection_jobs=projection_jobs,
        route_semantic_modules=route_semantic_modules,
        candidate_scope_decision_path=record.get("candidate_scope_decision_path"),
    )


def load_flow_run_execution(
    *,
    project_root: Path,
    flow_run_id: str,
    require_doc_meta_bundle_reference: bool = True,
) -> FlowRunExecution:
    """Load a checkpoint; advisory Setup reads may tolerate a missing meta reference.

    Execution/resume callers retain strict artifact validation by default.
    """
    output_dir = resolve_flow_run_output_dir(
        project_root=project_root,
        flow_run_id=flow_run_id,
    )
    summary_path = output_dir / FLOW_RUN_SUMMARY_FILENAME
    if not summary_path.is_file():
        raise FlowResumeError(
            f"flow_run_summary not found for flow_run_id={flow_run_id!r}"
        )
    summary = load_json(summary_path)
    validate_flow_run_summary(
        summary, require_doc_meta_bundle_reference=require_doc_meta_bundle_reference
    )
    if summary["flow_run_id"] != flow_run_id:
        raise FlowResumeError("flow_run_summary.flow_run_id does not match request")

    decision_mode = CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
    raw_mode = summary.get("candidate_scope_decision_mode")
    if isinstance(raw_mode, str) and raw_mode.strip():
        try:
            decision_mode = CandidateScopeDecisionMode(raw_mode.strip())
        except ValueError as exc:
            raise FlowResumeError(
                f"unsupported candidate_scope_decision_mode: {raw_mode!r}"
            ) from exc

    return FlowRunExecution(
        flow_id=str(summary["flow_id"]),
        flow_run_id=flow_run_id,
        output_dir=output_dir,
        capability_id=summary["capability_id"],
        source_language=summary["source_language"],
        created_at=summary["created_at"],
        slot_provenance=[
            _slot_provenance_from_record(slot) for slot in summary["slots"]
        ],
        candidate_scope_decision_mode=decision_mode,
    )


def can_resume_candidate_scope(execution: FlowRunExecution) -> bool:
    """Return whether the flow is still paused at the Candidate Scope checkpoint."""

    return (
        resolve_flow_status(execution.slot_provenance)
        == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    )


def _slot_has_candidate_scope_read_prerequisites(
    slot_provenance: FlowRunSlotProvenance,
) -> bool:
    doc_id = str(slot_provenance.doc_id or "").strip()
    if not doc_id:
        return False
    if not slot_provenance.filter_job_ids:
        return False
    if not slot_provenance.filter_jobs:
        return False
    analysis_bundle_path = Path(slot_provenance.analysis_bundle_path or "")
    block_manifest_path = Path(slot_provenance.block_manifest_path or "")
    return analysis_bundle_path.is_file() and block_manifest_path.is_file()


def resolve_candidate_scope_readable_slots(
    execution: FlowRunExecution,
) -> tuple[FlowRunSlotProvenance, ...]:
    """Return slots whose persisted Candidate Scope artifacts can be read."""

    if can_resume_candidate_scope(execution):
        return resolve_paused_candidate_scope_slots(execution)

    historical_slots = tuple(
        slot
        for slot in execution.slot_provenance
        if _slot_has_candidate_scope_read_prerequisites(slot)
        and str(slot.candidate_scope_decision_path or "").strip()
    )
    if historical_slots:
        return historical_slots

    flow_status = resolve_flow_status(execution.slot_provenance)
    if any(
        _slot_has_candidate_scope_read_prerequisites(slot)
        for slot in execution.slot_provenance
    ):
        raise FlowResumeError(
            f"flow {execution.flow_run_id!r} reached Candidate Scope but persisted "
            f"decision artifacts are unavailable (status={flow_status!r})"
        )
    raise FlowResumeError(
        f"flow {execution.flow_run_id!r} never reached Candidate Scope "
        f"(status={flow_status!r})"
    )


def resolve_paused_candidate_scope_slots(
    execution: FlowRunExecution,
) -> tuple[FlowRunSlotProvenance, ...]:
    """Return all paused Candidate Scope slots in canonical flow order."""

    flow_status = resolve_flow_status(execution.slot_provenance)
    if flow_status != FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        raise FlowResumeError(
            f"flow {execution.flow_run_id!r} is not paused_at_candidate_scope "
            f"(status={flow_status!r})"
        )

    paused_slots = tuple(
        slot
        for slot in execution.slot_provenance
        if slot.status == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    )
    if not paused_slots:
        raise FlowResumeError(
            f"flow {execution.flow_run_id!r} has no slot paused_at_candidate_scope"
        )
    return paused_slots


def resolve_unique_paused_candidate_scope_slot(
    execution: FlowRunExecution,
) -> FlowRunSlotProvenance:
    """Return the sole paused Candidate Scope slot for one canonical flow."""

    paused_slots = resolve_paused_candidate_scope_slots(execution)
    if len(paused_slots) > 1:
        raise FlowResumeError(
            "multiple slots are paused_at_candidate_scope for "
            f"flow_run_id={execution.flow_run_id!r}: "
            f"{[slot.slot_id for slot in paused_slots]!r}"
        )
    return paused_slots[0]


def _slot_provenance_by_id(
    execution: FlowRunExecution,
    *,
    slot_id: str,
) -> FlowRunSlotProvenance:
    try:
        return next(
            slot for slot in execution.slot_provenance if slot.slot_id == slot_id
        )
    except StopIteration:
        raise FlowResumeError(
            f"slot_id {slot_id!r} is not configured for flow_run_id="
            f"{execution.flow_run_id!r}"
        ) from None


def validate_candidate_scope_resume_decisions(
    execution: FlowRunExecution,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    *,
    flow_run_id: str,
    candidate_scope_decisions_by_slot: Mapping[
        str, Sequence[FilterJobCandidateScopeSelection]
    ],
) -> tuple[FlowRunSlotProvenance, ...]:
    """Validate one flow-level Candidate Scope resume and return paused slots in order."""

    if execution.flow_run_id != flow_run_id:
        raise FlowResumeError("flow_run_id does not match loaded execution")
    if execution.capability_id != capability_config.capability_id:
        raise FlowResumeError(
            "resume capability_id does not match persisted flow capability_id"
        )

    expected_slot_ids = tuple(slot.slot_id for slot in capability_config.slots)
    if not expected_slot_ids:
        raise FlowResumeError("capability_config has no configured slots")

    decision_slot_ids = frozenset(candidate_scope_decisions_by_slot)
    expected_slot_id_set = frozenset(expected_slot_ids)
    if decision_slot_ids != expected_slot_id_set:
        missing = sorted(expected_slot_id_set - decision_slot_ids)
        extra = sorted(decision_slot_ids - expected_slot_id_set)
        if missing and extra:
            raise FlowResumeError(
                "candidate_scope_decisions_by_slot is missing paused slot(s) "
                f"{missing!r} and includes unknown slot(s) {extra!r}"
            )
        if missing:
            raise FlowResumeError(
                "candidate_scope_decisions_by_slot is missing paused slot(s) "
                f"{missing!r}"
            )
        raise FlowResumeError(
            f"candidate_scope_decisions_by_slot includes unknown slot(s) {extra!r}"
        )

    paused_slots: list[FlowRunSlotProvenance] = []
    for slot_id in expected_slot_ids:
        slot_provenance = _slot_provenance_by_id(execution, slot_id=slot_id)
        if slot_provenance.status == "not_started":
            raise FlowResumeError(
                f"slot {slot_id!r} is not_started; flow is not ready for "
                "Candidate Scope resume"
            )
        if slot_provenance.status != SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
            raise FlowResumeError(
                f"slot {slot_id!r} is not paused_at_candidate_scope "
                f"(status={slot_provenance.status!r})"
            )
        paused_slots.append(slot_provenance)

    flow_status = resolve_flow_status(execution.slot_provenance)
    if flow_status != FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        raise FlowResumeError(
            f"flow {execution.flow_run_id!r} is not paused_at_candidate_scope "
            f"(status={flow_status!r})"
        )

    return tuple(paused_slots)


def validate_paused_flow_for_resume(
    execution: FlowRunExecution,
    *,
    flow_run_id: str,
    slot_id: str,
) -> FlowRunSlotProvenance:
    if execution.flow_run_id != flow_run_id:
        raise FlowResumeError("flow_run_id does not match loaded execution")
    slot_provenance = _slot_provenance_by_id(execution, slot_id=slot_id)
    if slot_provenance.status != SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        raise FlowResumeError(
            f"slot {slot_id!r} is not paused_at_candidate_scope "
            f"(status={slot_provenance.status!r})"
        )
    return slot_provenance


def build_doc_meta_report_from_provenance(
    slot_provenance: FlowRunSlotProvenance,
) -> dict[str, Any]:
    if slot_provenance.doc_meta_bundle_path is None:
        raise FlowResumeError("paused slot provenance is missing doc_meta_bundle_path")
    doc_meta_bundle_path = Path(slot_provenance.doc_meta_bundle_path)
    doc_meta_bundle = load_json(doc_meta_bundle_path)
    return {
        "output_dir": slot_provenance.doc_meta_output_dir,
        "doc_meta_bundle_path": slot_provenance.doc_meta_bundle_path,
        "doc_meta_bundle": doc_meta_bundle,
        "run_summary_path": slot_provenance.doc_meta_run_summary_path,
    }


def build_resumed_upstream_stubs(
    slot_provenance: FlowRunSlotProvenance,
    *,
    admitted_source: DocumentIntakeSourceBinding,
) -> tuple[Any, Any, Any]:
    """Return placeholder upstream values for resumed slots."""
    return (
        admitted_source,
        SimpleNamespace(result=SimpleNamespace(run_id="resumed")),
        SimpleNamespace(documents=[SimpleNamespace(run_id="resumed")]),
    )


def recover_legacy_resumed_admitted_source(
    *,
    project_root: Path,
    flow_root: Path,
    slot_provenance: FlowRunSlotProvenance,
) -> DocumentIntakeSourceBinding:
    """Recover admitted-source facts from a legacy Flow-local Intake."""

    label = f"slot {slot_provenance.slot_id!r}"
    intake_dir = flow_root / "participants" / slot_provenance.slot_id / "intake"
    result_path = intake_dir / REQUEST_FILE_INTAKE_RESULT_FILENAME
    summary_path = intake_dir / "run_summary.json"
    try:
        result = load_json(result_path)
        validate_request_file_intake_result(result)
        summary = load_json(summary_path)
        raw_source_path = summary["inputs"]["source_file"]
        if not isinstance(raw_source_path, str) or not raw_source_path.strip():
            raise ValueError("run_summary.inputs.source_file is required")
        source_path = Path(raw_source_path)
        if not source_path.is_absolute():
            source_path = project_root / source_path
        source_path = source_path.resolve()
        if not source_path.is_file():
            raise ValueError("run_summary.inputs.source_file is not a regular file")

        document = result["document"]
        file_hash = document["file_hash"]
        original_file_name = document["original_file_name"]
        if slot_provenance.file_hash not in (None, file_hash):
            raise ValueError("Flow summary and Intake file_hash disagree")
        if source_path.name != original_file_name:
            raise ValueError("Intake original_file_name and source path disagree")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise FlowResumeError(
            f"legacy resume source provenance unavailable for {label}: {exc}"
        ) from exc

    slot_provenance.file_hash = file_hash
    slot_provenance.original_file_name = original_file_name
    return DocumentIntakeSourceBinding(
        file_hash=file_hash,
        original_file_name=original_file_name,
        source_path=source_path,
    )


def resolve_resumed_admitted_source(
    *,
    project_root: Path,
    flow_root: Path,
    slot_provenance: FlowRunSlotProvenance,
) -> DocumentIntakeSourceBinding:
    """Resolve a resumed slot without inventing missing source identity."""

    if slot_provenance.intake_run_id is not None or not (
        slot_provenance.file_hash and slot_provenance.original_file_name
    ):
        return recover_legacy_resumed_admitted_source(
            project_root=project_root,
            flow_root=flow_root,
            slot_provenance=slot_provenance,
        )
    return DocumentIntakeSourceBinding(
        file_hash=slot_provenance.file_hash,
        original_file_name=slot_provenance.original_file_name,
        source_path=Path(slot_provenance.analysis_bundle_path or "."),
    )


__all__ = [
    "FlowResumeError",
    "build_doc_meta_report_from_provenance",
    "build_resumed_upstream_stubs",
    "can_resume_candidate_scope",
    "load_flow_run_execution",
    "recover_legacy_resumed_admitted_source",
    "resolve_candidate_scope_readable_slots",
    "resolve_flow_run_output_dir",
    "resolve_paused_candidate_scope_slots",
    "resolve_resumed_admitted_source",
    "resolve_unique_paused_candidate_scope_slot",
    "validate_candidate_scope_resume_decisions",
    "validate_paused_flow_for_resume",
]
