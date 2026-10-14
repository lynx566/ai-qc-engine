"""Flow execution identity and flow_run_summary persistence coordination."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from artifacts.document_consistency_qc_flow_run_summary import (
    DOCUMENT_CONSISTENCY_QC_FLOW_ID,
    FLOW_RUN_SUMMARY_FILENAME,
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    build_flow_run_slot_record,
    build_flow_run_summary,
    validate_flow_run_summary,
)
from operations.evidence_comparison.handoff import EvidenceComparisonHandoffResolution
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from runtime.io import load_json, save_json
from runtime.run_ids import (
    build_run_id_from_session_dir,
    build_session_dir_segment,
    utc_run_stamp,
)
from runtime.run_layout import sanitize_run_segment, utc_now_iso

from execution_flow.document_consistency_qc.contracts import CandidateScopeDecisionMode

DOCUMENT_CONSISTENCY_QC_FLOW_STAGE = DOCUMENT_CONSISTENCY_QC_FLOW_ID
PARTICIPANTS_DIRNAME = "participants"
INTAKE_OPERATION_DIRNAME = "intake"
EXTRACT_OPERATION_DIRNAME = "extract"
PREPARE_ANALYSIS_OPERATION_DIRNAME = "prepare_analysis"
DOC_META_OPERATION_DIRNAME = "doc_meta"
FILTER_OPERATION_DIRNAME = "filter"
CANDIDATE_SCOPE_OPERATION_DIRNAME = "candidate_scope"
FILTER_OUTPUT_PROJECTION_OPERATION_DIRNAME = "filter_output_projection"
ROUTE_OPERATION_DIRNAME = "route"
EVIDENCE_SOURCE_PREPARATION_OPERATION_DIRNAME = "evidence_source_preparation"
EVIDENCE_COMPARISON_OPERATION_DIRNAME = "evidence_comparison"
EVIDENCE_COMPARISON_EXECUTION_FAILURE_STAGE_EXECUTOR_ID = (
    "evidence_comparison.execution_failed"
)


def slot_candidate_scope_output_dir(
    *,
    flow_root: Path,
    slot_id: str,
) -> Path:
    """Return canonical Candidate Scope checkpoint directory for one participant slot."""
    return (
        flow_root / PARTICIPANTS_DIRNAME / slot_id / CANDIDATE_SCOPE_OPERATION_DIRNAME
    )


def slot_filter_job_output_dir(
    *,
    flow_root: Path,
    slot_id: str,
    filter_job_id: str,
) -> Path:
    """Return canonical Filter output directory for one participant job."""
    return (
        flow_root
        / PARTICIPANTS_DIRNAME
        / slot_id
        / FILTER_OPERATION_DIRNAME
        / filter_job_id
    )


def slot_filter_output_projection_job_output_dir(
    *,
    flow_root: Path,
    slot_id: str,
    filter_job_id: str,
) -> Path:
    """Return canonical Filter-output projection directory for one participant job."""
    return (
        flow_root
        / PARTICIPANTS_DIRNAME
        / slot_id
        / FILTER_OUTPUT_PROJECTION_OPERATION_DIRNAME
        / filter_job_id
    )


def slot_route_semantic_module_output_dir(
    *,
    flow_root: Path,
    slot_id: str,
    semantic_module_id: str,
) -> Path:
    """Return canonical Route semantic-module output directory for one participant slot."""
    return (
        flow_root
        / PARTICIPANTS_DIRNAME
        / slot_id
        / ROUTE_OPERATION_DIRNAME
        / semantic_module_id
    )


def slot_evidence_source_preparation_semantic_module_output_dir(
    *,
    flow_root: Path,
    slot_id: str,
    semantic_module_id: str,
) -> Path:
    """Return canonical ESP output directory for one participant semantic module."""
    return (
        flow_root
        / PARTICIPANTS_DIRNAME
        / slot_id
        / EVIDENCE_SOURCE_PREPARATION_OPERATION_DIRNAME
        / semantic_module_id
    )


def slot_participant_operation_output_dirs(
    *,
    flow_root: Path,
    slot_id: str,
) -> tuple[Path, Path, Path]:
    """Return canonical child-operation sinks for one Flow participant slot."""
    participant_root = flow_root / PARTICIPANTS_DIRNAME / slot_id
    return (
        participant_root / EXTRACT_OPERATION_DIRNAME,
        participant_root / PREPARE_ANALYSIS_OPERATION_DIRNAME,
        participant_root / DOC_META_OPERATION_DIRNAME,
    )


def slot_participant_operation_run_ids(*, slot_id: str) -> tuple[str, str, str]:
    """Return distinct child operation run IDs for one composed Flow participant slot."""
    segment = sanitize_run_segment(slot_id).lower()
    return (
        f"extract_{segment}",
        f"prepare_analysis_{segment}",
        f"doc_meta_{segment}",
    )


def slot_participant_filter_run_id(*, slot_id: str, filter_job_id: str) -> str:
    """Return a distinct Filter child run ID for one participant job."""
    slot_segment = sanitize_run_segment(slot_id).lower()
    job_segment = sanitize_run_segment(filter_job_id).lower()
    return f"filter_{slot_segment}_{job_segment}"


def slot_participant_filter_output_projection_run_id(
    *,
    slot_id: str,
    filter_job_id: str,
) -> str:
    """Return a distinct projection child run ID for one participant job."""
    slot_segment = sanitize_run_segment(slot_id).lower()
    job_segment = sanitize_run_segment(filter_job_id).lower()
    return f"filter_output_projection_{slot_segment}_{job_segment}"


def slot_participant_route_semantic_module_run_id(
    *,
    slot_id: str,
    semantic_module_id: str,
) -> str:
    """Return a distinct Route semantic-module child run ID for one participant slot."""
    slot_segment = sanitize_run_segment(slot_id).lower()
    module_segment = sanitize_run_segment(semantic_module_id).lower()
    return f"route_{slot_segment}_{module_segment}"


def slot_participant_evidence_source_preparation_semantic_module_run_id(
    *,
    slot_id: str,
    semantic_module_id: str,
) -> str:
    """Return a distinct ESP child run ID for one participant semantic module."""
    slot_segment = sanitize_run_segment(slot_id).lower()
    module_segment = sanitize_run_segment(semantic_module_id).lower()
    return f"evidence_source_preparation_{slot_segment}_{module_segment}"


def slot_evidence_comparison_output_dir(
    *,
    flow_root: Path,
    slot_id: str,
) -> Path:
    """Return canonical Evidence Comparison output directory for one participant slot."""
    return (
        flow_root
        / PARTICIPANTS_DIRNAME
        / slot_id
        / EVIDENCE_COMPARISON_OPERATION_DIRNAME
    )


def capability_evidence_comparison_run_id(*, capability_id: str) -> str:
    """Return a distinct Evidence Comparison child run ID for one capability."""
    capability_segment = sanitize_run_segment(capability_id).lower()
    return f"evidence_comparison_{capability_segment}"


def capability_evidence_comparison_output_dir(
    *,
    flow_root: Path,
    capability_id: str,
) -> Path:
    """Return canonical cross-participant Evidence Comparison output directory."""
    capability_segment = sanitize_run_segment(capability_id).lower()
    return flow_root / EVIDENCE_COMPARISON_OPERATION_DIRNAME / capability_segment


@dataclass
class FlowRunFilterJobProvenance:
    filter_job_id: str
    source_language: str
    zone_config_name: str
    zone_config_version: str
    filter_run_id: str | None = None
    output_dir: str | None = None
    zone_match_bundle_path: str | None = None
    coverage_bundle_path: str | None = None
    run_summary_path: str | None = None

    def to_record(self) -> dict[str, Any]:
        if self.filter_run_id is None:
            raise ValueError("filter_run_id is required for filter job provenance")
        if self.output_dir is None:
            raise ValueError("output_dir is required for filter job provenance")
        if self.zone_match_bundle_path is None:
            raise ValueError(
                "zone_match_bundle_path is required for filter job provenance"
            )
        if self.coverage_bundle_path is None:
            raise ValueError(
                "coverage_bundle_path is required for filter job provenance"
            )
        if self.run_summary_path is None:
            raise ValueError("run_summary_path is required for filter job provenance")
        return {
            "filter_job_id": self.filter_job_id,
            "source_language": self.source_language,
            "zone_config_name": self.zone_config_name,
            "zone_config_version": self.zone_config_version,
            "filter_run_id": self.filter_run_id,
            "output_dir": self.output_dir,
            "zone_match_bundle_path": self.zone_match_bundle_path,
            "coverage_bundle_path": self.coverage_bundle_path,
            "run_summary_path": self.run_summary_path,
        }


@dataclass
class FlowRunProjectionJobProvenance:
    filter_job_id: str
    projection_run_id: str | None = None
    output_dir: str | None = None
    projection_bundle_path: str | None = None
    run_summary_path: str | None = None
    projected_source_count: int | None = None
    semantic_outcome_count: int | None = None

    def to_record(self) -> dict[str, Any]:
        if self.projection_run_id is None:
            raise ValueError(
                "projection_run_id is required for projection job provenance"
            )
        if self.output_dir is None:
            raise ValueError("output_dir is required for projection job provenance")
        if self.projection_bundle_path is None:
            raise ValueError(
                "projection_bundle_path is required for projection job provenance"
            )
        if self.run_summary_path is None:
            raise ValueError(
                "run_summary_path is required for projection job provenance"
            )
        if self.projected_source_count is None:
            raise ValueError(
                "projected_source_count is required for projection job provenance"
            )
        if self.semantic_outcome_count is None:
            raise ValueError(
                "semantic_outcome_count is required for projection job provenance"
            )
        return {
            "filter_job_id": self.filter_job_id,
            "projection_run_id": self.projection_run_id,
            "output_dir": self.output_dir,
            "projection_bundle_path": self.projection_bundle_path,
            "run_summary_path": self.run_summary_path,
            "projected_source_count": self.projected_source_count,
            "semantic_outcome_count": self.semantic_outcome_count,
        }


@dataclass
class FlowRunRouteSemanticModuleProvenance:
    """Per semantic-module provenance for one Flow participant slot.

    When ``evidence_source_preparation_invoked`` is true, ESP downstream output
    is referenced only by ``evidence_source_preparation_declared_output_path``.
    Internal ESP artifacts must not appear as additional provenance keys.
    """

    semantic_module_id: str
    selected_projected_source_count: int | None = None
    route_invoked: bool | None = None
    route_run_id: str | None = None
    output_dir: str | None = None
    routing_manifest_path: str | None = None
    run_summary_path: str | None = None
    evidence_source_preparation_invoked: bool | None = None
    evidence_source_preparation_run_id: str | None = None
    evidence_source_preparation_stage_executor_id: str | None = None
    evidence_source_preparation_declared_output_path: str | None = None
    evidence_source_preparation_run_summary_path: str | None = None

    def to_record(self) -> dict[str, Any]:
        if self.selected_projected_source_count is None:
            raise ValueError(
                "selected_projected_source_count is required for "
                "route semantic module provenance"
            )
        if self.route_invoked is None:
            raise ValueError(
                "route_invoked is required for route semantic module provenance"
            )
        record: dict[str, Any] = {
            "semantic_module_id": self.semantic_module_id,
            "selected_projected_source_count": self.selected_projected_source_count,
            "route_invoked": self.route_invoked,
        }
        if self.route_invoked:
            if self.route_run_id is None:
                raise ValueError("route_run_id is required when route_invoked is true")
            if self.output_dir is None:
                raise ValueError("output_dir is required when route_invoked is true")
            if self.routing_manifest_path is None:
                raise ValueError(
                    "routing_manifest_path is required when route_invoked is true"
                )
            if self.run_summary_path is None:
                raise ValueError(
                    "run_summary_path is required when route_invoked is true"
                )
            record.update(
                {
                    "route_run_id": self.route_run_id,
                    "output_dir": self.output_dir,
                    "routing_manifest_path": self.routing_manifest_path,
                    "run_summary_path": self.run_summary_path,
                }
            )
        if self.evidence_source_preparation_invoked is None:
            raise ValueError(
                "evidence_source_preparation_invoked is required for "
                "route semantic module provenance"
            )
        record["evidence_source_preparation_invoked"] = (
            self.evidence_source_preparation_invoked
        )
        if self.evidence_source_preparation_invoked:
            if self.evidence_source_preparation_run_id is None:
                raise ValueError(
                    "evidence_source_preparation_run_id is required when "
                    "evidence_source_preparation_invoked is true"
                )
            if self.evidence_source_preparation_stage_executor_id is None:
                raise ValueError(
                    "evidence_source_preparation_stage_executor_id is required when "
                    "evidence_source_preparation_invoked is true"
                )
            if self.evidence_source_preparation_declared_output_path is None:
                raise ValueError(
                    "evidence_source_preparation_declared_output_path is required when "
                    "evidence_source_preparation_invoked is true"
                )
            if self.evidence_source_preparation_run_summary_path is None:
                raise ValueError(
                    "evidence_source_preparation_run_summary_path is required when "
                    "evidence_source_preparation_invoked is true"
                )
            record.update(
                {
                    "evidence_source_preparation_run_id": (
                        self.evidence_source_preparation_run_id
                    ),
                    "evidence_source_preparation_stage_executor_id": (
                        self.evidence_source_preparation_stage_executor_id
                    ),
                    "evidence_source_preparation_declared_output_path": (
                        self.evidence_source_preparation_declared_output_path
                    ),
                    "evidence_source_preparation_run_summary_path": (
                        self.evidence_source_preparation_run_summary_path
                    ),
                }
            )
        return record


@dataclass
class FlowRunEvidenceComparisonParticipantProvenance:
    role_id: str
    slot_id: str
    semantic_module_id: str
    declared_output_path: str

    def to_record(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "slot_id": self.slot_id,
            "semantic_module_id": self.semantic_module_id,
            "declared_output_path": self.declared_output_path,
        }


@dataclass
class FlowRunEvidenceComparisonProvenance:
    """Capability-level Evidence Comparison provenance for one Flow run."""

    capability_id: str
    handoff_status: str
    stage_executed: bool
    stage_executor_id: str | None = None
    run_id: str | None = None
    output_dir: str | None = None
    run_status: str | None = None
    run_summary_path: str | None = None
    declared_output_path: str | None = None
    participants: tuple[FlowRunEvidenceComparisonParticipantProvenance, ...] = ()

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "capability_id": self.capability_id,
            "handoff_status": self.handoff_status,
            "stage_executed": self.stage_executed,
        }
        if self.stage_executed:
            if self.stage_executor_id is None:
                raise ValueError(
                    "stage_executor_id is required when Evidence Comparison stage_executed "
                    "is true"
                )
            if self.run_id is None:
                raise ValueError(
                    "run_id is required when Evidence Comparison stage_executed is true"
                )
            if self.output_dir is None:
                raise ValueError(
                    "output_dir is required when Evidence Comparison stage_executed is true"
                )
            if self.run_status is None:
                raise ValueError(
                    "run_status is required when Evidence Comparison stage_executed is true"
                )
            if self.run_summary_path is None:
                raise ValueError(
                    "run_summary_path is required when Evidence Comparison stage_executed "
                    "is true"
                )
            record.update(
                {
                    "stage_executor_id": self.stage_executor_id,
                    "run_id": self.run_id,
                    "output_dir": self.output_dir,
                    "run_status": self.run_status,
                    "run_summary_path": self.run_summary_path,
                    "participants": [
                        participant.to_record() for participant in self.participants
                    ],
                }
            )
            if self.declared_output_path is not None:
                record["declared_output_path"] = self.declared_output_path
        else:
            unexpected = {
                "stage_executor_id",
                "run_id",
                "output_dir",
                "run_status",
                "run_summary_path",
                "declared_output_path",
                "participants",
            }.intersection(
                {
                    key
                    for key, value in (
                        ("stage_executor_id", self.stage_executor_id),
                        ("run_id", self.run_id),
                        ("output_dir", self.output_dir),
                        ("run_status", self.run_status),
                        ("run_summary_path", self.run_summary_path),
                        ("declared_output_path", self.declared_output_path),
                        ("participants", self.participants),
                    )
                    if value not in (None, ())
                }
            )
            if unexpected:
                raise ValueError(
                    "Evidence Comparison provenance with stage_executed=false must not "
                    f"include {sorted(unexpected)!r}"
                )
        return record


@dataclass
class FlowRunSlotProvenance:
    slot_id: str
    extract_config_id: str
    prepare_analysis_config_id: PrepareAnalysisConfigId
    filter_job_ids: tuple[str, ...] = ()
    status: str = "not_started"
    intake_run_id: str | None = None
    file_hash: str | None = None
    original_file_name: str | None = None
    doc_id: str | None = None
    extract_run_id: str | None = None
    prepare_analysis_run_id: str | None = None
    analysis_bundle_path: str | None = None
    block_manifest_path: str | None = None
    prepare_analysis_run_summary_path: str | None = None
    doc_meta_run_id: str | None = None
    doc_meta_output_dir: str | None = None
    doc_meta_bundle_path: str | None = None
    doc_meta_run_summary_path: str | None = None
    filter_jobs: list[FlowRunFilterJobProvenance] = field(default_factory=list)
    projection_jobs: list[FlowRunProjectionJobProvenance] = field(default_factory=list)
    route_semantic_modules: list[FlowRunRouteSemanticModuleProvenance] = field(
        default_factory=list
    )
    candidate_scope_decision_path: str | None = None

    def to_record(self) -> dict[str, Any]:
        return build_flow_run_slot_record(
            slot_id=self.slot_id,
            status=self.status,
            extract_config_id=self.extract_config_id,
            prepare_analysis_config_id=str(self.prepare_analysis_config_id),
            file_hash=self.file_hash,
            original_file_name=self.original_file_name,
            doc_id=self.doc_id,
            extract_run_id=self.extract_run_id,
            prepare_analysis_run_id=self.prepare_analysis_run_id,
            analysis_bundle_path=self.analysis_bundle_path,
            block_manifest_path=self.block_manifest_path,
            prepare_analysis_run_summary_path=self.prepare_analysis_run_summary_path,
            doc_meta_run_id=self.doc_meta_run_id,
            doc_meta_output_dir=self.doc_meta_output_dir,
            doc_meta_bundle_path=self.doc_meta_bundle_path,
            doc_meta_run_summary_path=self.doc_meta_run_summary_path,
            filter_job_ids=self.filter_job_ids,
            filter_jobs=[job.to_record() for job in self.filter_jobs]
            if self.filter_jobs
            else None,
            projection_jobs=[job.to_record() for job in self.projection_jobs]
            if self.projection_jobs
            else None,
            route_semantic_modules=[
                module.to_record() for module in self.route_semantic_modules
            ]
            if self.route_semantic_modules
            else None,
            candidate_scope_decision_path=self.candidate_scope_decision_path,
        )


@dataclass
class FlowRunExecution:
    flow_id: str
    flow_run_id: str
    output_dir: Path
    capability_id: str
    source_language: str
    created_at: str
    slot_provenance: list[FlowRunSlotProvenance] = field(default_factory=list)
    evidence_comparison_provenance: FlowRunEvidenceComparisonProvenance | None = None
    candidate_scope_decision_mode: CandidateScopeDecisionMode = (
        CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
    )

    @property
    def flow_run_summary_path(self) -> Path:
        return self.output_dir / FLOW_RUN_SUMMARY_FILENAME


def _allocate_flow_run_dir(*, runs_root: Path, stamp: datetime) -> tuple[Path, str]:
    session_base = build_session_dir_segment(stamp)
    stage_root = (
        runs_root / sanitize_run_segment(DOCUMENT_CONSISTENCY_QC_FLOW_STAGE).lower()
    )
    stage_root.mkdir(parents=True, exist_ok=True)
    candidate = stage_root / session_base
    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate, build_run_id_from_session_dir(
            DOCUMENT_CONSISTENCY_QC_FLOW_STAGE,
            session_base,
        )
    suffix = 2
    while True:
        alt_name = f"{session_base}__{suffix}"
        alt = stage_root / alt_name
        if not alt.exists():
            alt.mkdir(parents=True, exist_ok=True)
            return alt, build_run_id_from_session_dir(
                DOCUMENT_CONSISTENCY_QC_FLOW_STAGE,
                alt_name,
            )
        suffix += 1


def begin_flow_run_execution(
    *,
    project_root: Path,
    capability_id: str,
    source_language: str,
    slot_specs: Sequence[tuple[str, str, PrepareAnalysisConfigId, tuple[str, ...]]],
) -> FlowRunExecution:
    """Allocate flow_run_id and initialize slot provenance in configured order."""
    if not isinstance(source_language, str) or not source_language.strip():
        raise ValueError("source_language must be a non-empty string")
    stamp = utc_run_stamp()
    output_dir, flow_run_id = _allocate_flow_run_dir(
        runs_root=project_root / "runs",
        stamp=stamp,
    )
    return FlowRunExecution(
        flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
        flow_run_id=flow_run_id,
        output_dir=output_dir,
        capability_id=capability_id,
        source_language=source_language.strip(),
        created_at=utc_now_iso(),
        slot_provenance=[
            FlowRunSlotProvenance(
                slot_id=slot_id,
                extract_config_id=extract_config_id,
                prepare_analysis_config_id=prepare_analysis_config_id,
                filter_job_ids=filter_job_ids,
            )
            for slot_id, extract_config_id, prepare_analysis_config_id, filter_job_ids in slot_specs
        ],
    )


def resolve_flow_status(
    slot_provenance: Sequence[FlowRunSlotProvenance],
    *,
    evidence_comparison: FlowRunEvidenceComparisonProvenance | None = None,
) -> str:
    if any(
        slot.status == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE for slot in slot_provenance
    ):
        return FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE

    if all(slot.status == "success" for slot in slot_provenance):
        base_status = "success"
    elif any(slot.status == "success" for slot in slot_provenance):
        base_status = "partial"
    else:
        base_status = "failed"

    if evidence_comparison is None or not evidence_comparison.stage_executed:
        return base_status

    comparison_run_status = evidence_comparison.run_status
    if comparison_run_status == "success":
        return base_status
    if comparison_run_status == "partial_failure":
        if base_status == "failed":
            return "failed"
        return "partial"
    if comparison_run_status == "failed":
        return "failed"
    return base_status


def persist_flow_run_summary(
    execution: FlowRunExecution,
    *,
    status: str | None = None,
    completed_at: str | None = None,
) -> Path:
    """Write flow_run_summary.json and return its path."""
    resolved_status = status or resolve_flow_status(execution.slot_provenance)
    resolved_completed_at = completed_at or utc_now_iso()
    candidate_scope_mode = (
        execution.candidate_scope_decision_mode.value
        if execution.candidate_scope_decision_mode
        is not CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
        else None
    )
    summary = build_flow_run_summary(
        flow_run_id=execution.flow_run_id,
        capability_id=execution.capability_id,
        source_language=execution.source_language,
        status=resolved_status,
        created_at=execution.created_at,
        completed_at=resolved_completed_at,
        slots=[slot.to_record() for slot in execution.slot_provenance],
        evidence_comparison=(
            execution.evidence_comparison_provenance.to_record()
            if execution.evidence_comparison_provenance is not None
            else None
        ),
        candidate_scope_decision_mode=candidate_scope_mode,
    )
    path = execution.flow_run_summary_path
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path, summary)
    reloaded = load_json(path)
    validate_flow_run_summary(reloaded)
    if reloaded != summary:
        raise RuntimeError(
            "persisted flow_run_summary does not match in-memory summary"
        )
    return path


def _persist_evidence_comparison_execution_failure_run_summary(
    *,
    output_dir: Path,
    run_id: str,
    capability_id: str,
    exc: BaseException,
) -> Path:
    """Write a minimal Comparison run_summary for flow exception provenance."""

    output_dir.mkdir(parents=True, exist_ok=True)
    run_summary_path = output_dir / "run_summary.json"
    if run_summary_path.is_file():
        try:
            existing_summary = load_json(run_summary_path)
        except (OSError, TypeError, ValueError):
            existing_summary = None
        if (
            isinstance(existing_summary, Mapping)
            and existing_summary.get("run_status") == "failed"
            and existing_summary.get("failure_reason") == "execution_exception"
            and isinstance(existing_summary.get("outputs"), Mapping)
            and isinstance(existing_summary.get("stats"), Mapping)
            and isinstance(existing_summary.get("consolidation"), list)
        ):
            return run_summary_path
    save_json(
        run_summary_path,
        {
            "run_id": run_id,
            "stage": "evidence_comparison",
            "status": "failed",
            "run_status": "failed",
            "capability_id": capability_id,
            "stage_executor_id": EVIDENCE_COMPARISON_EXECUTION_FAILURE_STAGE_EXECUTOR_ID,
            "failure_reason": "execution_exception",
            "failure_message": str(exc),
        },
    )
    return run_summary_path


def build_evidence_comparison_execution_failure_provenance(
    *,
    capability_id: str,
    handoff_resolution: EvidenceComparisonHandoffResolution,
    run_id: str,
    output_dir: Path,
    exc: BaseException,
) -> FlowRunEvidenceComparisonProvenance:
    """Record Comparison setup/execution failure in flow provenance."""

    handoff = handoff_resolution.handoff
    if handoff is None:
        raise ValueError("READY handoff resolution must include a handoff")
    participants = tuple(
        FlowRunEvidenceComparisonParticipantProvenance(
            role_id=participant.role_id,
            slot_id=participant.slot_id,
            semantic_module_id=participant.semantic_module_id,
            declared_output_path=participant.declared_output_path.as_posix(),
        )
        for participant in handoff.participants
    )
    run_summary_path = _persist_evidence_comparison_execution_failure_run_summary(
        output_dir=output_dir,
        run_id=run_id,
        capability_id=capability_id,
        exc=exc,
    )
    return FlowRunEvidenceComparisonProvenance(
        capability_id=capability_id,
        handoff_status=handoff_resolution.status.value,
        stage_executed=True,
        stage_executor_id=EVIDENCE_COMPARISON_EXECUTION_FAILURE_STAGE_EXECUTOR_ID,
        run_id=run_id,
        output_dir=output_dir.as_posix(),
        run_status="failed",
        run_summary_path=run_summary_path.as_posix(),
        participants=participants,
    )


def persist_flow_run_summary_best_effort(
    execution: FlowRunExecution,
    *,
    status: str | None = None,
) -> None:
    """Persist flow manifest without raising; used when an operation error is active."""
    try:
        persist_flow_run_summary(execution, status=status)
    except Exception:
        pass
