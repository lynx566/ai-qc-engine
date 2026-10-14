"""Canonical document-consistency QC flow through Extract, Prepare Analysis, Doc Meta, Filter, Projection, Route, and Evidence Source Preparation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.metadata.schemas import MetadataProfile
from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBindings,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolution,
    EvidenceComparisonHandoffResolutionStatus,
    ProducedEvidenceSourcePreparationOutputReference,
    resolve_evidence_comparison_handoff,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageContext,
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBindings,
)
from operations.evidence_source_preparation.route_handoff import (
    EvidenceSourcePreparationRouteHandoff,
    resolve_evidence_source_preparation_route_handoff,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
    EvidenceSourcePreparationStageContext,
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationStageResult,
    EvidenceSourcePreparationUpstreamReferences,
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
    RouteStageReference,
    SelectedRouteOutputReference,
)
from operations.filter.variant_registry import resolve_filter_job_variant
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionFacade,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.registry import (
    resolve_filter_output_projection_job,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from operations.projected_source_route.contracts import ProjectedSourceRouteExecutor
from runtime.doc_meta_stage import run_doc_meta_stage
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.evidence_comparison_stage import run_evidence_comparison_stage
from runtime.evidence_source_preparation_stage import (
    run_evidence_source_preparation_stage,
)
from runtime.extract import ExtractDocumentInput, ExtractOperationReport
from runtime.filter_output_projection_stage import (
    FilterOutputProjectionStageResult,
    run_filter_output_projection_stage,
)
from runtime.filter_stage import (
    FilterStageInvocation,
    FilterStageResult,
    run_filter_stage,
)
from runtime.io import load_json
from runtime.prepare_analysis import (
    PrepareAnalysisExecutionContext,
    PrepareAnalysisOperationReport,
    run_prepare_analysis_operation,
)
from runtime.projected_source_route_stage import (
    ProjectedSourceRouteStageResult,
    run_projected_source_route_from_projection_bundles,
)
from runtime.run_ids import utc_run_stamp

from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
    build_candidate_scope_decision_payload,
    materialize_candidate_scope_zone_matches,
    persist_candidate_scope_decision,
    zone_match_bundle_paths_from_resolved,
)
from execution_flow.document_consistency_qc.contracts import (
    CandidateScopeDecisionMode,
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantRunInput,
    DocumentConsistencyQcParticipantSlot,
    FilterJobCandidateScopeSelection,
)
from execution_flow.document_consistency_qc.errors import (
    reraise_post_allocation_flow_execution_failure,
)
from execution_flow.document_consistency_qc.execution_provenance import (
    SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    FlowRunEvidenceComparisonParticipantProvenance,
    FlowRunEvidenceComparisonProvenance,
    FlowRunExecution,
    FlowRunFilterJobProvenance,
    FlowRunProjectionJobProvenance,
    FlowRunRouteSemanticModuleProvenance,
    FlowRunSlotProvenance,
    begin_flow_run_execution,
    build_evidence_comparison_execution_failure_provenance,
    capability_evidence_comparison_output_dir,
    capability_evidence_comparison_run_id,
    persist_flow_run_summary,
    persist_flow_run_summary_best_effort,
    resolve_flow_status,
    slot_evidence_comparison_output_dir,
    slot_evidence_source_preparation_semantic_module_output_dir,
    slot_filter_job_output_dir,
    slot_filter_output_projection_job_output_dir,
    slot_participant_evidence_source_preparation_semantic_module_run_id,
    slot_participant_filter_output_projection_run_id,
    slot_participant_operation_output_dirs,
    slot_participant_operation_run_ids,
    slot_participant_route_semantic_module_run_id,
    slot_route_semantic_module_output_dir,
)
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    build_doc_meta_report_from_provenance,
    build_resumed_upstream_stubs,
    load_flow_run_execution,
    resolve_resumed_admitted_source,
    validate_candidate_scope_resume_decisions,
)
from execution_flow.document_processing_sequence import (
    run_document_processing_launch_extract,
)

Source = DocumentIntakeSourceBinding
DocMetaStageReport = dict[str, Any]
DocMetaSummaryBuilder = Callable[[dict[str, Any]], dict[str, Any]]
EvidenceComparisonExecutionDependenciesMaterializer = Callable[
    [str],
    EvidenceComparisonExecutionDependencies,
]


@dataclass(frozen=True)
class FilterJobFlowResult:
    filter_job_id: str
    source_language: str
    zone_config_name: str
    zone_config_version: str
    stage_result: FilterStageResult


@dataclass(frozen=True)
class ProjectionJobFlowResult:
    filter_job_id: str
    stage_result: FilterOutputProjectionStageResult


@dataclass(frozen=True)
class RouteSemanticModuleFlowResult:
    semantic_module_id: str
    selected_projected_source_count: int
    route_invoked: bool
    stage_result: ProjectedSourceRouteStageResult | None = None
    evidence_source_preparation_invoked: bool = False
    evidence_source_preparation_stage_result: (
        EvidenceSourcePreparationStageResult | None
    ) = None


@dataclass(frozen=True)
class DocumentConsistencyQcSlotResult:
    slot_id: str
    admitted_source: DocumentIntakeSourceBinding
    extract_report: ExtractOperationReport
    prepare_analysis_report: PrepareAnalysisOperationReport
    doc_meta_report: DocMetaStageReport
    filter_results: tuple[FilterJobFlowResult, ...] = ()
    projection_results: tuple[ProjectionJobFlowResult, ...] = ()
    route_semantic_module_results: tuple[RouteSemanticModuleFlowResult, ...] = ()


@dataclass(frozen=True)
class DocumentConsistencyQcFlowResult:
    slots: tuple[DocumentConsistencyQcSlotResult, ...]
    evidence_comparison_handoff_resolution: EvidenceComparisonHandoffResolution = field(
        default_factory=lambda: EvidenceComparisonHandoffResolution(
            status=EvidenceComparisonHandoffResolutionStatus.UNBOUND,
            consumer_binding=None,
            handoff=None,
        )
    )
    evidence_comparison_stage_result: EvidenceComparisonStageResult | None = None
    paused_at_candidate_scope: bool = False


def _collect_produced_evidence_source_preparation_outputs(
    slot_results: Sequence[DocumentConsistencyQcSlotResult],
) -> tuple[ProducedEvidenceSourcePreparationOutputReference, ...]:
    produced: list[ProducedEvidenceSourcePreparationOutputReference] = []
    for slot_result in slot_results:
        for module_result in slot_result.route_semantic_module_results:
            stage_result = module_result.evidence_source_preparation_stage_result
            if stage_result is None:
                continue
            produced.append(
                ProducedEvidenceSourcePreparationOutputReference(
                    slot_id=slot_result.slot_id,
                    semantic_module_id=stage_result.semantic_module_id,
                    declared_output_path=stage_result.declared_output_path,
                )
            )
    return tuple(produced)


def _build_evidence_comparison_provenance(
    *,
    capability_id: str,
    handoff_resolution: EvidenceComparisonHandoffResolution,
    stage_result: EvidenceComparisonStageResult | None,
) -> FlowRunEvidenceComparisonProvenance:
    handoff_status = handoff_resolution.status.value
    if handoff_resolution.status is not EvidenceComparisonHandoffResolutionStatus.READY:
        return FlowRunEvidenceComparisonProvenance(
            capability_id=capability_id,
            handoff_status=handoff_status,
            stage_executed=False,
        )
    if stage_result is None:
        return FlowRunEvidenceComparisonProvenance(
            capability_id=capability_id,
            handoff_status=handoff_status,
            stage_executed=False,
        )

    handoff = handoff_resolution.handoff
    participants: tuple[FlowRunEvidenceComparisonParticipantProvenance, ...] = ()
    if handoff is not None:
        participants = tuple(
            FlowRunEvidenceComparisonParticipantProvenance(
                role_id=participant.role_id,
                slot_id=participant.slot_id,
                semantic_module_id=participant.semantic_module_id,
                declared_output_path=participant.declared_output_path.as_posix(),
            )
            for participant in handoff.participants
        )

    declared_output_path = (
        stage_result.declared_output_path.as_posix()
        if stage_result.declared_output_path is not None
        else None
    )
    return FlowRunEvidenceComparisonProvenance(
        capability_id=capability_id,
        handoff_status=handoff_status,
        stage_executed=True,
        stage_executor_id=stage_result.stage_executor_id,
        run_id=stage_result.run_id,
        output_dir=stage_result.output_dir.as_posix(),
        run_status=stage_result.run_status,
        run_summary_path=stage_result.run_summary_path.as_posix(),
        declared_output_path=declared_output_path,
        participants=participants,
    )


def _resolve_evidence_comparison_execution_dependencies_for_stage(
    *,
    capability_id: str,
    evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependencies | None
    ),
    materialize_evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependenciesMaterializer | None
    ),
) -> EvidenceComparisonExecutionDependencies:
    if evidence_comparison_execution_dependencies is not None:
        if not isinstance(
            evidence_comparison_execution_dependencies,
            EvidenceComparisonExecutionDependencies,
        ):
            raise TypeError(
                "evidence_comparison_execution_dependencies must be an "
                "EvidenceComparisonExecutionDependencies"
            )
        return evidence_comparison_execution_dependencies
    if materialize_evidence_comparison_execution_dependencies is None:
        raise ValueError(
            "Evidence Comparison handoff is READY but no execution dependencies "
            "were supplied; provide evidence_comparison_execution_dependencies or "
            "materialize_evidence_comparison_execution_dependencies"
        )
    dependencies = materialize_evidence_comparison_execution_dependencies(capability_id)
    if not isinstance(dependencies, EvidenceComparisonExecutionDependencies):
        raise TypeError(
            "materialize_evidence_comparison_execution_dependencies must return an "
            "EvidenceComparisonExecutionDependencies"
        )
    return dependencies


@dataclass(frozen=True, slots=True)
class _FlowEvidenceComparisonFinalization:
    comparison_handoff_resolution: EvidenceComparisonHandoffResolution
    comparison_stage_result: EvidenceComparisonStageResult | None
    summary_path: Path


def _finalize_flow_with_evidence_comparison(
    *,
    execution: FlowRunExecution,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    slot_results: Sequence[DocumentConsistencyQcSlotResult],
    evidence_comparison_consumer_bindings: EvidenceComparisonConsumerBindings,
    evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependencies | None
    ),
    materialize_evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependenciesMaterializer | None
    ),
    git_provenance: Mapping[str, str | bool | None] | None,
) -> _FlowEvidenceComparisonFinalization:
    """Finalize one flow after all slot orchestration is complete."""
    comparison_failure_context: dict[str, Any] | None = None
    try:
        comparison_binding = (
            evidence_comparison_consumer_bindings.resolve_consumer_binding(
                capability_config.capability_id
            )
        )
        comparison_handoff_resolution = resolve_evidence_comparison_handoff(
            consumer_binding=comparison_binding,
            produced_outputs=_collect_produced_evidence_source_preparation_outputs(
                slot_results
            ),
        )
        comparison_stage_result: EvidenceComparisonStageResult | None = None
        if (
            comparison_handoff_resolution.status
            is EvidenceComparisonHandoffResolutionStatus.READY
        ):
            comparison_handoff = comparison_handoff_resolution.handoff
            if comparison_handoff is None:
                raise RuntimeError("ready Comparison handoff must include a handoff")
            comparison_run_id = capability_evidence_comparison_run_id(
                capability_id=capability_config.capability_id,
            )
            if len(comparison_handoff.participants) == 1:
                comparison_output_dir = slot_evidence_comparison_output_dir(
                    flow_root=execution.output_dir,
                    slot_id=comparison_handoff.participants[0].slot_id,
                )
            else:
                comparison_output_dir = capability_evidence_comparison_output_dir(
                    flow_root=execution.output_dir,
                    capability_id=capability_config.capability_id,
                )
            comparison_failure_context = {
                "capability_id": capability_config.capability_id,
                "handoff_resolution": comparison_handoff_resolution,
                "run_id": comparison_run_id,
                "output_dir": comparison_output_dir,
            }
            comparison_execution_dependencies = (
                _resolve_evidence_comparison_execution_dependencies_for_stage(
                    capability_id=capability_config.capability_id,
                    evidence_comparison_execution_dependencies=(
                        evidence_comparison_execution_dependencies
                    ),
                    materialize_evidence_comparison_execution_dependencies=(
                        materialize_evidence_comparison_execution_dependencies
                    ),
                )
            )
            comparison_stage_result = run_evidence_comparison_stage(
                stage_input=EvidenceComparisonStageInput(
                    participants=comparison_handoff.participants,
                    context=EvidenceComparisonStageContext(
                        output_dir=comparison_output_dir,
                        run_id=comparison_run_id,
                        git_provenance=git_provenance,
                    ),
                    execution_dependencies=comparison_execution_dependencies,
                ),
                stage_executor=comparison_handoff.consumer_binding.stage_executor,
            )

        execution.evidence_comparison_provenance = (
            _build_evidence_comparison_provenance(
                capability_id=capability_config.capability_id,
                handoff_resolution=comparison_handoff_resolution,
                stage_result=comparison_stage_result,
            )
        )
        flow_status = resolve_flow_status(
            execution.slot_provenance,
            evidence_comparison=execution.evidence_comparison_provenance,
        )
        summary_path = persist_flow_run_summary(execution, status=flow_status)
    except Exception as exc:
        flow_status = resolve_flow_status(execution.slot_provenance)
        if comparison_failure_context is not None:
            execution.evidence_comparison_provenance = (
                build_evidence_comparison_execution_failure_provenance(
                    capability_id=comparison_failure_context["capability_id"],
                    handoff_resolution=comparison_failure_context["handoff_resolution"],
                    run_id=comparison_failure_context["run_id"],
                    output_dir=comparison_failure_context["output_dir"],
                    exc=exc,
                )
            )
            flow_status = resolve_flow_status(
                execution.slot_provenance,
                evidence_comparison=execution.evidence_comparison_provenance,
            )
        persist_flow_run_summary_best_effort(execution, status=flow_status)
        raise

    return _FlowEvidenceComparisonFinalization(
        comparison_handoff_resolution=comparison_handoff_resolution,
        comparison_stage_result=comparison_stage_result,
        summary_path=summary_path,
    )


@dataclass(frozen=True)
class DocumentConsistencyQcFlowReport:
    result: DocumentConsistencyQcFlowResult
    messages: tuple[str, ...]
    flow_run_id: str
    flow_run_summary_path: Path


def _normalize_source_language(source_language: str) -> str:
    if not isinstance(source_language, str) or not source_language.strip():
        raise ValueError("source_language must be a non-empty string")
    return source_language.strip()


def _validate_request_binding(
    capability_config: DocumentConsistencyQcCapabilityConfig,
    uploads: Mapping[str, Source],
    participant_inputs: Mapping[str, DocumentConsistencyQcParticipantRunInput],
    *,
    source_language: str,
) -> None:
    _normalize_source_language(source_language)

    slots = capability_config.slots
    if not slots:
        raise ValueError("capability_config.slots must contain at least one entry")

    slot_ids = [slot.slot_id for slot in slots]
    if len(slot_ids) != len(set(slot_ids)):
        duplicates = sorted(
            {slot_id for slot_id in slot_ids if slot_ids.count(slot_id) > 1}
        )
        raise ValueError(
            "capability_config.slots contains duplicate slot_id values: "
            + ", ".join(duplicates)
        )

    expected = set(slot_ids)
    provided = set(uploads.keys())
    missing = sorted(expected - provided)
    if missing:
        raise ValueError("missing upload for configured slot(s): " + ", ".join(missing))
    unexpected = sorted(provided - expected)
    if unexpected:
        raise ValueError("unexpected upload slot id(s): " + ", ".join(unexpected))

    provided_participants = set(participant_inputs)
    missing_participants = sorted(expected - provided_participants)
    if missing_participants:
        raise ValueError(
            "missing participant run input for configured slot(s): "
            + ", ".join(missing_participants)
        )
    unexpected_participants = sorted(provided_participants - expected)
    if unexpected_participants:
        raise ValueError(
            "unexpected participant run input slot id(s): "
            + ", ".join(unexpected_participants)
        )
    for slot_id, participant_input in participant_inputs.items():
        if not isinstance(participant_input, DocumentConsistencyQcParticipantRunInput):
            raise TypeError(
                f"participant input for slot {slot_id!r} must be a "
                "DocumentConsistencyQcParticipantRunInput"
            )

    for slot_id in slot_ids:
        source = uploads[slot_id]
        if not isinstance(source, DocumentIntakeSourceBinding):
            raise TypeError(
                f"upload for slot {slot_id!r} must be a DocumentIntakeSourceBinding"
            )
        if not source.source_path.is_file():
            raise ValueError(
                f"upload for slot {slot_id!r} must reference an existing source file"
            )


def _capability_slot_binding_key(
    *,
    capability_id: str,
    slot_id: str,
) -> tuple[str, str]:
    return (capability_id, slot_id)


def _lookup_binding_value(
    bindings: Mapping[tuple[str, str], Any],
    *,
    binding_key: tuple[str, str],
    binding_name: str,
) -> Any:
    try:
        return bindings[binding_key]
    except KeyError as exc:
        capability_id, slot_id = binding_key
        raise ValueError(
            f"missing {binding_name} binding for capability slot "
            f"({capability_id!r}, {slot_id!r})"
        ) from exc


def _validate_operation_bindings(
    capability_config: DocumentConsistencyQcCapabilityConfig,
    *,
    extract_bindings: Mapping[tuple[str, str], str],
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
) -> None:
    for slot in capability_config.slots:
        binding_key = _capability_slot_binding_key(
            capability_id=capability_config.capability_id,
            slot_id=slot.slot_id,
        )
        _lookup_binding_value(
            extract_bindings,
            binding_key=binding_key,
            binding_name="Extract",
        )
        prepare_binding = _lookup_binding_value(
            prepare_analysis_bindings,
            binding_key=binding_key,
            binding_name="Prepare Analysis",
        )
        if not isinstance(prepare_binding, PrepareAnalysisConfigId):
            raise TypeError(
                "prepare_analysis_bindings values must be PrepareAnalysisConfigId"
            )
        filter_binding = _lookup_binding_value(
            filter_job_bindings,
            binding_key=binding_key,
            binding_name="Filter job",
        )
        if not isinstance(filter_binding, tuple):
            raise TypeError("filter_job_bindings values must be tuples")


def _resolve_slot_filter_jobs(
    *,
    filter_job_ids: tuple[str, ...],
    source_language: str,
    filter_job_variants: Mapping[tuple[str, str], Any],
) -> tuple[tuple[str, Any], ...]:
    resolved: list[tuple[str, Any]] = []
    for filter_job_id in filter_job_ids:
        config = resolve_filter_job_variant(
            filter_job_id=filter_job_id,
            language=source_language,
            filter_job_variants=filter_job_variants,
        )
        resolved.append((filter_job_id, config))
    return tuple(resolved)


def _build_evidence_source_preparation_stage_input(
    *,
    route_stage_result: ProjectedSourceRouteStageResult,
    route_handoff: EvidenceSourcePreparationRouteHandoff,
    projection_input_refs: Sequence[Mapping[str, str]],
    filter_results: Sequence[FilterJobFlowResult],
    block_manifest_path: Path,
    doc_meta_bundle_path: Path,
    analysis_bundle_path: Path,
    output_dir: Path,
    run_id: str,
    git_provenance: Mapping[str, str | bool | None] | None,
    execution_dependencies: EvidenceSourcePreparationExecutionDependencies,
) -> EvidenceSourcePreparationStageInput:
    route_stage = RouteStageReference(
        output_dir=route_stage_result.output_dir,
        run_id=route_stage_result.run_id,
        doc_id=route_stage_result.doc_id,
        semantic_module_id=route_stage_result.semantic_module_id,
        route_counts=dict(route_stage_result.route_counts),
        routed_bundle_paths=dict(route_stage_result.routed_bundle_paths),
        routing_manifest_path=route_stage_result.routing_manifest_path,
    )
    selected_route_output = route_handoff.selected_route_output
    return EvidenceSourcePreparationStageInput(
        route_stage=route_stage,
        projection_input_refs=tuple(
            ProjectionInputRefRecord(
                filter_job_id=str(ref["filter_job_id"]),
                zone_key=str(ref["zone_key"]),
                filter_output_projection_bundle_id=str(
                    ref["filter_output_projection_bundle_id"]
                ),
            )
            for ref in projection_input_refs
        ),
        filter_job_coverage_refs=tuple(
            FilterJobCoverageReference(
                filter_job_id=filter_job.filter_job_id,
                coverage_bundle_path=filter_job.stage_result.coverage_bundle_path,
            )
            for filter_job in filter_results
        ),
        upstream=EvidenceSourcePreparationUpstreamReferences(
            block_manifest_path=block_manifest_path,
            doc_meta_bundle_path=doc_meta_bundle_path,
            analysis_bundle_path=analysis_bundle_path,
        ),
        context=EvidenceSourcePreparationStageContext(
            output_dir=output_dir,
            run_id=run_id,
            git_provenance=git_provenance,
        ),
        execution_dependencies=execution_dependencies,
        evidence_form_id=route_handoff.consumer_binding.evidence_form_id,
        selected_route_output=SelectedRouteOutputReference(
            route_output_kind=selected_route_output.route_output_kind,
            unit_count=selected_route_output.unit_count,
            routed_bundle_path=selected_route_output.routed_bundle_path,
        ),
    )


def _filter_job_flow_results_from_provenance(
    slot_provenance: FlowRunSlotProvenance,
) -> tuple[FilterJobFlowResult, ...]:
    if slot_provenance.doc_id is None:
        raise ValueError("paused slot provenance is missing doc_id")
    results: list[FilterJobFlowResult] = []
    for job in slot_provenance.filter_jobs:
        stage_result = FilterStageResult(
            output_dir=Path(job.output_dir),
            run_id=job.filter_run_id,
            doc_id=slot_provenance.doc_id,
            zone_key=job.zone_config_name,
            run_context=job.zone_config_name,
            zone_bundle_path=Path(job.zone_match_bundle_path),
            coverage_bundle_path=Path(job.coverage_bundle_path),
            zone_bundle_debug_path=None,
            run_summary_path=Path(job.run_summary_path),
            bundle={},
            bundle_path=Path(job.zone_match_bundle_path),
        )
        results.append(
            FilterJobFlowResult(
                filter_job_id=job.filter_job_id,
                source_language=job.source_language,
                zone_config_name=job.zone_config_name,
                zone_config_version=job.zone_config_version,
                stage_result=stage_result,
            )
        )
    return tuple(results)


def _continue_slot_after_candidate_scope(
    *,
    slot_id: str,
    filter_results: Sequence[FilterJobFlowResult],
    zone_match_bundle_paths: Mapping[str, Path],
    analysis_bundle_path: Path,
    block_manifest_path: Path,
    doc_meta_bundle_path: Path,
    flow_root: Path,
    slot_provenance: FlowRunSlotProvenance,
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    filter_output_projection_facade_builder: Callable[
        ...,
        FilterOutputProjectionFacade,
    ],
    projected_source_route_executor: ProjectedSourceRouteExecutor,
    route_semantic_module_sequence: Sequence[str],
    enabled_route_semantic_module_ids: frozenset[str],
    evidence_source_preparation_consumer_bindings: (
        EvidenceSourcePreparationConsumerBindings
    ),
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies
    ),
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
    git_provenance: Mapping[str, str | bool | None] | None = None,
) -> tuple[
    tuple[ProjectionJobFlowResult, ...], tuple[RouteSemanticModuleFlowResult, ...]
]:
    projection_results: list[ProjectionJobFlowResult] = []
    persisted_projection_bundle_paths: list[Path] = []
    runtime_dependencies = (
        projection_runtime_dependencies or FilterOutputProjectionRuntimeDependencies()
    )
    for filter_job in filter_results:
        zone_match_path = zone_match_bundle_paths[filter_job.filter_job_id]
        resolved_projection_job = resolve_filter_output_projection_job(
            filter_job_id=filter_job.filter_job_id,
            filter_output_projection_jobs=filter_output_projection_jobs,
        )
        projection_output_dir = slot_filter_output_projection_job_output_dir(
            flow_root=flow_root,
            slot_id=slot_id,
            filter_job_id=filter_job.filter_job_id,
        )
        facade = filter_output_projection_facade_builder(
            job=resolved_projection_job,
            runtime_dependencies=runtime_dependencies,
        )
        projection_stage_result = run_filter_output_projection_stage(
            filter_job_id=filter_job.filter_job_id,
            resolved_job=resolved_projection_job,
            zone_match_bundle_path=zone_match_path,
            analysis_bundle_path=analysis_bundle_path,
            facade=facade,
            output_dir=projection_output_dir,
            git_provenance=dict(git_provenance) if git_provenance is not None else None,
            run_id=slot_participant_filter_output_projection_run_id(
                slot_id=slot_id,
                filter_job_id=filter_job.filter_job_id,
            ),
        )
        slot_provenance.projection_jobs.append(
            FlowRunProjectionJobProvenance(
                filter_job_id=filter_job.filter_job_id,
                projection_run_id=projection_stage_result.run_id,
                output_dir=projection_stage_result.output_dir.as_posix(),
                projection_bundle_path=(
                    projection_stage_result.projection_bundle_path.as_posix()
                ),
                run_summary_path=projection_stage_result.run_summary_path.as_posix(),
                projected_source_count=len(
                    projection_stage_result.step_result.projected_sources
                ),
                semantic_outcome_count=len(
                    projection_stage_result.step_result.semantic_outcomes
                ),
            )
        )
        projection_results.append(
            ProjectionJobFlowResult(
                filter_job_id=filter_job.filter_job_id,
                stage_result=projection_stage_result,
            )
        )
        persisted_projection_bundle_paths.append(
            projection_stage_result.projection_bundle_path
        )

    route_semantic_module_results: list[RouteSemanticModuleFlowResult] = []
    if persisted_projection_bundle_paths:
        for semantic_module_id in route_semantic_module_sequence:
            route_outcome = run_projected_source_route_from_projection_bundles(
                projection_bundle_paths=tuple(persisted_projection_bundle_paths),
                semantic_module_id=semantic_module_id,
                enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
                block_manifest_path=block_manifest_path,
                doc_meta_bundle_path=doc_meta_bundle_path,
                analysis_bundle_path=analysis_bundle_path,
                output_dir=slot_route_semantic_module_output_dir(
                    flow_root=flow_root,
                    slot_id=slot_id,
                    semantic_module_id=semantic_module_id,
                ),
                run_id=slot_participant_route_semantic_module_run_id(
                    slot_id=slot_id,
                    semantic_module_id=semantic_module_id,
                ),
                route_executor=projected_source_route_executor,
                git_provenance=(
                    dict(git_provenance) if git_provenance is not None else None
                ),
            )
            selected_count = route_outcome.selected_projected_source_count
            route_stage_result: ProjectedSourceRouteStageResult | None = (
                route_outcome.route_result
            )
            esp_stage_result: EvidenceSourcePreparationStageResult | None = None
            esp_invoked = False
            if route_stage_result is not None:
                route_semantic_module_id = route_stage_result.semantic_module_id
                projection_input_refs = route_outcome.projection_input_refs
                route_provenance = FlowRunRouteSemanticModuleProvenance(
                    semantic_module_id=route_semantic_module_id,
                    selected_projected_source_count=selected_count,
                    route_invoked=True,
                    route_run_id=route_stage_result.run_id,
                    output_dir=route_stage_result.output_dir.as_posix(),
                    routing_manifest_path=(
                        route_stage_result.routing_manifest_path.as_posix()
                    ),
                    run_summary_path=route_stage_result.run_summary_path.as_posix(),
                    evidence_source_preparation_invoked=False,
                )
                consumer_binding = evidence_source_preparation_consumer_bindings.resolve_consumer_binding(
                    route_semantic_module_id
                )
                route_handoff = resolve_evidence_source_preparation_route_handoff(
                    route_counts=route_stage_result.route_counts,
                    routed_bundle_paths=route_stage_result.routed_bundle_paths,
                    consumer_binding=consumer_binding,
                )
                if route_handoff is not None:
                    esp_stage_input = _build_evidence_source_preparation_stage_input(
                        route_stage_result=route_stage_result,
                        route_handoff=route_handoff,
                        projection_input_refs=projection_input_refs,
                        filter_results=tuple(filter_results),
                        block_manifest_path=block_manifest_path,
                        doc_meta_bundle_path=doc_meta_bundle_path,
                        analysis_bundle_path=analysis_bundle_path,
                        output_dir=slot_evidence_source_preparation_semantic_module_output_dir(
                            flow_root=flow_root,
                            slot_id=slot_id,
                            semantic_module_id=route_semantic_module_id,
                        ),
                        run_id=slot_participant_evidence_source_preparation_semantic_module_run_id(
                            slot_id=slot_id,
                            semantic_module_id=route_semantic_module_id,
                        ),
                        git_provenance=(
                            dict(git_provenance) if git_provenance is not None else None
                        ),
                        execution_dependencies=(
                            evidence_source_preparation_execution_dependencies
                        ),
                    )
                    esp_stage_result = run_evidence_source_preparation_stage(
                        stage_input=esp_stage_input,
                        stage_executor=route_handoff.consumer_binding.stage_executor,
                    )
                    esp_invoked = True
                    route_provenance.evidence_source_preparation_invoked = True
                    route_provenance.evidence_source_preparation_run_id = (
                        esp_stage_result.run_id
                    )
                    route_provenance.evidence_source_preparation_stage_executor_id = (
                        esp_stage_result.stage_executor_id
                    )
                    route_provenance.evidence_source_preparation_declared_output_path = esp_stage_result.declared_output_path.as_posix()
                    route_provenance.evidence_source_preparation_run_summary_path = (
                        esp_stage_result.run_summary_path.as_posix()
                    )
                slot_provenance.route_semantic_modules.append(route_provenance)
            else:
                slot_provenance.route_semantic_modules.append(
                    FlowRunRouteSemanticModuleProvenance(
                        semantic_module_id=semantic_module_id,
                        selected_projected_source_count=0,
                        route_invoked=False,
                        evidence_source_preparation_invoked=False,
                    )
                )
            route_semantic_module_results.append(
                RouteSemanticModuleFlowResult(
                    semantic_module_id=(
                        route_stage_result.semantic_module_id
                        if route_stage_result is not None
                        else semantic_module_id
                    ),
                    selected_projected_source_count=selected_count,
                    route_invoked=route_stage_result is not None,
                    stage_result=route_stage_result,
                    evidence_source_preparation_invoked=esp_invoked,
                    evidence_source_preparation_stage_result=esp_stage_result,
                )
            )
    elif route_semantic_module_sequence:
        for semantic_module_id in route_semantic_module_sequence:
            slot_provenance.route_semantic_modules.append(
                FlowRunRouteSemanticModuleProvenance(
                    semantic_module_id=semantic_module_id,
                    selected_projected_source_count=0,
                    route_invoked=False,
                    evidence_source_preparation_invoked=False,
                )
            )
            route_semantic_module_results.append(
                RouteSemanticModuleFlowResult(
                    semantic_module_id=semantic_module_id,
                    selected_projected_source_count=0,
                    route_invoked=False,
                    stage_result=None,
                    evidence_source_preparation_invoked=False,
                    evidence_source_preparation_stage_result=None,
                )
            )

    return tuple(projection_results), tuple(route_semantic_module_results)


def _run_canonical_slot(
    *,
    execution: FlowRunExecution,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    slot: DocumentConsistencyQcParticipantSlot,
    slot_provenance: FlowRunSlotProvenance,
    source_language: str,
    source: Source,
    participant_input: DocumentConsistencyQcParticipantRunInput,
    project_root: Path,
    export_slices: bool,
    git_provenance: Mapping[str, str | bool | None] | None,
    extract_bindings: Mapping[tuple[str, str], str],
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
    doc_meta_profile: MetadataProfile,
    doc_meta_summary_builder: DocMetaSummaryBuilder,
    filter_job_variants: Mapping[tuple[str, str], Any],
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    filter_output_projection_facade_builder: Callable[
        ...,
        FilterOutputProjectionFacade,
    ],
    projected_source_route_executor: ProjectedSourceRouteExecutor,
    route_semantic_module_sequence: Sequence[str],
    enabled_route_semantic_module_ids: frozenset[str],
    evidence_source_preparation_consumer_bindings: (
        EvidenceSourcePreparationConsumerBindings
    ),
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies
    ),
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies | None,
) -> DocumentConsistencyQcSlotResult:
    """Run one canonical slot through Filter and post-checkpoint stages."""
    (
        extract_output_dir,
        prepare_analysis_output_dir,
        doc_meta_output_dir,
    ) = slot_participant_operation_output_dirs(
        flow_root=execution.output_dir,
        slot_id=slot.slot_id,
    )
    binding_key = _capability_slot_binding_key(
        capability_id=capability_config.capability_id,
        slot_id=slot.slot_id,
    )
    return _run_slot(
        slot=slot,
        extract_config_id=_lookup_binding_value(
            extract_bindings,
            binding_key=binding_key,
            binding_name="Extract",
        ),
        prepare_analysis_config_id=_lookup_binding_value(
            prepare_analysis_bindings,
            binding_key=binding_key,
            binding_name="Prepare Analysis",
        ),
        filter_job_ids=_lookup_binding_value(
            filter_job_bindings,
            binding_key=binding_key,
            binding_name="Filter job",
        ),
        source=source,
        project_root=project_root,
        flow_root=execution.output_dir,
        source_language=source_language,
        extract_output_dir=extract_output_dir,
        prepare_analysis_output_dir=prepare_analysis_output_dir,
        doc_meta_output_dir=doc_meta_output_dir,
        export_slices=export_slices,
        git_provenance=git_provenance,
        slot_provenance=slot_provenance,
        participant_input=participant_input,
        prepare_analysis_config_registry=prepare_analysis_config_registry,
        doc_meta_profile=doc_meta_profile,
        doc_meta_summary_builder=doc_meta_summary_builder,
        filter_job_variants=filter_job_variants,
        filter_output_projection_jobs=filter_output_projection_jobs,
        filter_output_projection_facade_builder=filter_output_projection_facade_builder,
        projected_source_route_executor=projected_source_route_executor,
        route_semantic_module_sequence=route_semantic_module_sequence,
        enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
        evidence_source_preparation_consumer_bindings=(
            evidence_source_preparation_consumer_bindings
        ),
        evidence_source_preparation_execution_dependencies=(
            evidence_source_preparation_execution_dependencies
        ),
        projection_runtime_dependencies=projection_runtime_dependencies,
    )


def _run_canonical_slot_through_candidate_scope_checkpoint(
    *,
    execution: FlowRunExecution,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    slot: DocumentConsistencyQcParticipantSlot,
    slot_provenance: FlowRunSlotProvenance,
    source_language: str,
    source: Source,
    participant_input: DocumentConsistencyQcParticipantRunInput,
    project_root: Path,
    export_slices: bool,
    git_provenance: Mapping[str, str | bool | None] | None,
    extract_bindings: Mapping[tuple[str, str], str],
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
    doc_meta_profile: MetadataProfile,
    doc_meta_summary_builder: DocMetaSummaryBuilder,
    filter_job_variants: Mapping[tuple[str, str], Any],
) -> DocumentConsistencyQcSlotResult:
    """Run one slot through Filter and mark it paused at Candidate Scope."""
    (
        extract_output_dir,
        prepare_analysis_output_dir,
        doc_meta_output_dir,
    ) = slot_participant_operation_output_dirs(
        flow_root=execution.output_dir,
        slot_id=slot.slot_id,
    )
    binding_key = _capability_slot_binding_key(
        capability_id=capability_config.capability_id,
        slot_id=slot.slot_id,
    )
    slot_result = _run_slot_through_candidate_scope_checkpoint(
        slot=slot,
        extract_config_id=_lookup_binding_value(
            extract_bindings,
            binding_key=binding_key,
            binding_name="Extract",
        ),
        prepare_analysis_config_id=_lookup_binding_value(
            prepare_analysis_bindings,
            binding_key=binding_key,
            binding_name="Prepare Analysis",
        ),
        filter_job_ids=_lookup_binding_value(
            filter_job_bindings,
            binding_key=binding_key,
            binding_name="Filter job",
        ),
        source=source,
        project_root=project_root,
        flow_root=execution.output_dir,
        source_language=source_language,
        extract_output_dir=extract_output_dir,
        prepare_analysis_output_dir=prepare_analysis_output_dir,
        doc_meta_output_dir=doc_meta_output_dir,
        export_slices=export_slices,
        git_provenance=git_provenance,
        slot_provenance=slot_provenance,
        participant_input=participant_input,
        prepare_analysis_config_registry=prepare_analysis_config_registry,
        doc_meta_profile=doc_meta_profile,
        doc_meta_summary_builder=doc_meta_summary_builder,
        filter_job_variants=filter_job_variants,
    )
    slot_provenance.status = SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    return slot_result


def _run_slot_through_candidate_scope_checkpoint(
    *,
    slot: DocumentConsistencyQcParticipantSlot,
    extract_config_id: str,
    prepare_analysis_config_id: PrepareAnalysisConfigId,
    filter_job_ids: tuple[str, ...],
    source: Source,
    project_root: Path,
    flow_root: Path,
    source_language: str,
    extract_output_dir: Path | str | None,
    prepare_analysis_output_dir: Path | str | None,
    doc_meta_output_dir: Path | str | None,
    export_slices: bool,
    git_provenance: Mapping[str, str | bool | None] | None,
    slot_provenance: FlowRunSlotProvenance,
    participant_input: DocumentConsistencyQcParticipantRunInput,
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
    doc_meta_profile: MetadataProfile,
    doc_meta_summary_builder: DocMetaSummaryBuilder,
    filter_job_variants: Mapping[tuple[str, str], Any],
) -> DocumentConsistencyQcSlotResult:
    """Run Launch through Filter for one admitted source without post-checkpoint stages."""
    extract_run_id, prepare_analysis_run_id, doc_meta_run_id = (
        slot_participant_operation_run_ids(
            slot_id=slot.slot_id,
        )
    )
    try:

        def _record_launch_provenance(
            admitted_source: DocumentIntakeSourceBinding,
            launched_document: ExtractDocumentInput,
        ) -> None:
            slot_provenance.file_hash = admitted_source.file_hash
            slot_provenance.original_file_name = admitted_source.original_file_name
            slot_provenance.doc_id = launched_document.identity.doc_id

        sequence = run_document_processing_launch_extract(
            project_root=project_root,
            admitted_source=source,
            extract_config_id=extract_config_id,
            extract_output_dir=extract_output_dir,
            extract_run_id=extract_run_id,
            export_slices=export_slices,
            git_provenance=git_provenance,
            on_launched=_record_launch_provenance,
        )
        admitted_source = sequence.admitted_source
        extract_report = sequence.extract_report
        slot_provenance.extract_run_id = extract_report.result.run_id

        bundle = asdict(extract_report.result.document.bundle)
        slot_provenance.prepare_analysis_run_id = prepare_analysis_run_id
        prepare_analysis_report = run_prepare_analysis_operation(
            execution=PrepareAnalysisExecutionContext(
                project_root=project_root,
                output_dir=(
                    Path(prepare_analysis_output_dir)
                    if prepare_analysis_output_dir is not None
                    else None
                ),
                run_id=prepare_analysis_run_id,
                git_provenance=git_provenance,
            ),
            prepare_analysis_config_id=prepare_analysis_config_id,
            config_registry=prepare_analysis_config_registry,
            request_options=participant_input.prepare_analysis_request_options,
            bundle=bundle,
        )
        prepare_document = prepare_analysis_report.documents[0]
        if prepare_document.paths is None:
            raise RuntimeError(
                "persisted Prepare Analysis child result is missing artifact paths"
            )
        slot_provenance.prepare_analysis_run_id = prepare_document.run_id
        slot_provenance.analysis_bundle_path = (
            prepare_document.paths.analysis_bundle.as_posix()
        )
        slot_provenance.block_manifest_path = (
            prepare_document.paths.block_manifest.as_posix()
        )
        slot_provenance.prepare_analysis_run_summary_path = (
            prepare_document.paths.run_summary.as_posix()
        )

        slot_provenance.doc_meta_run_id = doc_meta_run_id
        doc_meta_report = run_doc_meta_stage(
            analysis_bundle_path=prepare_document.paths.analysis_bundle,
            analysis_bundle=prepare_document.artifacts.analysis_bundle,
            output_dir=Path(doc_meta_output_dir),
            profile=doc_meta_profile,
            build_summary=doc_meta_summary_builder,
            git_provenance=dict(git_provenance) if git_provenance is not None else None,
            run_id=doc_meta_run_id,
        )
        slot_provenance.doc_meta_output_dir = doc_meta_report["output_dir"]
        slot_provenance.doc_meta_bundle_path = doc_meta_report["doc_meta_bundle_path"]
        slot_provenance.doc_meta_run_summary_path = doc_meta_report["run_summary_path"]

        resolved_filter_jobs = _resolve_slot_filter_jobs(
            filter_job_ids=filter_job_ids,
            source_language=source_language,
            filter_job_variants=filter_job_variants,
        )

        filter_stamp = utc_run_stamp()
        filter_invocation = FilterStageInvocation(
            stamp=filter_stamp,
            session_dir=flow_root,
            runs_root=project_root / "runs",
            git_root=project_root,
            multi_bundle=False,
            multi_profile=False,
        )
        filter_results: list[FilterJobFlowResult] = []
        for filter_job_id, profile in resolved_filter_jobs:
            filter_output_dir = slot_filter_job_output_dir(
                flow_root=flow_root,
                slot_id=slot.slot_id,
                filter_job_id=filter_job_id,
            )
            stage_result = run_filter_stage(
                bundle_path=prepare_document.paths.analysis_bundle,
                profile=profile,
                zone_key=profile.zone_config_name,
                invocation=FilterStageInvocation(
                    stamp=filter_invocation.stamp,
                    session_dir=filter_invocation.session_dir,
                    runs_root=filter_invocation.runs_root,
                    git_root=filter_invocation.git_root,
                    multi_bundle=False,
                    multi_profile=False,
                    custom_output_dir=filter_output_dir,
                ),
                git_provenance=dict(git_provenance)
                if git_provenance is not None
                else None,
                paths_base=project_root,
            )
            slot_provenance.filter_jobs.append(
                FlowRunFilterJobProvenance(
                    filter_job_id=filter_job_id,
                    source_language=source_language,
                    zone_config_name=profile.zone_config_name,
                    zone_config_version=profile.zone_config_version,
                    filter_run_id=stage_result.run_id,
                    output_dir=stage_result.output_dir.as_posix(),
                    zone_match_bundle_path=stage_result.zone_bundle_path.as_posix(),
                    coverage_bundle_path=stage_result.coverage_bundle_path.as_posix(),
                    run_summary_path=stage_result.run_summary_path.as_posix(),
                )
            )
            filter_results.append(
                FilterJobFlowResult(
                    filter_job_id=filter_job_id,
                    source_language=source_language,
                    zone_config_name=profile.zone_config_name,
                    zone_config_version=profile.zone_config_version,
                    stage_result=stage_result,
                )
            )

        return DocumentConsistencyQcSlotResult(
            slot_id=slot.slot_id,
            admitted_source=admitted_source,
            extract_report=extract_report,
            prepare_analysis_report=prepare_analysis_report,
            doc_meta_report=doc_meta_report,
            filter_results=tuple(filter_results),
        )
    except Exception:
        slot_provenance.status = (
            "partial" if slot_provenance.file_hash is not None else "failed"
        )
        raise


def _run_slot(
    *,
    slot: DocumentConsistencyQcParticipantSlot,
    extract_config_id: str,
    prepare_analysis_config_id: PrepareAnalysisConfigId,
    filter_job_ids: tuple[str, ...],
    source: Source,
    project_root: Path,
    flow_root: Path,
    source_language: str,
    extract_output_dir: Path | str | None,
    prepare_analysis_output_dir: Path | str | None,
    doc_meta_output_dir: Path | str | None,
    export_slices: bool,
    git_provenance: Mapping[str, str | bool | None] | None,
    slot_provenance: FlowRunSlotProvenance,
    participant_input: DocumentConsistencyQcParticipantRunInput,
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
    doc_meta_profile: MetadataProfile,
    doc_meta_summary_builder: DocMetaSummaryBuilder,
    filter_job_variants: Mapping[tuple[str, str], Any],
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    filter_output_projection_facade_builder: Callable[
        ...,
        FilterOutputProjectionFacade,
    ],
    projected_source_route_executor: ProjectedSourceRouteExecutor,
    route_semantic_module_sequence: Sequence[str],
    enabled_route_semantic_module_ids: frozenset[str],
    evidence_source_preparation_consumer_bindings: (
        EvidenceSourcePreparationConsumerBindings
    ),
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies
    ),
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
) -> DocumentConsistencyQcSlotResult:
    """Run one slot through Filter, then continue post-checkpoint stages."""
    pre_checkpoint_result = _run_slot_through_candidate_scope_checkpoint(
        slot=slot,
        extract_config_id=extract_config_id,
        prepare_analysis_config_id=prepare_analysis_config_id,
        filter_job_ids=filter_job_ids,
        source=source,
        project_root=project_root,
        flow_root=flow_root,
        source_language=source_language,
        extract_output_dir=extract_output_dir,
        prepare_analysis_output_dir=prepare_analysis_output_dir,
        doc_meta_output_dir=doc_meta_output_dir,
        export_slices=export_slices,
        git_provenance=git_provenance,
        slot_provenance=slot_provenance,
        participant_input=participant_input,
        prepare_analysis_config_registry=prepare_analysis_config_registry,
        doc_meta_profile=doc_meta_profile,
        doc_meta_summary_builder=doc_meta_summary_builder,
        filter_job_variants=filter_job_variants,
    )
    analysis_bundle_path = Path(slot_provenance.analysis_bundle_path or "")
    block_manifest_path = Path(slot_provenance.block_manifest_path or "")
    zone_match_bundle_paths = {
        filter_job.filter_job_id: filter_job.stage_result.zone_bundle_path
        for filter_job in pre_checkpoint_result.filter_results
    }
    projection_results, route_semantic_module_results = (
        _continue_slot_after_candidate_scope(
            slot_id=slot.slot_id,
            filter_results=pre_checkpoint_result.filter_results,
            zone_match_bundle_paths=zone_match_bundle_paths,
            analysis_bundle_path=analysis_bundle_path,
            block_manifest_path=block_manifest_path,
            doc_meta_bundle_path=Path(
                pre_checkpoint_result.doc_meta_report["doc_meta_bundle_path"]
            ),
            flow_root=flow_root,
            slot_provenance=slot_provenance,
            filter_output_projection_jobs=filter_output_projection_jobs,
            filter_output_projection_facade_builder=(
                filter_output_projection_facade_builder
            ),
            projected_source_route_executor=projected_source_route_executor,
            route_semantic_module_sequence=route_semantic_module_sequence,
            enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
            evidence_source_preparation_consumer_bindings=(
                evidence_source_preparation_consumer_bindings
            ),
            evidence_source_preparation_execution_dependencies=(
                evidence_source_preparation_execution_dependencies
            ),
            projection_runtime_dependencies=projection_runtime_dependencies,
            git_provenance=git_provenance,
        )
    )
    slot_provenance.status = "success"
    return DocumentConsistencyQcSlotResult(
        slot_id=slot.slot_id,
        admitted_source=pre_checkpoint_result.admitted_source,
        extract_report=pre_checkpoint_result.extract_report,
        prepare_analysis_report=pre_checkpoint_result.prepare_analysis_report,
        doc_meta_report=pre_checkpoint_result.doc_meta_report,
        filter_results=pre_checkpoint_result.filter_results,
        projection_results=tuple(projection_results),
        route_semantic_module_results=tuple(route_semantic_module_results),
    )


@dataclass(frozen=True, slots=True)
class PreparedDocumentConsistencyQcFlowExecution:
    """Process-local handoff from FlowRun allocation to stage execution."""

    execution: FlowRunExecution
    project_root: Path
    capability_config: DocumentConsistencyQcCapabilityConfig
    uploads: Mapping[str, Source]
    participant_inputs: Mapping[str, DocumentConsistencyQcParticipantRunInput]
    source_language: str
    extract_bindings: Mapping[tuple[str, str], str]
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId]
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]]
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry
    doc_meta_profile: MetadataProfile
    doc_meta_summary_builder: DocMetaSummaryBuilder
    filter_job_variants: Mapping[tuple[str, str], Any]
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob]
    filter_output_projection_facade_builder: Callable[..., FilterOutputProjectionFacade]
    projected_source_route_executor: ProjectedSourceRouteExecutor
    route_semantic_module_sequence: Sequence[str]
    enabled_route_semantic_module_ids: frozenset[str]
    evidence_source_preparation_consumer_bindings: EvidenceSourcePreparationConsumerBindings
    evidence_source_preparation_execution_dependencies: EvidenceSourcePreparationExecutionDependencies
    evidence_comparison_consumer_bindings: EvidenceComparisonConsumerBindings
    evidence_comparison_execution_dependencies: EvidenceComparisonExecutionDependencies | None
    materialize_evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependenciesMaterializer | None
    )
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies | None
    candidate_scope_decision_mode: CandidateScopeDecisionMode
    export_slices: bool
    git_provenance: Mapping[str, str | bool | None] | None

    @property
    def flow_id(self) -> str:
        return self.execution.flow_id

    @property
    def flow_run_id(self) -> str:
        return self.execution.flow_run_id

    @property
    def output_dir(self) -> Path:
        return self.execution.output_dir


def prepare_and_allocate_document_consistency_qc_flow(
    *,
    project_root: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    uploads: Mapping[str, Source],
    participant_inputs: Mapping[str, DocumentConsistencyQcParticipantRunInput],
    source_language: str,
    extract_bindings: Mapping[tuple[str, str], str],
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
    doc_meta_profile: MetadataProfile,
    doc_meta_summary_builder: DocMetaSummaryBuilder,
    filter_job_variants: Mapping[tuple[str, str], Any],
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    filter_output_projection_facade_builder: Callable[
        ...,
        FilterOutputProjectionFacade,
    ],
    projected_source_route_executor: ProjectedSourceRouteExecutor,
    route_semantic_module_sequence: Sequence[str],
    evidence_source_preparation_consumer_bindings: EvidenceSourcePreparationConsumerBindings,
    evidence_source_preparation_execution_dependencies: EvidenceSourcePreparationExecutionDependencies,
    evidence_comparison_consumer_bindings: EvidenceComparisonConsumerBindings
    | None = None,
    evidence_comparison_execution_dependencies: EvidenceComparisonExecutionDependencies
    | None = None,
    materialize_evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependenciesMaterializer | None
    ) = None,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
    candidate_scope_decision_mode: CandidateScopeDecisionMode = (
        CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
    ),
    export_slices: bool = False,
    git_provenance: Mapping[str, str | bool | None] | None = None,
) -> PreparedDocumentConsistencyQcFlowExecution:
    """Validate the Flow invocation and allocate its identity without running stages."""
    if not isinstance(prepare_analysis_config_registry, PrepareAnalysisConfigRegistry):
        raise TypeError(
            "prepare_analysis_config_registry must be a PrepareAnalysisConfigRegistry"
        )
    if not isinstance(doc_meta_profile, MetadataProfile):
        raise TypeError("doc_meta_profile must be a MetadataProfile")
    if not callable(doc_meta_summary_builder):
        raise TypeError("doc_meta_summary_builder must be callable")
    if not callable(filter_output_projection_facade_builder):
        raise TypeError("filter_output_projection_facade_builder must be callable")
    if not callable(projected_source_route_executor):
        raise TypeError("projected_source_route_executor must be callable")
    if not isinstance(
        evidence_source_preparation_consumer_bindings,
        EvidenceSourcePreparationConsumerBindings,
    ):
        raise TypeError(
            "evidence_source_preparation_consumer_bindings must be an "
            "EvidenceSourcePreparationConsumerBindings"
        )
    resolved_comparison_consumer_bindings = (
        evidence_comparison_consumer_bindings
        if evidence_comparison_consumer_bindings is not None
        else EvidenceComparisonConsumerBindings(bindings={})
    )
    if not isinstance(
        resolved_comparison_consumer_bindings,
        EvidenceComparisonConsumerBindings,
    ):
        raise TypeError(
            "evidence_comparison_consumer_bindings must be an "
            "EvidenceComparisonConsumerBindings"
        )
    if evidence_comparison_execution_dependencies is not None and not isinstance(
        evidence_comparison_execution_dependencies,
        EvidenceComparisonExecutionDependencies,
    ):
        raise TypeError(
            "evidence_comparison_execution_dependencies must be an "
            "EvidenceComparisonExecutionDependencies"
        )
    if (
        materialize_evidence_comparison_execution_dependencies is not None
        and not callable(materialize_evidence_comparison_execution_dependencies)
    ):
        raise TypeError(
            "materialize_evidence_comparison_execution_dependencies must be callable"
        )
    if not isinstance(
        evidence_source_preparation_execution_dependencies,
        EvidenceSourcePreparationExecutionDependencies,
    ):
        raise TypeError(
            "evidence_source_preparation_execution_dependencies must be an "
            "EvidenceSourcePreparationExecutionDependencies"
        )
    if not isinstance(candidate_scope_decision_mode, CandidateScopeDecisionMode):
        raise TypeError(
            "candidate_scope_decision_mode must be a CandidateScopeDecisionMode"
        )
    enabled_route_semantic_module_ids = frozenset(route_semantic_module_sequence)
    normalized_source_language = _normalize_source_language(source_language)
    _validate_request_binding(
        capability_config,
        uploads,
        participant_inputs,
        source_language=normalized_source_language,
    )
    _validate_operation_bindings(
        capability_config,
        extract_bindings=extract_bindings,
        prepare_analysis_bindings=prepare_analysis_bindings,
        filter_job_bindings=filter_job_bindings,
    )

    slot_binding_specs: list[
        tuple[str, str, PrepareAnalysisConfigId, tuple[str, ...]]
    ] = []
    for slot in capability_config.slots:
        binding_key = _capability_slot_binding_key(
            capability_id=capability_config.capability_id,
            slot_id=slot.slot_id,
        )
        slot_binding_specs.append(
            (
                slot.slot_id,
                _lookup_binding_value(
                    extract_bindings,
                    binding_key=binding_key,
                    binding_name="Extract",
                ),
                _lookup_binding_value(
                    prepare_analysis_bindings,
                    binding_key=binding_key,
                    binding_name="Prepare Analysis",
                ),
                _lookup_binding_value(
                    filter_job_bindings,
                    binding_key=binding_key,
                    binding_name="Filter job",
                ),
            )
        )

    execution: FlowRunExecution = begin_flow_run_execution(
        project_root=project_root,
        capability_id=capability_config.capability_id,
        source_language=normalized_source_language,
        slot_specs=slot_binding_specs,
    )
    execution.candidate_scope_decision_mode = candidate_scope_decision_mode
    return PreparedDocumentConsistencyQcFlowExecution(
        execution=execution,
        project_root=project_root,
        capability_config=capability_config,
        uploads=dict(uploads),
        participant_inputs=dict(participant_inputs),
        source_language=normalized_source_language,
        extract_bindings=dict(extract_bindings),
        prepare_analysis_bindings=dict(prepare_analysis_bindings),
        filter_job_bindings=dict(filter_job_bindings),
        prepare_analysis_config_registry=prepare_analysis_config_registry,
        doc_meta_profile=doc_meta_profile,
        doc_meta_summary_builder=doc_meta_summary_builder,
        filter_job_variants=dict(filter_job_variants),
        filter_output_projection_jobs=dict(filter_output_projection_jobs),
        filter_output_projection_facade_builder=filter_output_projection_facade_builder,
        projected_source_route_executor=projected_source_route_executor,
        route_semantic_module_sequence=tuple(route_semantic_module_sequence),
        enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
        evidence_source_preparation_consumer_bindings=evidence_source_preparation_consumer_bindings,
        evidence_source_preparation_execution_dependencies=(
            evidence_source_preparation_execution_dependencies
        ),
        evidence_comparison_consumer_bindings=resolved_comparison_consumer_bindings,
        evidence_comparison_execution_dependencies=(
            evidence_comparison_execution_dependencies
        ),
        materialize_evidence_comparison_execution_dependencies=(
            materialize_evidence_comparison_execution_dependencies
        ),
        projection_runtime_dependencies=projection_runtime_dependencies,
        candidate_scope_decision_mode=candidate_scope_decision_mode,
        export_slices=export_slices,
        git_provenance=dict(git_provenance) if git_provenance is not None else None,
    )


def execute_prepared_document_consistency_qc_flow(
    prepared: PreparedDocumentConsistencyQcFlowExecution,
) -> DocumentConsistencyQcFlowReport:
    """Run the stages of an already allocated FlowRun."""
    execution = prepared.execution
    project_root = prepared.project_root
    capability_config = prepared.capability_config
    uploads = prepared.uploads
    participant_inputs = prepared.participant_inputs
    normalized_source_language = prepared.source_language
    extract_bindings = prepared.extract_bindings
    prepare_analysis_bindings = prepared.prepare_analysis_bindings
    filter_job_bindings = prepared.filter_job_bindings
    prepare_analysis_config_registry = prepared.prepare_analysis_config_registry
    doc_meta_profile = prepared.doc_meta_profile
    doc_meta_summary_builder = prepared.doc_meta_summary_builder
    filter_job_variants = prepared.filter_job_variants
    filter_output_projection_jobs = prepared.filter_output_projection_jobs
    filter_output_projection_facade_builder = (
        prepared.filter_output_projection_facade_builder
    )
    projected_source_route_executor = prepared.projected_source_route_executor
    route_semantic_module_sequence = prepared.route_semantic_module_sequence
    enabled_route_semantic_module_ids = prepared.enabled_route_semantic_module_ids
    evidence_source_preparation_consumer_bindings = (
        prepared.evidence_source_preparation_consumer_bindings
    )
    evidence_source_preparation_execution_dependencies = (
        prepared.evidence_source_preparation_execution_dependencies
    )
    resolved_comparison_consumer_bindings = prepared.evidence_comparison_consumer_bindings
    evidence_comparison_execution_dependencies = (
        prepared.evidence_comparison_execution_dependencies
    )
    materialize_evidence_comparison_execution_dependencies = (
        prepared.materialize_evidence_comparison_execution_dependencies
    )
    projection_runtime_dependencies = prepared.projection_runtime_dependencies
    candidate_scope_decision_mode = prepared.candidate_scope_decision_mode
    export_slices = prepared.export_slices
    git_provenance = prepared.git_provenance

    git_prov = dict(git_provenance) if git_provenance is not None else None
    slot_results: list[DocumentConsistencyQcSlotResult] = []
    try:
        if (
            candidate_scope_decision_mode
            is CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE
        ):
            for slot, slot_provenance in zip(
                capability_config.slots,
                execution.slot_provenance,
                strict=True,
            ):
                slot_result = _run_canonical_slot_through_candidate_scope_checkpoint(
                    execution=execution,
                    capability_config=capability_config,
                    slot=slot,
                    slot_provenance=slot_provenance,
                    source_language=normalized_source_language,
                    source=uploads[slot.slot_id],
                    participant_input=participant_inputs[slot.slot_id],
                    project_root=project_root,
                    export_slices=export_slices,
                    git_provenance=git_prov,
                    extract_bindings=extract_bindings,
                    prepare_analysis_bindings=prepare_analysis_bindings,
                    filter_job_bindings=filter_job_bindings,
                    prepare_analysis_config_registry=prepare_analysis_config_registry,
                    doc_meta_profile=doc_meta_profile,
                    doc_meta_summary_builder=doc_meta_summary_builder,
                    filter_job_variants=filter_job_variants,
                )
                slot_results.append(slot_result)
            flow_status = resolve_flow_status(execution.slot_provenance)
            summary_path = persist_flow_run_summary(execution, status=flow_status)
            paused_messages = (
                (
                    f"flow_run_id: {execution.flow_run_id}",
                    f"flow_run_summary: {summary_path.as_posix()}",
                    f"source_language: {normalized_source_language}",
                    "flow.paused_at_candidate_scope: true",
                )
                + tuple(
                    f"slot.{branch.slot_id}.status: paused_at_candidate_scope"
                    for branch in slot_results
                )
                + tuple(
                    f"slot.{branch.slot_id}.filter.{job.filter_job_id}.output_dir: "
                    f"{job.stage_result.output_dir.as_posix()}"
                    for branch in slot_results
                    for job in branch.filter_results
                )
            )
            return DocumentConsistencyQcFlowReport(
                result=DocumentConsistencyQcFlowResult(
                    slots=tuple(slot_results),
                    paused_at_candidate_scope=True,
                ),
                messages=paused_messages,
                flow_run_id=execution.flow_run_id,
                flow_run_summary_path=summary_path,
            )

        for slot, slot_provenance in zip(
            capability_config.slots,
            execution.slot_provenance,
            strict=True,
        ):
            slot_result = _run_canonical_slot(
                execution=execution,
                capability_config=capability_config,
                slot=slot,
                slot_provenance=slot_provenance,
                source_language=normalized_source_language,
                source=uploads[slot.slot_id],
                participant_input=participant_inputs[slot.slot_id],
                project_root=project_root,
                export_slices=export_slices,
                git_provenance=git_prov,
                extract_bindings=extract_bindings,
                prepare_analysis_bindings=prepare_analysis_bindings,
                filter_job_bindings=filter_job_bindings,
                prepare_analysis_config_registry=prepare_analysis_config_registry,
                doc_meta_profile=doc_meta_profile,
                doc_meta_summary_builder=doc_meta_summary_builder,
                filter_job_variants=filter_job_variants,
                filter_output_projection_jobs=filter_output_projection_jobs,
                filter_output_projection_facade_builder=(
                    filter_output_projection_facade_builder
                ),
                projected_source_route_executor=projected_source_route_executor,
                route_semantic_module_sequence=route_semantic_module_sequence,
                enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
                evidence_source_preparation_consumer_bindings=(
                    evidence_source_preparation_consumer_bindings
                ),
                evidence_source_preparation_execution_dependencies=(
                    evidence_source_preparation_execution_dependencies
                ),
                projection_runtime_dependencies=projection_runtime_dependencies,
            )
            slot_results.append(slot_result)
    except Exception as exc:
        if (
            candidate_scope_decision_mode
            is CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE
        ):
            reraise_post_allocation_flow_execution_failure(execution, exc)
        flow_status = resolve_flow_status(execution.slot_provenance)
        persist_flow_run_summary_best_effort(execution, status=flow_status)
        raise

    finalization = _finalize_flow_with_evidence_comparison(
        execution=execution,
        capability_config=capability_config,
        slot_results=tuple(slot_results),
        evidence_comparison_consumer_bindings=resolved_comparison_consumer_bindings,
        evidence_comparison_execution_dependencies=(
            evidence_comparison_execution_dependencies
        ),
        materialize_evidence_comparison_execution_dependencies=(
            materialize_evidence_comparison_execution_dependencies
        ),
        git_provenance=git_prov,
    )
    comparison_handoff_resolution = finalization.comparison_handoff_resolution
    comparison_stage_result = finalization.comparison_stage_result
    summary_path = finalization.summary_path

    messages = (
        (
            f"flow_run_id: {execution.flow_run_id}",
            f"flow_run_summary: {summary_path.as_posix()}",
            f"source_language: {normalized_source_language}",
        )
        + tuple(
            f"slot.{branch.slot_id}.source.file_hash: {branch.admitted_source.file_hash}"
            for branch in slot_results
        )
        + tuple(
            f"slot.{branch.slot_id}.extract.run_id: {branch.extract_report.result.run_id}"
            for branch in slot_results
        )
        + tuple(
            "slot."
            f"{branch.slot_id}.prepare_analysis.run_id: "
            f"{branch.prepare_analysis_report.documents[0].run_id}"
            for branch in slot_results
        )
        + tuple(
            f"slot.{branch.slot_id}.doc_meta.output_dir: "
            f"{branch.doc_meta_report['output_dir']}"
            for branch in slot_results
        )
        + tuple(
            f"slot.{branch.slot_id}.filter.{job.filter_job_id}.output_dir: "
            f"{job.stage_result.output_dir.as_posix()}"
            for branch in slot_results
            for job in branch.filter_results
        )
        + tuple(
            "slot."
            f"{branch.slot_id}.filter_output_projection.{job.filter_job_id}.output_dir: "
            f"{job.stage_result.output_dir.as_posix()}"
            for branch in slot_results
            for job in branch.projection_results
        )
        + tuple(
            f"slot.{branch.slot_id}.route.{module.semantic_module_id}.route_invoked: "
            f"{module.route_invoked}"
            for branch in slot_results
            for module in branch.route_semantic_module_results
        )
        + tuple(
            "slot."
            f"{branch.slot_id}.evidence_source_preparation."
            f"{module.semantic_module_id}.invoked: "
            f"{module.evidence_source_preparation_invoked}"
            for branch in slot_results
            for module in branch.route_semantic_module_results
        )
        + (
            (
                f"evidence_comparison.handoff_status: "
                f"{comparison_handoff_resolution.status.value}",
                f"evidence_comparison.stage_executed: "
                f"{execution.evidence_comparison_provenance.stage_executed}",
            )
            if execution.evidence_comparison_provenance is not None
            else ()
        )
        + (
            (
                f"evidence_comparison.run_id: "
                f"{execution.evidence_comparison_provenance.run_id}",
                f"evidence_comparison.output_dir: "
                f"{execution.evidence_comparison_provenance.output_dir}",
                f"evidence_comparison.run_status: "
                f"{execution.evidence_comparison_provenance.run_status}",
            )
            if execution.evidence_comparison_provenance is not None
            and execution.evidence_comparison_provenance.stage_executed
            else ()
        )
    )
    return DocumentConsistencyQcFlowReport(
        result=DocumentConsistencyQcFlowResult(
            slots=tuple(slot_results),
            evidence_comparison_handoff_resolution=(comparison_handoff_resolution),
            evidence_comparison_stage_result=comparison_stage_result,
        ),
        messages=messages,
        flow_run_id=execution.flow_run_id,
        flow_run_summary_path=summary_path,
    )


def run_document_consistency_qc_flow(
    *,
    project_root: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    uploads: Mapping[str, Source],
    participant_inputs: Mapping[str, DocumentConsistencyQcParticipantRunInput],
    source_language: str,
    extract_bindings: Mapping[tuple[str, str], str],
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId],
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry,
    doc_meta_profile: MetadataProfile,
    doc_meta_summary_builder: DocMetaSummaryBuilder,
    filter_job_variants: Mapping[tuple[str, str], Any],
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    filter_output_projection_facade_builder: Callable[..., FilterOutputProjectionFacade],
    projected_source_route_executor: ProjectedSourceRouteExecutor,
    route_semantic_module_sequence: Sequence[str],
    evidence_source_preparation_consumer_bindings: EvidenceSourcePreparationConsumerBindings,
    evidence_source_preparation_execution_dependencies: EvidenceSourcePreparationExecutionDependencies,
    evidence_comparison_consumer_bindings: EvidenceComparisonConsumerBindings | None = None,
    evidence_comparison_execution_dependencies: EvidenceComparisonExecutionDependencies | None = None,
    materialize_evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependenciesMaterializer | None
    ) = None,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies | None = None,
    candidate_scope_decision_mode: CandidateScopeDecisionMode = (
        CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
    ),
    export_slices: bool = False,
    git_provenance: Mapping[str, str | bool | None] | None = None,
) -> DocumentConsistencyQcFlowReport:
    """Compatibility convenience that allocates then executes one FlowRun."""
    prepared = prepare_and_allocate_document_consistency_qc_flow(
        project_root=project_root,
        capability_config=capability_config,
        uploads=uploads,
        participant_inputs=participant_inputs,
        source_language=source_language,
        extract_bindings=extract_bindings,
        prepare_analysis_bindings=prepare_analysis_bindings,
        filter_job_bindings=filter_job_bindings,
        prepare_analysis_config_registry=prepare_analysis_config_registry,
        doc_meta_profile=doc_meta_profile,
        doc_meta_summary_builder=doc_meta_summary_builder,
        filter_job_variants=filter_job_variants,
        filter_output_projection_jobs=filter_output_projection_jobs,
        filter_output_projection_facade_builder=filter_output_projection_facade_builder,
        projected_source_route_executor=projected_source_route_executor,
        route_semantic_module_sequence=route_semantic_module_sequence,
        evidence_source_preparation_consumer_bindings=(
            evidence_source_preparation_consumer_bindings
        ),
        evidence_source_preparation_execution_dependencies=(
            evidence_source_preparation_execution_dependencies
        ),
        evidence_comparison_consumer_bindings=evidence_comparison_consumer_bindings,
        evidence_comparison_execution_dependencies=(
            evidence_comparison_execution_dependencies
        ),
        materialize_evidence_comparison_execution_dependencies=(
            materialize_evidence_comparison_execution_dependencies
        ),
        projection_runtime_dependencies=projection_runtime_dependencies,
        candidate_scope_decision_mode=candidate_scope_decision_mode,
        export_slices=export_slices,
        git_provenance=git_provenance,
    )
    return execute_prepared_document_consistency_qc_flow(prepared)


def _completed_slot_result_from_provenance(
    slot_provenance: FlowRunSlotProvenance,
    *,
    admitted_source: DocumentIntakeSourceBinding,
) -> DocumentConsistencyQcSlotResult:
    route_semantic_module_results: list[RouteSemanticModuleFlowResult] = []
    for module in slot_provenance.route_semantic_modules:
        esp_stage_result: EvidenceSourcePreparationStageResult | None = None
        if (
            module.evidence_source_preparation_invoked
            and module.evidence_source_preparation_declared_output_path
            and module.evidence_source_preparation_run_id
            and module.evidence_source_preparation_stage_executor_id
            and module.evidence_source_preparation_run_summary_path
            and slot_provenance.doc_id
        ):
            esp_stage_result = EvidenceSourcePreparationStageResult(
                output_dir=Path(
                    module.evidence_source_preparation_declared_output_path
                ).parent,
                run_id=module.evidence_source_preparation_run_id,
                doc_id=slot_provenance.doc_id,
                semantic_module_id=module.semantic_module_id,
                stage_executor_id=module.evidence_source_preparation_stage_executor_id,
                declared_output_path=Path(
                    module.evidence_source_preparation_declared_output_path
                ),
                run_summary_path=Path(
                    module.evidence_source_preparation_run_summary_path
                ),
            )
        route_semantic_module_results.append(
            RouteSemanticModuleFlowResult(
                semantic_module_id=module.semantic_module_id,
                selected_projected_source_count=module.selected_projected_source_count
                or 0,
                route_invoked=bool(module.route_invoked),
                stage_result=None,
                evidence_source_preparation_invoked=bool(
                    module.evidence_source_preparation_invoked
                ),
                evidence_source_preparation_stage_result=esp_stage_result,
            )
        )
    admitted_source, extract_report, prepare_analysis_report = (
        build_resumed_upstream_stubs(
            slot_provenance,
            admitted_source=admitted_source,
        )
    )
    return DocumentConsistencyQcSlotResult(
        slot_id=slot_provenance.slot_id,
        admitted_source=admitted_source,
        extract_report=extract_report,
        prepare_analysis_report=prepare_analysis_report,
        doc_meta_report=build_doc_meta_report_from_provenance(slot_provenance),
        filter_results=_filter_job_flow_results_from_provenance(slot_provenance),
        projection_results=(),
        route_semantic_module_results=tuple(route_semantic_module_results),
    )


def _collect_slot_results_for_flow(
    execution: FlowRunExecution,
    *,
    fresh_results_by_slot_id: Mapping[str, DocumentConsistencyQcSlotResult],
    admitted_sources_by_slot_id: Mapping[str, DocumentIntakeSourceBinding],
) -> tuple[DocumentConsistencyQcSlotResult, ...]:
    collected: list[DocumentConsistencyQcSlotResult] = []
    for slot_provenance in execution.slot_provenance:
        if slot_provenance.slot_id in fresh_results_by_slot_id:
            collected.append(fresh_results_by_slot_id[slot_provenance.slot_id])
        elif slot_provenance.status == "success":
            collected.append(
                _completed_slot_result_from_provenance(
                    slot_provenance,
                    admitted_source=admitted_sources_by_slot_id[
                        slot_provenance.slot_id
                    ],
                )
            )
    return tuple(collected)


def resume_document_consistency_qc_flow(
    *,
    project_root: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    flow_run_id: str,
    candidate_scope_decisions_by_slot: Mapping[
        str, Sequence[FilterJobCandidateScopeSelection]
    ],
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    filter_output_projection_facade_builder: Callable[
        ...,
        FilterOutputProjectionFacade,
    ],
    projected_source_route_executor: ProjectedSourceRouteExecutor,
    route_semantic_module_sequence: Sequence[str],
    evidence_source_preparation_consumer_bindings: EvidenceSourcePreparationConsumerBindings,
    evidence_source_preparation_execution_dependencies: EvidenceSourcePreparationExecutionDependencies,
    evidence_comparison_consumer_bindings: EvidenceComparisonConsumerBindings
    | None = None,
    evidence_comparison_execution_dependencies: EvidenceComparisonExecutionDependencies
    | None = None,
    materialize_evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependenciesMaterializer | None
    ) = None,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
    candidate_scope_manual_default_filter_job_bindings: Mapping[tuple[str, str], str]
    | None = None,
    git_provenance: Mapping[str, str | bool | None] | None = None,
) -> DocumentConsistencyQcFlowReport:
    """Resume a flow-level Candidate Scope checkpoint for all configured slots."""
    if capability_config.capability_id is None:
        raise ValueError("capability_config.capability_id is required")

    execution = load_flow_run_execution(
        project_root=project_root, flow_run_id=flow_run_id
    )
    paused_slots = validate_candidate_scope_resume_decisions(
        execution,
        capability_config,
        flow_run_id=flow_run_id,
        candidate_scope_decisions_by_slot=candidate_scope_decisions_by_slot,
    )
    admitted_sources_by_slot_id = {
        slot.slot_id: resolve_resumed_admitted_source(
            project_root=project_root,
            flow_root=execution.output_dir,
            slot_provenance=slot,
        )
        for slot in execution.slot_provenance
    }

    enabled_route_semantic_module_ids = frozenset(route_semantic_module_sequence)
    git_prov = dict(git_provenance) if git_provenance is not None else None
    fresh_results_by_slot_id: dict[str, DocumentConsistencyQcSlotResult] = {}

    try:
        for slot_provenance in paused_slots:
            slot_id = slot_provenance.slot_id
            candidate_scope_selections = candidate_scope_decisions_by_slot[slot_id]
            manual_default_filter_job_id: str | None = None
            if candidate_scope_manual_default_filter_job_bindings is not None:
                manual_default_filter_job_id = (
                    candidate_scope_manual_default_filter_job_bindings.get(
                        (capability_config.capability_id, slot_id)
                    )
                )

            filter_job_ids = tuple(slot_provenance.filter_job_ids)
            if not filter_job_ids:
                raise FlowResumeError(
                    f"paused slot {slot_id!r} is missing filter_job_ids"
                )

            analysis_bundle_path = Path(slot_provenance.analysis_bundle_path or "")
            block_manifest_path = Path(slot_provenance.block_manifest_path or "")
            if not analysis_bundle_path.is_file() or not block_manifest_path.is_file():
                raise FlowResumeError(
                    f"paused slot {slot_id!r} upstream analysis artifacts are missing"
                )

            analysis_bundle = load_json(analysis_bundle_path)
            block_manifest = load_json(block_manifest_path)
            resolved_jobs = materialize_candidate_scope_zone_matches(
                filter_job_ids=filter_job_ids,
                filter_jobs=tuple(slot_provenance.filter_jobs),
                selections=tuple(candidate_scope_selections),
                analysis_bundle=analysis_bundle,
                block_manifest=block_manifest,
                flow_root=execution.output_dir,
                slot_id=slot_id,
                doc_id=str(slot_provenance.doc_id or ""),
                project_root=project_root,
                manual_default_filter_job_id=manual_default_filter_job_id,
            )
            decision_payload = build_candidate_scope_decision_payload(
                flow_run_id=flow_run_id,
                slot_id=slot_id,
                filter_job_ids=filter_job_ids,
                resolved_jobs=resolved_jobs,
            )
            decision_path = persist_candidate_scope_decision(
                flow_root=execution.output_dir,
                slot_id=slot_id,
                payload=decision_payload,
            )
            slot_provenance.candidate_scope_decision_path = decision_path.as_posix()

            filter_results = _filter_job_flow_results_from_provenance(slot_provenance)
            doc_meta_report = build_doc_meta_report_from_provenance(slot_provenance)
            zone_match_bundle_paths = zone_match_bundle_paths_from_resolved(
                resolved_jobs
            )

            projection_results, route_semantic_module_results = (
                _continue_slot_after_candidate_scope(
                    slot_id=slot_id,
                    filter_results=filter_results,
                    zone_match_bundle_paths=zone_match_bundle_paths,
                    analysis_bundle_path=analysis_bundle_path,
                    block_manifest_path=block_manifest_path,
                    doc_meta_bundle_path=Path(doc_meta_report["doc_meta_bundle_path"]),
                    flow_root=execution.output_dir,
                    slot_provenance=slot_provenance,
                    filter_output_projection_jobs=filter_output_projection_jobs,
                    filter_output_projection_facade_builder=(
                        filter_output_projection_facade_builder
                    ),
                    projected_source_route_executor=projected_source_route_executor,
                    route_semantic_module_sequence=route_semantic_module_sequence,
                    enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
                    evidence_source_preparation_consumer_bindings=(
                        evidence_source_preparation_consumer_bindings
                    ),
                    evidence_source_preparation_execution_dependencies=(
                        evidence_source_preparation_execution_dependencies
                    ),
                    projection_runtime_dependencies=projection_runtime_dependencies,
                    git_provenance=git_prov,
                )
            )
            slot_provenance.status = "success"
            admitted_source, extract_report, prepare_analysis_report = (
                build_resumed_upstream_stubs(
                    slot_provenance,
                    admitted_source=admitted_sources_by_slot_id[slot_id],
                )
            )
            fresh_results_by_slot_id[slot_id] = DocumentConsistencyQcSlotResult(
                slot_id=slot_id,
                admitted_source=admitted_source,
                extract_report=extract_report,
                prepare_analysis_report=prepare_analysis_report,
                doc_meta_report=doc_meta_report,
                filter_results=filter_results,
                projection_results=projection_results,
                route_semantic_module_results=route_semantic_module_results,
            )
    except Exception:
        for slot_provenance in paused_slots:
            if slot_provenance.status != "success":
                slot_provenance.status = (
                    "partial" if slot_provenance.file_hash is not None else "failed"
                )
        flow_status = resolve_flow_status(execution.slot_provenance)
        persist_flow_run_summary_best_effort(execution, status=flow_status)
        raise

    slot_results = _collect_slot_results_for_flow(
        execution,
        fresh_results_by_slot_id=fresh_results_by_slot_id,
        admitted_sources_by_slot_id=admitted_sources_by_slot_id,
    )
    resolved_comparison_consumer_bindings = (
        evidence_comparison_consumer_bindings
        if evidence_comparison_consumer_bindings is not None
        else EvidenceComparisonConsumerBindings(bindings={})
    )
    finalization = _finalize_flow_with_evidence_comparison(
        execution=execution,
        capability_config=capability_config,
        slot_results=slot_results,
        evidence_comparison_consumer_bindings=resolved_comparison_consumer_bindings,
        evidence_comparison_execution_dependencies=(
            evidence_comparison_execution_dependencies
        ),
        materialize_evidence_comparison_execution_dependencies=(
            materialize_evidence_comparison_execution_dependencies
        ),
        git_provenance=git_prov,
    )
    comparison_handoff_resolution = finalization.comparison_handoff_resolution
    comparison_stage_result = finalization.comparison_stage_result
    summary_path = finalization.summary_path

    return DocumentConsistencyQcFlowReport(
        result=DocumentConsistencyQcFlowResult(
            slots=slot_results,
            evidence_comparison_handoff_resolution=comparison_handoff_resolution,
            evidence_comparison_stage_result=comparison_stage_result,
            paused_at_candidate_scope=False,
        ),
        messages=(
            f"flow_run_id: {execution.flow_run_id}",
            f"flow_run_summary: {summary_path.as_posix()}",
        ),
        flow_run_id=execution.flow_run_id,
        flow_run_summary_path=summary_path,
    )


__all__ = [
    "DocMetaStageReport",
    "DocMetaSummaryBuilder",
    "DocumentConsistencyQcFlowReport",
    "DocumentConsistencyQcFlowResult",
    "DocumentConsistencyQcSlotResult",
    "FilterJobFlowResult",
    "FlowResumeError",
    "ProjectionJobFlowResult",
    "PreparedDocumentConsistencyQcFlowExecution",
    "RouteSemanticModuleFlowResult",
    "_continue_slot_after_candidate_scope",
    "_finalize_flow_with_evidence_comparison",
    "_run_canonical_slot",
    "_run_canonical_slot_through_candidate_scope_checkpoint",
    "_run_slot_through_candidate_scope_checkpoint",
    "execute_prepared_document_consistency_qc_flow",
    "prepare_and_allocate_document_consistency_qc_flow",
    "resume_document_consistency_qc_flow",
    "run_document_consistency_qc_flow",
]
