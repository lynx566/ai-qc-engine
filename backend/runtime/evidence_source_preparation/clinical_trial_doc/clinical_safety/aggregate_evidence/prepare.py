# ruff: noqa: TRY004
"""Aggregate Evidence prepare phase dev/debug harness: load inputs and persist outputs.

Phase dev/debug harness — not a canonical runtime stage.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from operations.evidence_source_preparation.stage import (
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceRouteArtifactsInput,
    EvidenceSourcePreparationUpstreamInput,
    ProjectedCoverageByFilterJob,
)
from runtime.io import load_json
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    persist_prepare_execution,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.results import PrepareResult
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import require_evidence_form_id_segment
from runtime.upstream_privacy_context import resolve_upstream_privacy_runtime_context

# Backward-compatible re-export for callers importing result type from this module.
__all__ = [
    "PrepareResult",
    "load_route_artifact_set",
    "resolve_prepare_run_id",
    "run_prepare",
]


def resolve_prepare_run_id(*, stamp: datetime | None = None) -> str:
    resolved_stamp = stamp or utc_run_stamp()
    return format_run_timestamp(resolved_stamp)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def load_route_artifact_set(
    *,
    selected_route_bundle_path: Path,
    routing_manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load selected route bundle and explicit routing manifest refs."""

    selected_path = Path(selected_route_bundle_path).resolve()
    manifest_path = Path(routing_manifest_path).resolve()
    aggregate_bundle = _load_json_object(
        selected_path,
        label="selected_route_bundle_path",
    )
    routing_manifest = _load_json_object(
        manifest_path,
        label="routing_manifest_path",
    )
    return aggregate_bundle, routing_manifest


def run_prepare(
    *,
    run_prepare_phase: Callable[..., Any],
    prepare_semantic: Any,
    routed_aggregate_bundle_path: Path | str,
    routing_manifest_path: Path | str,
    block_manifest_path: Path | str,
    doc_meta_bundle_path: Path | str,
    analysis_bundle_path: Path | str,
    output_dir: Path | str,
    evidence_form_id: str,
    coverage_bundle_path: Path | str | None = None,
    private_audit_bundle_path: Path | str | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    run_id: str | None = None,
    projection_input_refs: tuple[ProjectionInputRefRecord, ...] = (),
    projected_coverage_by_filter_job: ProjectedCoverageByFilterJob | None = None,
    filter_job_coverage_refs: tuple[FilterJobCoverageReference, ...] = (),
    semantic_module_id: str | None = None,
    route_counts: dict[str, int] | None = None,
) -> PrepareResult:
    """
    Build Aggregate Evidence prepare artifacts under *output_dir*.

    Consumes explicit route artifacts only. Does not call LLM.
    """
    resolved_evidence_form_id = require_evidence_form_id_segment(evidence_form_id)
    resolved_routed_aggregate = Path(routed_aggregate_bundle_path).resolve()
    resolved_routing_manifest = Path(routing_manifest_path).resolve()
    resolved_block_manifest = Path(block_manifest_path).resolve()
    resolved_doc_meta_bundle_path = Path(doc_meta_bundle_path).resolve()
    resolved_analysis = Path(analysis_bundle_path).resolve()
    resolved_private_audit = (
        Path(private_audit_bundle_path).resolve()
        if private_audit_bundle_path is not None
        else None
    )

    is_fan_in = projected_coverage_by_filter_job is not None
    if is_fan_in:
        if coverage_bundle_path is not None:
            raise ValueError(
                "coverage_bundle_path must be omitted for projected fan-in prepare; "
                "use projected_coverage_by_filter_job and filter_job_coverage_refs"
            )
        coverage_bundle = None
        resolved_coverage: Path | None = None
    else:
        if coverage_bundle_path is None:
            raise ValueError(
                "coverage_bundle_path is required for single-source prepare"
            )
        resolved_coverage = Path(coverage_bundle_path).resolve()
        coverage_bundle = load_json(resolved_coverage)

    block_manifest = load_json(resolved_block_manifest)
    doc_meta_bundle = load_json(resolved_doc_meta_bundle_path)
    analysis_bundle = load_json(resolved_analysis)

    private_audit_bundle: dict[str, Any] | None = None
    if resolved_private_audit is not None:
        if not resolved_private_audit.is_file():
            raise ValueError(
                f"private_audit_bundle_path must be a file: {resolved_private_audit}"
            )
        private_audit_bundle = load_json(resolved_private_audit)

    aggregate_bundle, routing_manifest = load_route_artifact_set(
        selected_route_bundle_path=resolved_routed_aggregate,
        routing_manifest_path=resolved_routing_manifest,
    )

    upstream_privacy = resolve_upstream_privacy_runtime_context(
        analysis_bundle_path=resolved_analysis,
        analysis_bundle=analysis_bundle,
        private_audit_bundle=private_audit_bundle,
    )

    upstream = EvidenceSourcePreparationUpstreamInput(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
        private_audit_bundle=private_audit_bundle,
        date_shift_offset_days=upstream_privacy.date_shift_offset_days,
        date_shift_offset_source=(
            "upstream_privacy_runtime_context"
            if upstream_privacy.date_shift_offset_days is not None
            else None
        ),
        projected_coverage_by_filter_job=projected_coverage_by_filter_job,
        projection_input_refs=projection_input_refs,
        semantic_module_id=semantic_module_id,
    )
    route_artifacts = AggregateEvidenceRouteArtifactsInput(
        route_counts=dict(route_counts or {}),
        aggregate_bundle=aggregate_bundle,
        routing_manifest=routing_manifest,
        source_routed_unit_bundle_filename=resolved_routed_aggregate.name,
        routing_manifest_filename=resolved_routing_manifest.name,
    )

    prepare_execution = run_prepare_phase(
        upstream=upstream,
        route_artifacts=route_artifacts,
        evidence_form_id=resolved_evidence_form_id,
        prepare_semantic=prepare_semantic,
    )

    resolved_run_id = run_id or resolve_prepare_run_id()
    return persist_prepare_execution(
        execution=prepare_execution,
        output_dir=output_dir,
        run_id=resolved_run_id,
        coverage_bundle_path=resolved_coverage,
        block_manifest_path=resolved_block_manifest,
        doc_meta_bundle_path=resolved_doc_meta_bundle_path,
        analysis_bundle_path=resolved_analysis,
        routed_aggregate_bundle_path=resolved_routed_aggregate,
        routing_manifest_path=resolved_routing_manifest,
        private_audit_bundle_path=resolved_private_audit,
        git_provenance=git_provenance,
        private_audit_bundle=private_audit_bundle,
        filter_job_coverage_refs=filter_job_coverage_refs or None,
        projection_input_refs=projection_input_refs or None,
    )
