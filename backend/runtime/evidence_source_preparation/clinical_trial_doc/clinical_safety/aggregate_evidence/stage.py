"""Clinical-trial aggregate Evidence Source Preparation production stage runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm.invocation import llm_invocations_from_exception, serialize_llm_invocations
from llm.providers.base import LLMProvider
from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationExecutor,
)
from operations.evidence_source_preparation.coverage_resolution import (
    is_projected_multi_source_fan_in,
    resolve_projected_coverage_bundles_by_filter_job_id,
    resolve_unique_coverage_bundle_path,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
    EvidenceSourcePreparationStageExecutor,
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationStageResult,
)
from operations.evidence_source_preparation.stage_validation import (
    validate_evidence_source_preparation_stage_input,
)
from steps import evidence_source_preparation as esp_step
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
    CLINICAL_TRIAL_DOC_PLUGIN_ID,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceExecution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceExecutionInput,
    AggregateEvidenceRouteArtifactsInput,
    EvidenceSourcePreparationUpstreamInput,
    ProjectedCoverageByFilterJob,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    persist_unified_aggregate_evidence_execution,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
    load_route_artifact_set,
)
from runtime.io import load_json, save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import utc_now_iso
from runtime.run_provenance import finalize_run_summary
from runtime.run_summaries import BACKEND_ROOT
from runtime.upstream_privacy_context import resolve_upstream_privacy_runtime_context

CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID = (
    f"{CLINICAL_TRIAL_DOC_PLUGIN_ID}.{AGGREGATE_EVIDENCE_FORM_ID}"
)


@dataclass(frozen=True, slots=True)
class ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
    EvidenceSourcePreparationExecutionDependencies,
):
    """Concrete execution dependencies for clinical-trial aggregate ESP stage runs."""

    llm_mode: str = "mock"
    llm_profile: str | None = None
    provider: LLMProvider | None = None
    llm_execution_config: dict[str, Any] | None = None
    allow_api_parse_fallback: bool = False
    assessment_profile_name: str | None = None


def resolve_evidence_source_preparation_stage_run_id(*, stamp=None) -> str:
    resolved_stamp = stamp or utc_run_stamp()
    return format_run_timestamp(resolved_stamp)


def _validate_clinical_trial_aggregate_stage_handoff(
    stage_input: EvidenceSourcePreparationStageInput,
) -> None:
    """Fail fast when this concrete runtime receives non-aggregate handoff facts."""

    if stage_input.evidence_form_id != AGGREGATE_EVIDENCE_FORM_ID:
        raise ValueError(
            "clinical-trial aggregate stage requires "
            f"evidence_form_id={AGGREGATE_EVIDENCE_FORM_ID!r}; "
            f"got {stage_input.evidence_form_id!r}"
        )
    selected_route_output = stage_input.selected_route_output
    if selected_route_output.route_output_kind != "aggregate":
        raise ValueError(
            "clinical-trial aggregate stage requires "
            "selected_route_output.route_output_kind='aggregate'; "
            f"got {selected_route_output.route_output_kind!r}"
        )


def execute_clinical_trial_aggregate_evidence_source_preparation_stage(
    *,
    stage_input: EvidenceSourcePreparationStageInput,
    evidence_source_preparation_executor: EvidenceSourcePreparationExecutor,
) -> EvidenceSourcePreparationStageResult:
    """Load upstream artifacts, run canonical ESP step, and persist unified outputs."""

    if not isinstance(stage_input, EvidenceSourcePreparationStageInput):
        raise TypeError(
            "stage_input must be an EvidenceSourcePreparationStageInput; "
            f"got {type(stage_input)!r}"
        )
    execution_dependencies = stage_input.execution_dependencies
    if not isinstance(
        execution_dependencies,
        ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
    ):
        raise TypeError(
            "clinical-trial aggregate stage requires "
            "ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies; "
            f"got {type(execution_dependencies)!r}"
        )

    validate_evidence_source_preparation_stage_input(stage_input)
    _validate_clinical_trial_aggregate_stage_handoff(stage_input)

    route_stage = stage_input.route_stage
    selected_route_output = stage_input.selected_route_output
    routed_selected_path = selected_route_output.routed_bundle_path.resolve()
    resolved_routing_manifest_path = route_stage.routing_manifest_path.resolve()
    aggregate_bundle, routing_manifest = load_route_artifact_set(
        selected_route_bundle_path=routed_selected_path,
        routing_manifest_path=resolved_routing_manifest_path,
    )

    coverage_resolution = resolve_projected_coverage_bundles_by_filter_job_id(
        projection_input_refs=stage_input.projection_input_refs,
        filter_job_coverage_refs=stage_input.filter_job_coverage_refs,
    )
    distinct_coverage_paths = tuple(
        dict.fromkeys(
            coverage_resolution.paths_by_filter_job_id[job_id]
            for job_id in coverage_resolution.ordered_filter_job_ids
        ).keys()
    )
    projected_fan_in = is_projected_multi_source_fan_in(
        aggregate_bundle=aggregate_bundle,
        projection_input_refs=stage_input.projection_input_refs,
        distinct_coverage_count=len(distinct_coverage_paths),
    )

    coverage_bundles_by_filter_job_id = {
        filter_job_id: load_json(path)
        for filter_job_id, path in coverage_resolution.paths_by_filter_job_id.items()
    }
    if projected_fan_in:
        coverage_bundle = None
        primary_coverage_path = None
    else:
        primary_coverage_path = resolve_unique_coverage_bundle_path(
            projection_input_refs=stage_input.projection_input_refs,
            filter_job_coverage_refs=stage_input.filter_job_coverage_refs,
        )
        coverage_bundle = load_json(primary_coverage_path)

    upstream_refs = stage_input.upstream
    resolved_block_manifest = Path(upstream_refs.block_manifest_path).resolve()
    resolved_doc_meta_bundle_path = Path(upstream_refs.doc_meta_bundle_path).resolve()
    resolved_analysis = Path(upstream_refs.analysis_bundle_path).resolve()
    resolved_private_audit = (
        Path(upstream_refs.private_audit_bundle_path).resolve()
        if upstream_refs.private_audit_bundle_path is not None
        else None
    )

    block_manifest = load_json(resolved_block_manifest)
    doc_meta_bundle = load_json(resolved_doc_meta_bundle_path)
    analysis_bundle = load_json(resolved_analysis)

    private_audit_bundle: dict[str, Any] | None = None
    if resolved_private_audit is not None:
        if not resolved_private_audit.is_file():
            raise ValueError(
                "private_audit_bundle_path must be a file: "
                f"{resolved_private_audit}"
            )
        private_audit_bundle = load_json(resolved_private_audit)

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
        projected_coverage_by_filter_job=(
            ProjectedCoverageByFilterJob(
                bundles_by_filter_job_id=coverage_bundles_by_filter_job_id,
            )
            if projected_fan_in
            else None
        ),
        projection_input_refs=stage_input.projection_input_refs,
        semantic_module_id=route_stage.semantic_module_id,
    )
    route_artifacts = AggregateEvidenceRouteArtifactsInput(
        route_counts=dict(route_stage.route_counts),
        aggregate_bundle=aggregate_bundle,
        routing_manifest=routing_manifest,
        source_routed_unit_bundle_filename=selected_route_output.routed_bundle_path.name,
        routing_manifest_filename=route_stage.routing_manifest_path.name,
    )
    invocation = AggregateEvidenceExecutionInput(
        upstream=upstream,
        route_artifacts=route_artifacts,
        evidence_form_id=stage_input.evidence_form_id,
        assessment_profile_name=execution_dependencies.assessment_profile_name,
        llm_mode=execution_dependencies.llm_mode,
        llm_profile=execution_dependencies.llm_profile,
        provider=execution_dependencies.provider,
        llm_execution_config=execution_dependencies.llm_execution_config,
        allow_api_parse_fallback=execution_dependencies.allow_api_parse_fallback,
    )

    stage_context = stage_input.context
    resolved_run_id = (
        stage_context.run_id or resolve_evidence_source_preparation_stage_run_id()
    )
    try:
        execution_result = esp_step.run_evidence_source_preparation(
            invocation=invocation,
            executor=evidence_source_preparation_executor,
        )
    except Exception as error:
        invocations = llm_invocations_from_exception(error)
        if invocations:
            out_dir = Path(stage_context.output_dir).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            summary = finalize_run_summary(
                stage="evidence_source_preparation",
                run_id=resolved_run_id,
                pipeline=[
                    "extract",
                    "prepare_analysis",
                    "doc_meta",
                    "filter",
                    "route",
                    "evidence_source_preparation",
                ],
                doc_id=route_stage.doc_id,
                inputs={
                    "routed_aggregate_bundle": routed_selected_path.as_posix(),
                    "routing_manifest": resolved_routing_manifest_path.as_posix(),
                },
                outputs={"run_summary": "run_summary.json"},
                git_root=BACKEND_ROOT,
                git_provenance=(
                    dict(stage_context.git_provenance)
                    if stage_context.git_provenance is not None
                    else None
                ),
                created_at=utc_now_iso(),
                status="failed",
                run_status="failed",
                error={
                    "type": type(error).__name__,
                    "message": str(error),
                },
                llm_invocations=serialize_llm_invocations(invocations),
            )
            save_json(out_dir / "run_summary.json", summary)
        raise
    if not isinstance(execution_result, AggregateEvidenceExecution):
        raise TypeError(
            "installed aggregate executor must return AggregateEvidenceExecution; "
            f"got {type(execution_result)!r}"
        )

    persist_result = persist_unified_aggregate_evidence_execution(
        execution=execution_result,
        output_dir=stage_context.output_dir,
        run_id=resolved_run_id,
        coverage_bundle_path=primary_coverage_path,
        block_manifest_path=resolved_block_manifest,
        doc_meta_bundle_path=resolved_doc_meta_bundle_path,
        analysis_bundle_path=resolved_analysis,
        routed_aggregate_bundle_path=routed_selected_path,
        routing_manifest_path=route_stage.routing_manifest_path,
        private_audit_bundle_path=resolved_private_audit,
        git_provenance=(
            dict(stage_context.git_provenance)
            if stage_context.git_provenance is not None
            else None
        ),
        llm_mode=execution_dependencies.llm_mode,
        private_audit_bundle=private_audit_bundle,
        filter_job_coverage_refs=(
            stage_input.filter_job_coverage_refs if projected_fan_in else None
        ),
        projection_input_refs=(
            stage_input.projection_input_refs if projected_fan_in else None
        ),
    )

    return EvidenceSourcePreparationStageResult(
        output_dir=persist_result.output_dir,
        run_id=persist_result.run_id,
        doc_id=persist_result.doc_id,
        semantic_module_id=route_stage.semantic_module_id,
        stage_executor_id=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID,
        declared_output_path=persist_result.aggregate_evidence_source_bundle_path,
        run_summary_path=persist_result.run_summary_path,
    )


def build_clinical_trial_aggregate_evidence_source_preparation_stage_executor(
    *,
    evidence_source_preparation_executor: EvidenceSourcePreparationExecutor,
) -> EvidenceSourcePreparationStageExecutor:
    """Bind one installed in-memory executor into the production stage runtime."""

    def _stage_executor(
        *,
        stage_input: EvidenceSourcePreparationStageInput,
    ) -> EvidenceSourcePreparationStageResult:
        return execute_clinical_trial_aggregate_evidence_source_preparation_stage(
            stage_input=stage_input,
            evidence_source_preparation_executor=evidence_source_preparation_executor,
        )

    return _stage_executor


__all__ = [
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID",
    "ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies",
    "build_clinical_trial_aggregate_evidence_source_preparation_stage_executor",
    "execute_clinical_trial_aggregate_evidence_source_preparation_stage",
    "resolve_evidence_source_preparation_stage_run_id",
]
