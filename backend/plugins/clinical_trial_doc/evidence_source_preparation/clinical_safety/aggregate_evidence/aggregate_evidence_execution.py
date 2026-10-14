"""Fixed four-phase aggregate-evidence execution orchestration (no I/O)."""

from __future__ import annotations

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import ASSESSMENT_INPUT_FILENAME
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import ASSESSMENT_RUNTIME_CONTEXT_FILENAME
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    build_in_memory_source_scope_assessments_ref,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
    run_aggregate_evidence_evaluate_heading_scope_eligibility,
    run_aggregate_evidence_prepare,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assemble_aggregate_evidence_source_bundle import (
    assemble_aggregate_evidence_source_bundle,
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


def run_aggregate_evidence_execution(
    *,
    execution_input: AggregateEvidenceExecutionInput,
    semantic_binding: AggregateEvidenceSemanticBinding,
) -> AggregateEvidenceExecution:
    """Run prepare → assess → eligibility → assemble using stable phase APIs."""
    prepare_execution = run_aggregate_evidence_prepare(
        upstream=execution_input.upstream,
        route_artifacts=execution_input.route_artifacts,
        evidence_form_id=execution_input.evidence_form_id,
        prepare_semantic=semantic_binding.prepare,
    )
    assessment_input = prepare_execution.assessment_input
    assessment_runtime_context = prepare_execution.assessment_runtime_context

    profile_name = execution_input.assessment_profile_name
    if profile_name is None:
        profile_ref = assessment_input.get("assessment_profile_ref")
        if not profile_ref:
            raise ValueError(
                "assessment_input missing assessment_profile_ref; "
                "pass assessment_profile_name"
            )
        profile_name = str(profile_ref)

    assess_execution = run_aggregate_evidence_assess_heading_scopes(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        assessment_profile_name=profile_name,
        llm_mode=execution_input.llm_mode,
        llm_profile=execution_input.llm_profile,
        provider=execution_input.provider,
        llm_execution_config=execution_input.llm_execution_config,
        assessment_input_ref=ASSESSMENT_INPUT_FILENAME,
        assessment_runtime_context_ref=ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
        allow_api_parse_fallback=execution_input.allow_api_parse_fallback,
    )
    scope_assessments = assess_execution.scope_assessments
    source_scope_assessments_ref = build_in_memory_source_scope_assessments_ref(
        scope_assessments_payload=scope_assessments,
    )
    eligibility_execution = run_aggregate_evidence_evaluate_heading_scope_eligibility(
        scope_assessments=scope_assessments,
        source_scope_assessments_ref=source_scope_assessments_ref,
        build_heading_scope_eligibility_entries=(
            semantic_binding.build_heading_scope_eligibility_entries
        ),
    )
    assemble_execution = assemble_aggregate_evidence_source_bundle(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=eligibility_execution.heading_scope_eligibility,
    )
    return AggregateEvidenceExecution(
        prepare=prepare_execution,
        assess=assess_execution,
        eligibility=eligibility_execution,
        assemble=assemble_execution,
    )


__all__ = ["run_aggregate_evidence_execution"]
