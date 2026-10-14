"""Clinical-trial aggregate Evidence Source Preparation executor."""

from __future__ import annotations

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    validate_aggregate_evidence_source_bundle,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
    validate_aggregate_evidence_prepare_assessment_artifacts,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    validate_heading_scope_eligibility,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import validate_aggregate_evidence_prepare_route_artifacts
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import validate_scope_assessments_envelope
from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationExecutor,
    EvidenceSourcePreparationInvocation,
    EvidenceSourcePreparationResult,
)
from operations.evidence_source_preparation.coverage_resolution import (
    is_projected_multi_source_fan_in,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.aggregate_evidence_execution import (
    run_aggregate_evidence_execution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidenceSemanticBinding,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceExecution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceExecutionInput,
)


def _invocation_uses_projected_fan_in(
    invocation: AggregateEvidenceExecutionInput,
) -> bool:
    upstream = invocation.upstream
    projected = upstream.projected_coverage_by_filter_job
    if projected is None:
        return False
    distinct_count = len(
        {
            str(bundle.get("coverage_bundle_id") or "")
            for bundle in projected.bundles_by_filter_job_id.values()
        }
    )
    return is_projected_multi_source_fan_in(
        aggregate_bundle=invocation.route_artifacts.aggregate_bundle,
        projection_input_refs=upstream.projection_input_refs,
        distinct_coverage_count=distinct_count,
    )


def execute_clinical_trial_aggregate_evidence_source_preparation(
    *,
    invocation: EvidenceSourcePreparationInvocation,
    semantic_binding: AggregateEvidenceSemanticBinding = (
        CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING
    ),
) -> EvidenceSourcePreparationResult:
    """Bridge neutral ESP invocation to configured aggregate four-phase execution."""
    if not isinstance(invocation, AggregateEvidenceExecutionInput):
        raise TypeError(
            "clinical-trial aggregate executor requires AggregateEvidenceExecutionInput; "
            f"got {type(invocation)!r}"
        )
    validate_aggregate_evidence_prepare_route_artifacts(
        aggregate_bundle=invocation.route_artifacts.aggregate_bundle,
        routing_manifest=invocation.route_artifacts.routing_manifest,
        projected_fan_in=_invocation_uses_projected_fan_in(invocation),
    )
    execution = run_aggregate_evidence_execution(
        execution_input=invocation,
        semantic_binding=semantic_binding,
    )
    if not isinstance(execution, AggregateEvidenceExecution):
        raise TypeError(
            "run_aggregate_evidence_execution must return AggregateEvidenceExecution; "
            f"got {type(execution)!r}"
        )
    validate_aggregate_evidence_prepare_assessment_artifacts(
        execution.prepare.assessment_input,
        execution.prepare.assessment_runtime_context,
    )
    validate_scope_assessments_envelope(execution.assess.scope_assessments)
    validate_heading_scope_eligibility(
        execution.eligibility.heading_scope_eligibility,
        source_scope_assessments_payload=execution.assess.scope_assessments,
    )
    validate_aggregate_evidence_source_bundle(
        execution.aggregate_evidence_source_bundle
    )
    return execution


CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR: (
    EvidenceSourcePreparationExecutor
) = execute_clinical_trial_aggregate_evidence_source_preparation

__all__ = [
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR",
    "execute_clinical_trial_aggregate_evidence_source_preparation",
]
