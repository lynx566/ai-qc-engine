"""Map canonical paused-flow slot provenance to Candidate Scope view context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bridge.candidate_scope.errors import CandidateScopeValidationError
from execution_flow.document_consistency_qc.execution_provenance import (
    FlowRunExecution,
    FlowRunFilterJobProvenance,
    FlowRunSlotProvenance,
)


@dataclass(frozen=True, slots=True)
class FilterJobViewPaths:
    filter_job_id: str
    zone_key: str
    zone_match_bundle_path: Path
    coverage_bundle_path: Path


@dataclass(frozen=True, slots=True)
class PausedSlotViewContext:
    flow_run_id: str
    capability_id: str
    slot_id: str
    doc_id: str
    analysis_bundle_path: Path
    block_manifest_path: Path
    filter_jobs: tuple[FilterJobViewPaths, ...]


def _filter_job_view_paths(job: FlowRunFilterJobProvenance) -> FilterJobViewPaths:
    return FilterJobViewPaths(
        filter_job_id=job.filter_job_id,
        zone_key=job.zone_config_name,
        zone_match_bundle_path=Path(job.zone_match_bundle_path),
        coverage_bundle_path=Path(job.coverage_bundle_path),
    )


def build_paused_slot_view_context(
    *,
    execution: FlowRunExecution,
    slot_provenance: FlowRunSlotProvenance,
) -> PausedSlotViewContext:
    doc_id = str(slot_provenance.doc_id or "").strip()
    if not doc_id:
        raise CandidateScopeValidationError("paused slot provenance is missing doc_id")

    filter_job_ids = tuple(slot_provenance.filter_job_ids)
    if not filter_job_ids:
        raise CandidateScopeValidationError(
            "paused slot provenance is missing filter_job_ids"
        )

    jobs_by_id = {job.filter_job_id: job for job in slot_provenance.filter_jobs}
    if set(jobs_by_id) != set(filter_job_ids):
        raise CandidateScopeValidationError(
            "paused slot filter job provenance does not match filter_job_ids"
        )

    analysis_bundle_path = Path(slot_provenance.analysis_bundle_path or "")
    block_manifest_path = Path(slot_provenance.block_manifest_path or "")
    if not analysis_bundle_path.is_file():
        raise CandidateScopeValidationError(
            "paused slot analysis_bundle_path is missing"
        )
    if not block_manifest_path.is_file():
        raise CandidateScopeValidationError(
            "paused slot block_manifest_path is missing"
        )

    capability_id = str(execution.capability_id or "").strip()
    if not capability_id:
        raise CandidateScopeValidationError(
            "paused flow provenance is missing capability_id"
        )

    return PausedSlotViewContext(
        flow_run_id=execution.flow_run_id,
        capability_id=capability_id,
        slot_id=slot_provenance.slot_id,
        doc_id=doc_id,
        analysis_bundle_path=analysis_bundle_path,
        block_manifest_path=block_manifest_path,
        filter_jobs=tuple(
            _filter_job_view_paths(jobs_by_id[job_id]) for job_id in filter_job_ids
        ),
    )


__all__ = [
    "FilterJobViewPaths",
    "PausedSlotViewContext",
    "build_paused_slot_view_context",
]
