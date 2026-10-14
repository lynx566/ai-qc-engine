"""Clinical-trial aggregate Evidence Comparison production stage runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from llm.providers.base import LLMProvider
from operations.evidence_comparison.contracts import (
    EvidenceComparisonExecutor,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageExecutor,
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)
from steps import evidence_comparison as comparison_step
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.config import (
    ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.config import (
    ResolvedComparisonFindingConsolidationConfig,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution import (
    AggregateEvidenceComparisonFinalizationFailure,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceComparisonExecution,
    AggregateEvidenceComparisonExecutionInput,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_adapter import (
    build_aggregate_evidence_comparison_invocation,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonInvocation,
    AggregateEvidenceComparisonSourceAdapter,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.source_adapter import (
    adapt_clinical_safety_aggregate_source_bundle,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    persist_aggregate_evidence_comparison_pre_final_failure,
    persist_unified_aggregate_evidence_comparison_execution,
)
from runtime.io import load_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_provenance import snapshot_git_provenance_before_run

CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID = (
    "clinical_trial_doc.clinical_safety.aggregate_evidence"
)


@dataclass(frozen=True, slots=True)
class ClinicalTrialAggregateEvidenceComparisonExecutionDependencies(
    EvidenceComparisonExecutionDependencies,
):
    """Concrete execution dependencies for clinical-safety aggregate Comparison."""

    capability_id: str
    assessment_config: ResolvedClinicalSafetyComparisonFindingAssessmentConfig
    assessment_provider: LLMProvider
    assessment_second_pass_provider: LLMProvider
    verification_provider: LLMProvider
    consolidation_config: ResolvedComparisonFindingConsolidationConfig
    consolidation_provider: LLMProvider
    max_concurrency: int | None = None
    assessment_llm_execution_config: dict[str, Any] | None = None
    assessment_second_pass_llm_execution_config: dict[str, Any] | None = None
    verification_llm_execution_config: dict[str, Any] | None = None
    consolidation_llm_execution_config: dict[str, Any] | None = None


def resolve_evidence_comparison_stage_run_id(*, stamp=None) -> str:
    resolved_stamp = stamp or utc_run_stamp()
    return format_run_timestamp(resolved_stamp)


def build_aggregate_evidence_comparison_invocation_from_stage_input(
    *,
    stage_input: EvidenceComparisonStageInput,
    source_adapter: AggregateEvidenceComparisonSourceAdapter = (
        adapt_clinical_safety_aggregate_source_bundle
    ),
) -> AggregateEvidenceComparisonInvocation:
    """Load ordered ESP participant outputs into canonical Comparison invocation."""

    if not isinstance(stage_input, EvidenceComparisonStageInput):
        raise TypeError(
            "stage_input must be an EvidenceComparisonStageInput; "
            f"got {type(stage_input)!r}"
        )

    role_bound_evidence = []
    for participant in stage_input.participants:
        source: Any = load_json(participant.declared_output_path)
        if not isinstance(source, Mapping):
            raise TypeError("loaded aggregate evidence source must be a mapping")
        role_bound_evidence.append((participant.role_id, source_adapter(source)))

    return build_aggregate_evidence_comparison_invocation(
        participants=role_bound_evidence
    )


def execute_aggregate_evidence_comparison_transport(
    *,
    stage_input: EvidenceComparisonStageInput,
    evidence_comparison_executor: EvidenceComparisonExecutor,
    source_adapter: AggregateEvidenceComparisonSourceAdapter = (
        adapt_clinical_safety_aggregate_source_bundle
    ),
):
    """Load ordered ESP outputs and execute the canonical in-memory step."""

    invocation = build_aggregate_evidence_comparison_invocation_from_stage_input(
        stage_input=stage_input,
        source_adapter=source_adapter,
    )
    return comparison_step.run_evidence_comparison(
        invocation=invocation,
        executor=evidence_comparison_executor,
    )


def execute_clinical_trial_aggregate_evidence_comparison_stage(
    *,
    stage_input: EvidenceComparisonStageInput,
    evidence_comparison_executor: EvidenceComparisonExecutor,
    source_adapter: AggregateEvidenceComparisonSourceAdapter = (
        adapt_clinical_safety_aggregate_source_bundle
    ),
) -> EvidenceComparisonStageResult:
    """Run canonical Comparison execution and persist unified stage artifacts."""

    if not isinstance(stage_input, EvidenceComparisonStageInput):
        raise TypeError(
            "stage_input must be an EvidenceComparisonStageInput; "
            f"got {type(stage_input)!r}"
        )
    execution_dependencies = stage_input.execution_dependencies
    if not isinstance(
        execution_dependencies,
        ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
    ):
        raise TypeError(
            "clinical-safety aggregate stage requires "
            "ClinicalTrialAggregateEvidenceComparisonExecutionDependencies; "
            f"got {type(execution_dependencies)!r}"
        )

    stage_context = stage_input.context
    resolved_run_id = stage_context.run_id or resolve_evidence_comparison_stage_run_id()
    git_provenance = None
    if stage_context.git_provenance is not None:
        git_provenance = dict(stage_context.git_provenance)
    else:
        git_provenance = snapshot_git_provenance_before_run(
            root=stage_context.output_dir.parent,
        )

    invocation = build_aggregate_evidence_comparison_invocation_from_stage_input(
        stage_input=stage_input,
        source_adapter=source_adapter,
    )
    execution_input = AggregateEvidenceComparisonExecutionInput(
        invocation=invocation,
        assessment_config=execution_dependencies.assessment_config,
        assessment_provider=execution_dependencies.assessment_provider,
        assessment_second_pass_provider=(
            execution_dependencies.assessment_second_pass_provider
        ),
        verification_provider=execution_dependencies.verification_provider,
        consolidation_config=execution_dependencies.consolidation_config,
        consolidation_provider=execution_dependencies.consolidation_provider,
        max_concurrency=execution_dependencies.max_concurrency,
        assessment_llm_execution_config=(
            execution_dependencies.assessment_llm_execution_config
        ),
        assessment_second_pass_llm_execution_config=(
            execution_dependencies.assessment_second_pass_llm_execution_config
        ),
        verification_llm_execution_config=(
            execution_dependencies.verification_llm_execution_config
        ),
        consolidation_llm_execution_config=(
            execution_dependencies.consolidation_llm_execution_config
        ),
    )
    try:
        execution_result = comparison_step.run_evidence_comparison(
            invocation=execution_input,
            executor=evidence_comparison_executor,
        )
    except AggregateEvidenceComparisonFinalizationFailure as exc:
        persist_aggregate_evidence_comparison_pre_final_failure(
            pre_final_state=exc.pre_final_state,
            finalization_error=exc.finalization_error,
            stage_input=stage_input,
            output_dir=stage_context.output_dir,
            run_id=resolved_run_id,
            stage_executor_id=(
                CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID
            ),
            capability_id=execution_dependencies.capability_id,
            git_provenance=git_provenance,
        )
        raise
    if not isinstance(execution_result, AggregateEvidenceComparisonExecution):
        raise TypeError(
            "installed aggregate comparison executor must return "
            "AggregateEvidenceComparisonExecution; "
            f"got {type(execution_result)!r}"
        )

    persist_result = persist_unified_aggregate_evidence_comparison_execution(
        execution=execution_result,
        stage_input=stage_input,
        output_dir=stage_context.output_dir,
        run_id=resolved_run_id,
        stage_executor_id=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID,
        capability_id=execution_dependencies.capability_id,
        git_provenance=git_provenance,
    )

    return EvidenceComparisonStageResult(
        output_dir=persist_result.output_dir,
        run_id=persist_result.run_id,
        stage_executor_id=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID,
        run_status=execution_result.run_status,
        run_summary_path=persist_result.run_summary_path,
        declared_output_path=persist_result.final_findings_path,
    )


def build_clinical_trial_aggregate_evidence_comparison_stage_executor(
    *,
    evidence_comparison_executor: EvidenceComparisonExecutor,
    source_adapter: AggregateEvidenceComparisonSourceAdapter = (
        adapt_clinical_safety_aggregate_source_bundle
    ),
) -> EvidenceComparisonStageExecutor:
    """Bind one installed in-memory executor into the production stage runtime."""

    def _stage_executor(
        *,
        stage_input: EvidenceComparisonStageInput,
    ) -> EvidenceComparisonStageResult:
        return execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=evidence_comparison_executor,
            source_adapter=source_adapter,
        )

    return _stage_executor


__all__ = [
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID",
    "ClinicalTrialAggregateEvidenceComparisonExecutionDependencies",
    "build_aggregate_evidence_comparison_invocation_from_stage_input",
    "build_clinical_trial_aggregate_evidence_comparison_stage_executor",
    "execute_aggregate_evidence_comparison_transport",
    "execute_clinical_trial_aggregate_evidence_comparison_stage",
    "resolve_evidence_comparison_stage_run_id",
]
