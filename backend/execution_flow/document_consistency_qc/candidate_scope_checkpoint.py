"""Canonical Candidate Scope checkpoint materialization and decision persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.candidate_scope_decision import (
    CANDIDATE_SCOPE_DECISION_FILENAME,
    validate_candidate_scope_decision,
)
from artifacts.effective_candidate_scope import RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
from runtime.effective_candidate_scope import build_resolved_candidate_scope
from runtime.io import load_json, save_json
from runtime.run_layout import utc_now_iso

from execution_flow.document_consistency_qc.candidate_scope_selection import (
    anchor_ids_from_zone_bundle,
    canonicalize_anchor_ids_for_job,
    derive_operations,
    sort_anchor_block_ids,
    validate_selection_ownership,
)
from execution_flow.document_consistency_qc.contracts import (
    FilterJobCandidateScopeSelection,
)
from execution_flow.document_consistency_qc.execution_provenance import (
    FlowRunFilterJobProvenance,
    slot_candidate_scope_output_dir,
)


@dataclass(frozen=True, slots=True)
class ResolvedFilterJobZoneMatch:
    filter_job_id: str
    zone_key: str
    anchor_block_ids: tuple[str, ...]
    resolution_kind: str
    resolved_zone_match_bundle_path: Path
    resolved_zone_match_bundle_ref: str
    upstream_filter_bundle_path: Path
    upstream_filter_bundle_ref: str


def _relative_artifact_ref(path: Path, *, project_root: Path) -> str:
    resolved = path.resolve()
    root = project_root.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validate_selection_shape(
    *,
    selections: Sequence[FilterJobCandidateScopeSelection],
    filter_job_ids: tuple[str, ...],
) -> dict[str, set[str]]:
    selection_by_job = {
        item.filter_job_id: set(item.anchor_block_ids) for item in selections
    }
    if set(selection_by_job) != set(filter_job_ids):
        raise ValueError(
            "candidate_scope_selections must include exactly one entry per "
            "installed filter job"
        )
    for filter_job_id in filter_job_ids:
        if not selection_by_job.get(filter_job_id):
            raise ValueError(
                f"candidate_scope_selections for {filter_job_id!r} must include "
                "anchor_block_ids"
            )
    return selection_by_job


def materialize_candidate_scope_zone_matches(
    *,
    filter_job_ids: tuple[str, ...],
    filter_jobs: Sequence[FlowRunFilterJobProvenance],
    selections: Sequence[FilterJobCandidateScopeSelection],
    analysis_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    flow_root: Path,
    slot_id: str,
    doc_id: str,
    project_root: Path,
    manual_default_filter_job_id: str | None = None,
) -> tuple[ResolvedFilterJobZoneMatch, ...]:
    selection_by_job = _validate_selection_shape(
        selections=selections,
        filter_job_ids=filter_job_ids,
    )
    jobs_by_id = {job.filter_job_id: job for job in filter_jobs}
    if set(jobs_by_id) != set(filter_job_ids):
        raise ValueError("filter job provenance does not match installed filter jobs")

    automatic_by_job: dict[str, set[str]] = {}
    for filter_job_id in filter_job_ids:
        automatic_bundle = load_json(
            Path(jobs_by_id[filter_job_id].zone_match_bundle_path)
        )
        automatic_by_job[filter_job_id] = set(
            anchor_ids_from_zone_bundle(automatic_bundle)
        )

    validate_selection_ownership(
        selections_by_job=selection_by_job,
        automatic_by_job=automatic_by_job,
        analysis_bundle=analysis_bundle,
        manual_default_filter_job_id=manual_default_filter_job_id,
    )

    resolved_jobs: list[ResolvedFilterJobZoneMatch] = []
    candidate_scope_root = slot_candidate_scope_output_dir(
        flow_root=flow_root,
        slot_id=slot_id,
    )
    candidate_scope_root.mkdir(parents=True, exist_ok=True)

    for filter_job_id in filter_job_ids:
        job = jobs_by_id[filter_job_id]
        automatic_path = Path(job.zone_match_bundle_path)
        automatic_bundle = load_json(automatic_path)
        automatic_anchors = set(anchor_ids_from_zone_bundle(automatic_bundle))
        canonical_desired = canonicalize_anchor_ids_for_job(
            anchor_ids=selection_by_job[filter_job_id],
            analysis_bundle=analysis_bundle,
        )
        operations = derive_operations(automatic_anchors, canonical_desired)
        zone_key = job.zone_config_name
        resolution_kind = (
            "automatic_unchanged" if not operations else "review_adjusted"
        )

        job_dir = candidate_scope_root / filter_job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        resolved_path = job_dir / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
        resolution_input: dict[str, Any] = {
            "doc_id": doc_id,
            "filter_job_id": filter_job_id,
            "base_filter_run_id": job.filter_run_id,
            "operations": operations,
        }
        result = build_resolved_candidate_scope(
            automatic_zone_match_bundle=automatic_bundle,
            candidate_scope_resolution_input=resolution_input,
            block_manifest=block_manifest,
            analysis_bundle=analysis_bundle,
            effective_run_id=job.filter_run_id,
        )
        save_json(resolved_path, result.effective_zone_match_bundle)
        resolved_ref = _relative_artifact_ref(resolved_path, project_root=project_root)
        upstream_ref = _relative_artifact_ref(automatic_path, project_root=project_root)
        resolved_jobs.append(
            ResolvedFilterJobZoneMatch(
                filter_job_id=filter_job_id,
                zone_key=zone_key,
                anchor_block_ids=tuple(
                    sort_anchor_block_ids(
                        set(
                            anchor_ids_from_zone_bundle(
                                result.effective_zone_match_bundle
                            )
                        ),
                        analysis_bundle=analysis_bundle,
                    )
                ),
                resolution_kind=resolution_kind,
                resolved_zone_match_bundle_path=resolved_path,
                resolved_zone_match_bundle_ref=resolved_ref,
                upstream_filter_bundle_path=automatic_path,
                upstream_filter_bundle_ref=upstream_ref,
            )
        )

    return tuple(resolved_jobs)


def build_candidate_scope_decision_payload(
    *,
    flow_run_id: str,
    slot_id: str,
    filter_job_ids: tuple[str, ...],
    resolved_jobs: Sequence[ResolvedFilterJobZoneMatch],
) -> dict[str, Any]:
    payload = {
        "artifact_type": "document_consistency_qc_candidate_scope_decision",
        "schema_version": "0.2.0",
        "checkpoint_kind": "candidate_scope",
        "flow_run_id": flow_run_id,
        "slot_id": slot_id,
        "decided_at": utc_now_iso(),
        "filter_job_order": list(filter_job_ids),
        "candidate_selections": [
            {
                "filter_job_id": item.filter_job_id,
                "anchor_block_ids": list(item.anchor_block_ids),
                "resolved_bundle_ref": item.resolved_zone_match_bundle_ref,
                "resolution": {
                    "kind": item.resolution_kind,
                    "upstream_bundle_ref": item.upstream_filter_bundle_ref,
                },
            }
            for item in resolved_jobs
        ],
    }
    return validate_candidate_scope_decision(payload)


def persist_candidate_scope_decision(
    *,
    flow_root: Path,
    slot_id: str,
    payload: Mapping[str, Any],
) -> Path:
    validated = validate_candidate_scope_decision(dict(payload))
    out_dir = slot_candidate_scope_output_dir(flow_root=flow_root, slot_id=slot_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / CANDIDATE_SCOPE_DECISION_FILENAME
    save_json(path, validated)
    return path


def zone_match_bundle_paths_from_resolved(
    resolved_jobs: Sequence[ResolvedFilterJobZoneMatch],
) -> dict[str, Path]:
    return {
        item.filter_job_id: item.resolved_zone_match_bundle_path
        for item in resolved_jobs
    }


def _zone_match_bundle_path_for_job(
    job: FlowRunFilterJobProvenance | Mapping[str, Any],
) -> Path:
    if isinstance(job, Mapping):
        return Path(str(job["zone_match_bundle_path"]))
    return Path(job.zone_match_bundle_path)


def automatic_candidate_scope_selections(
    *,
    filter_job_ids: tuple[str, ...],
    filter_jobs: Sequence[FlowRunFilterJobProvenance | Mapping[str, Any]],
) -> tuple[FilterJobCandidateScopeSelection, ...]:
    jobs_by_id = {
        (job["filter_job_id"] if isinstance(job, Mapping) else job.filter_job_id): job
        for job in filter_jobs
    }
    selections: list[FilterJobCandidateScopeSelection] = []
    for filter_job_id in filter_job_ids:
        automatic_bundle = load_json(
            _zone_match_bundle_path_for_job(jobs_by_id[filter_job_id])
        )
        selections.append(
            FilterJobCandidateScopeSelection(
                filter_job_id=filter_job_id,
                anchor_block_ids=tuple(anchor_ids_from_zone_bundle(automatic_bundle)),
            )
        )
    return tuple(selections)


__all__ = [
    "ResolvedFilterJobZoneMatch",
    "automatic_candidate_scope_selections",
    "build_candidate_scope_decision_payload",
    "materialize_candidate_scope_zone_matches",
    "persist_candidate_scope_decision",
    "zone_match_bundle_paths_from_resolved",
]
