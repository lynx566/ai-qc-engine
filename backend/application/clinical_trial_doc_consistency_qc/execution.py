"""Installed execution boundary for Clinical Trial × Document Consistency QC."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantRunInput,
    PreparedDocumentConsistencyQcFlowExecution,
    execute_prepared_document_consistency_qc_flow,
    prepare_and_allocate_document_consistency_qc_flow,
    resume_document_consistency_qc_flow,
)
from llm.execution_configs import (
    materialize_llm_provider,
    resolve_llm_execution_config,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_LLM_SLOT,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
)

from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
    PrepareRequestOptionsLoader,
)
from application.document_consistency_qc.document_type_result import (
    DocumentConsistencyQcApplicationResult,
    build_document_consistency_qc_application_result,
)
from application.document_consistency_qc.execution_request import (
    DocumentConsistencyQcExecutionRequest,
)
from application.document_consistency_qc.resume_request import (
    DocumentConsistencyQcResumeRequest,
)

from .comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from .comparison_finding_consolidation_installation import (
    resolve_installed_comparison_finding_consolidation_config,
)
from .evidence_comparison_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY,
)
from .expected_document_type_installation import (
    CLINICAL_TRIAL_DOCUMENT_TYPES,
)
from .projection_runtime import materialize_installed_projection_runtime_dependencies


def _build_participant_inputs(
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    participant_privacy_paths: Mapping[str, Path | None],
    load_prepare_request_options: PrepareRequestOptionsLoader,
) -> dict[str, DocumentConsistencyQcParticipantRunInput]:
    participant_inputs: dict[str, DocumentConsistencyQcParticipantRunInput] = {}
    for slot in capability_config.slots:
        privacy_path = participant_privacy_paths[slot.slot_id]
        participant_inputs[slot.slot_id] = DocumentConsistencyQcParticipantRunInput(
            prepare_analysis_request_options=load_prepare_request_options(privacy_path),
        )
    return participant_inputs


def _materialize_installed_evidence_source_preparation_execution_dependencies(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
) -> ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies:
    bindings = composition.llm_dependency_bindings
    try:
        config_id = bindings[CLINICAL_SAFETY_AGGREGATE_LLM_SLOT]
    except KeyError as exc:
        raise ValueError(
            "missing installed LLM dependency binding for slot "
            f"{CLINICAL_SAFETY_AGGREGATE_LLM_SLOT!r}"
        ) from exc
    config = resolve_llm_execution_config(config_id)
    provider = materialize_llm_provider(config)
    return ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
        llm_mode="api",
        llm_profile=config.profile_id,
        provider=provider,
        llm_execution_config=config.to_provenance_record(),
    )


def _resolve_projection_runtime_dependencies(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies | None,
) -> FilterOutputProjectionRuntimeDependencies:
    if projection_runtime_dependencies is not None:
        return projection_runtime_dependencies
    return materialize_installed_projection_runtime_dependencies(
        composition=composition,
    )


def _resolve_evidence_source_preparation_execution_dependencies(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ),
) -> EvidenceSourcePreparationExecutionDependencies:
    if evidence_source_preparation_execution_dependencies is not None:
        return evidence_source_preparation_execution_dependencies
    return _materialize_installed_evidence_source_preparation_execution_dependencies(
        composition=composition,
    )


def _materialize_installed_comparison_llm_slot(
    *,
    bindings: Mapping[str, str],
    slot_id: str,
) -> tuple[object, dict[str, object]]:
    try:
        config_id = bindings[slot_id]
    except KeyError as exc:
        raise ValueError(
            f"missing installed LLM dependency binding for slot {slot_id!r}"
        ) from exc
    llm_config = resolve_llm_execution_config(config_id)
    provider = materialize_llm_provider(llm_config)
    return provider, llm_config.to_provenance_record()


def materialize_installed_evidence_comparison_execution_dependencies(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    capability_id: str,
    assessment_provider=None,
    assessment_second_pass_provider=None,
    verification_provider=None,
    consolidation_provider=None,
) -> ClinicalTrialAggregateEvidenceComparisonExecutionDependencies:
    """Materialize installed Evidence Comparison execution dependencies for one capability."""

    binding = (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            capability_id
        )
    )
    if binding is None:
        raise ValueError(
            f"capability {capability_id!r} has no installed Evidence Comparison consumer binding"
        )

    assessment_config = resolve_installed_comparison_finding_assessment_config(
        capability_id
    )
    consolidation_config = resolve_installed_comparison_finding_consolidation_config(
        capability_id
    )
    providers_injected = (
        assessment_provider is not None
        or assessment_second_pass_provider is not None
        or verification_provider is not None
        or consolidation_provider is not None
    )
    if providers_injected:
        if (
            assessment_provider is None
            or assessment_second_pass_provider is None
            or verification_provider is None
            or consolidation_provider is None
        ):
            raise ValueError(
                "assessment_provider, assessment_second_pass_provider, "
                "verification_provider, and consolidation_provider must be "
                "injected together"
            )
        resolved_assessment_provider = assessment_provider
        resolved_assessment_second_pass_provider = assessment_second_pass_provider
        resolved_verification_provider = verification_provider
        resolved_consolidation_provider = consolidation_provider
        assessment_llm_execution_config = None
        assessment_second_pass_llm_execution_config = None
        verification_llm_execution_config = None
        consolidation_llm_execution_config = None
    else:
        bindings = composition.llm_dependency_bindings
        resolved_assessment_provider, assessment_llm_execution_config = (
            _materialize_installed_comparison_llm_slot(
                bindings=bindings,
                slot_id=CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT,
            )
        )
        (
            resolved_assessment_second_pass_provider,
            assessment_second_pass_llm_execution_config,
        ) = _materialize_installed_comparison_llm_slot(
            bindings=bindings,
            slot_id=(
                CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT
            ),
        )
        resolved_verification_provider, verification_llm_execution_config = (
            _materialize_installed_comparison_llm_slot(
                bindings=bindings,
                slot_id=CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT,
            )
        )
        resolved_consolidation_provider, consolidation_llm_execution_config = (
            _materialize_installed_comparison_llm_slot(
                bindings=bindings,
                slot_id=CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT,
            )
        )

    return ClinicalTrialAggregateEvidenceComparisonExecutionDependencies(
        capability_id=capability_id,
        assessment_config=assessment_config,
        consolidation_config=consolidation_config,
        assessment_provider=resolved_assessment_provider,
        assessment_second_pass_provider=resolved_assessment_second_pass_provider,
        verification_provider=resolved_verification_provider,
        consolidation_provider=resolved_consolidation_provider,
        max_concurrency=INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_MAX_CONCURRENCY,
        assessment_llm_execution_config=assessment_llm_execution_config,
        assessment_second_pass_llm_execution_config=(
            assessment_second_pass_llm_execution_config
        ),
        verification_llm_execution_config=verification_llm_execution_config,
        consolidation_llm_execution_config=consolidation_llm_execution_config,
    )


def _resolve_evidence_comparison_execution_dependencies(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    capability_id: str,
    evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependencies | None
    ),
) -> EvidenceComparisonExecutionDependencies:
    if evidence_comparison_execution_dependencies is not None:
        return evidence_comparison_execution_dependencies
    return materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id=capability_id,
    )


@dataclass(frozen=True, slots=True)
class PreparedInstalledDocumentConsistencyQcExecution:
    """Installed application handoff for an allocated DCQC FlowRun."""

    flow: PreparedDocumentConsistencyQcFlowExecution
    capability_id: str
    expected_document_type_bindings: Mapping[tuple[str, str], str]

    @property
    def flow_id(self) -> str:
        return self.flow.execution.flow_id

    @property
    def flow_run_id(self) -> str:
        return self.flow.execution.flow_run_id


def prepare_and_allocate_installed_clinical_trial_document_consistency_qc(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    request: DocumentConsistencyQcExecutionRequest,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ) = None,
) -> PreparedInstalledDocumentConsistencyQcExecution:
    """Resolve installed inputs and allocate a FlowRun without executing it."""

    capability_config = composition.capabilities[request.capability_id]
    participant_inputs = _build_participant_inputs(
        capability_config=capability_config,
        participant_privacy_paths=request.participant_privacy_paths,
        load_prepare_request_options=composition.load_prepare_request_options,
    )
    resolved_projection_runtime_dependencies = _resolve_projection_runtime_dependencies(
        composition=composition,
        projection_runtime_dependencies=projection_runtime_dependencies,
    )
    resolved_esp_execution_dependencies = (
        _resolve_evidence_source_preparation_execution_dependencies(
            composition=composition,
            evidence_source_preparation_execution_dependencies=(
                evidence_source_preparation_execution_dependencies
            ),
        )
    )
    prepared_flow = prepare_and_allocate_document_consistency_qc_flow(
        project_root=request.project_root,
        capability_config=capability_config,
        uploads=request.participant_inputs,
        participant_inputs=participant_inputs,
        source_language=request.source_language,
        extract_bindings=composition.extract_bindings,
        prepare_analysis_bindings=composition.prepare_analysis_bindings,
        filter_job_bindings=composition.filter_job_bindings,
        prepare_analysis_config_registry=composition.prepare_analysis_config_registry,
        doc_meta_profile=composition.doc_meta_profile,
        doc_meta_summary_builder=composition.doc_meta_summary_builder,
        filter_job_variants=composition.filter_job_variants,
        filter_output_projection_jobs=composition.filter_output_projection_jobs,
        filter_output_projection_facade_builder=(
            composition.filter_output_projection_facade_builder
        ),
        projected_source_route_executor=composition.projected_source_route_executor,
        route_semantic_module_sequence=composition.route_semantic_module_sequence,
        evidence_source_preparation_consumer_bindings=(
            composition.evidence_source_preparation_consumer_bindings
        ),
        evidence_source_preparation_execution_dependencies=(
            resolved_esp_execution_dependencies
        ),
        evidence_comparison_consumer_bindings=(
            composition.evidence_comparison_consumer_bindings
        ),
        materialize_evidence_comparison_execution_dependencies=(
            lambda capability_id: (
                materialize_installed_evidence_comparison_execution_dependencies(
                    composition=composition,
                    capability_id=capability_id,
                )
            )
        ),
        projection_runtime_dependencies=resolved_projection_runtime_dependencies,
        candidate_scope_decision_mode=request.candidate_scope_decision_mode,
    )
    return PreparedInstalledDocumentConsistencyQcExecution(
        flow=prepared_flow,
        capability_id=request.capability_id,
        expected_document_type_bindings=dict(
            composition.expected_document_type_bindings
        ),
    )


def execute_prepared_installed_clinical_trial_document_consistency_qc(
    prepared: PreparedInstalledDocumentConsistencyQcExecution,
) -> DocumentConsistencyQcApplicationResult:
    """Execute one prepared installed FlowRun and build its application result."""
    flow_report = execute_prepared_document_consistency_qc_flow(prepared.flow)
    return build_document_consistency_qc_application_result(
        capability_id=prepared.capability_id,
        flow_report=flow_report,
        expected_document_type_bindings=prepared.expected_document_type_bindings,
        supported_document_types=CLINICAL_TRIAL_DOCUMENT_TYPES,
    )


def execute_installed_clinical_trial_document_consistency_qc(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    request: DocumentConsistencyQcExecutionRequest,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ) = None,
) -> DocumentConsistencyQcApplicationResult:
    """Compatibility convenience that allocates and executes one installed run."""
    prepared = prepare_and_allocate_installed_clinical_trial_document_consistency_qc(
        composition=composition,
        request=request,
        projection_runtime_dependencies=projection_runtime_dependencies,
        evidence_source_preparation_execution_dependencies=(
            evidence_source_preparation_execution_dependencies
        ),
    )
    return execute_prepared_installed_clinical_trial_document_consistency_qc(
        prepared
    )


def resume_installed_clinical_trial_document_consistency_qc(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    request: DocumentConsistencyQcResumeRequest,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies
    | None = None,
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ) = None,
    evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependencies | None
    ) = None,
) -> DocumentConsistencyQcApplicationResult:
    """Resume one paused installed Clinical Trial Document Consistency QC flow."""

    capability_id = _resolve_capability_for_resume(
        composition=composition,
        flow_run_id=request.flow_run_id,
        project_root=request.project_root,
    )
    capability_config = composition.capabilities[capability_id]

    resolved_projection_runtime_dependencies = _resolve_projection_runtime_dependencies(
        composition=composition,
        projection_runtime_dependencies=projection_runtime_dependencies,
    )
    resolved_esp_execution_dependencies = (
        _resolve_evidence_source_preparation_execution_dependencies(
            composition=composition,
            evidence_source_preparation_execution_dependencies=(
                evidence_source_preparation_execution_dependencies
            ),
        )
    )
    comparison_flow_kwargs: dict[str, object] = {}
    if evidence_comparison_execution_dependencies is not None:
        comparison_flow_kwargs["evidence_comparison_execution_dependencies"] = (
            _resolve_evidence_comparison_execution_dependencies(
                composition=composition,
                capability_id=capability_config.capability_id,
                evidence_comparison_execution_dependencies=(
                    evidence_comparison_execution_dependencies
                ),
            )
        )
    else:
        comparison_flow_kwargs[
            "materialize_evidence_comparison_execution_dependencies"
        ] = lambda capability_id: (
            materialize_installed_evidence_comparison_execution_dependencies(
                composition=composition,
                capability_id=capability_id,
            )
        )
    flow_report = resume_document_consistency_qc_flow(
        project_root=request.project_root,
        capability_config=capability_config,
        flow_run_id=request.flow_run_id,
        candidate_scope_decisions_by_slot=request.candidate_scope_decisions_by_slot,
        filter_output_projection_jobs=composition.filter_output_projection_jobs,
        filter_output_projection_facade_builder=(
            composition.filter_output_projection_facade_builder
        ),
        projected_source_route_executor=composition.projected_source_route_executor,
        route_semantic_module_sequence=composition.route_semantic_module_sequence,
        evidence_source_preparation_consumer_bindings=(
            composition.evidence_source_preparation_consumer_bindings
        ),
        evidence_source_preparation_execution_dependencies=(
            resolved_esp_execution_dependencies
        ),
        evidence_comparison_consumer_bindings=(
            composition.evidence_comparison_consumer_bindings
        ),
        **comparison_flow_kwargs,
        projection_runtime_dependencies=resolved_projection_runtime_dependencies,
        candidate_scope_manual_default_filter_job_bindings=(
            composition.candidate_scope_manual_default_filter_job_bindings
        ),
    )
    return build_document_consistency_qc_application_result(
        capability_id=capability_config.capability_id,
        flow_report=flow_report,
        expected_document_type_bindings=composition.expected_document_type_bindings,
        supported_document_types=CLINICAL_TRIAL_DOCUMENT_TYPES,
    )


def _resolve_capability_for_resume(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    flow_run_id: str,
    project_root: Path,
) -> str:
    from execution_flow.document_consistency_qc.flow_loader import (
        load_flow_run_execution,
    )

    execution = load_flow_run_execution(
        project_root=project_root,
        flow_run_id=flow_run_id,
    )
    capability_id = execution.capability_id
    if capability_id not in composition.capabilities:
        raise ValueError(
            f"paused flow capability_id {capability_id!r} is not installed in composition"
        )
    return capability_id


__all__ = [
    "PreparedInstalledDocumentConsistencyQcExecution",
    "execute_installed_clinical_trial_document_consistency_qc",
    "execute_prepared_installed_clinical_trial_document_consistency_qc",
    "materialize_installed_evidence_comparison_execution_dependencies",
    "prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
    "resume_installed_clinical_trial_document_consistency_qc",
]
