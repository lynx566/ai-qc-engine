"""Aggregate Evidence assess orchestration."""

from __future__ import annotations

from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    validate_assessment_runtime_context,
    validate_scoped_assessment_cross_artifacts,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
    validate_assessment_input,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from llm.providers.base import LLMProvider

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    build_scope_aware_prompt_input,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import (
    run_aggregate_evidence_scope_assess,
)


def _validate_assess_inputs(
    assessment_input: dict[str, Any],
    *,
    assessment_runtime_context: dict[str, Any],
) -> None:
    validate_assessment_input(assessment_input)
    if assessment_input.get("stage") != EVIDENCE_SOURCE_PREPARATION_STAGE:
        raise ValueError(
            "assessment_input.stage must be 'evidence_source_preparation'"
        )
    if assessment_input.get("phase") != EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE:
        raise ValueError("assessment_input.phase must be 'prepare'")

    validate_assessment_runtime_context(assessment_runtime_context)
    validate_scoped_assessment_cross_artifacts(
        assessment_input,
        assessment_runtime_context,
    )

def run_aggregate_evidence_assess(
    assessment_input: dict[str, Any],
    *,
    assessment_profile_name: str,
    llm_mode: str = "mock",
    llm_profile: str | None = None,
    provider: LLMProvider | None = None,
    llm_execution_config: dict[str, Any] | None = None,
    assessment_input_path: str | None = None,
    allow_api_parse_fallback: bool = False,
    assessment_runtime_context: dict[str, Any] | None = None,
    assessment_runtime_context_path: str | None = None,
) -> dict[str, Any]:
    """
    Plugin boundary for Aggregate Evidence assess.

    Emits heading-scope planning hints (scope_assessments.json), not per-TU tags.
    """
    if assessment_runtime_context is None:
        raise ValueError("assessment_runtime_context is required for compact assessment_input")

    _validate_assess_inputs(
        assessment_input,
        assessment_runtime_context=assessment_runtime_context,
    )
    llm_input = build_scope_aware_prompt_input(
        assessment_input,
        assessment_runtime_context,
    )
    prompt_input_bundle = llm_input.prompt_input_bundle

    scope_result = run_aggregate_evidence_scope_assess(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        prompt_input_bundle=prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name=assessment_profile_name,
        llm_mode=llm_mode,
        llm_profile=llm_profile,
        provider=provider,
        llm_execution_config=llm_execution_config,
        allow_api_parse_fallback=allow_api_parse_fallback,
        assessment_input_path=assessment_input_path,
        assessment_runtime_context_path=assessment_runtime_context_path,
    )

    return {
        "scope_assessments": scope_result["scope_assessments"],
        "scope_assessment_trace": scope_result.get("scope_assessment_trace"),
        "assessment_profile_name": scope_result.get("assessment_profile_name"),
        "prompt_name": scope_result.get("prompt_name"),
        "prompt_version": scope_result.get("prompt_version"),
        "llm_mode": scope_result.get("llm_mode"),
        "llm_profile": scope_result.get("llm_profile"),
        "run_status": scope_result.get("run_status", "success"),
        "llm_debug_artifacts": scope_result.get("llm_debug_artifacts"),
        "llm_invocations": scope_result.get("llm_invocations", ()),
        "llm_input_payload": prompt_input_bundle,
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    }
