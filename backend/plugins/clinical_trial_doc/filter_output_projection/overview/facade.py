"""Overview semantic decomposition Filter-output projection facade."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from llm.invocation import attach_llm_invocations, invoke_llm
from llm.providers.base import LLMProvider
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ResolvedFilterOutputProjectionJob,
)

from plugins.clinical_trial_doc.filter_output_projection.overview.assembly import (
    assemble_overview_projection_result,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.prompt import (
    build_overview_assessment_messages,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.response import (
    parse_overview_assessment_response,
    validate_and_canonicalize_assessments,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.source_items import (
    build_overview_prompt_input_json,
    prepare_overview_source_items,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.vocabulary import (
    BUSINESS_CONTENT_MODULES,
)
from plugins.clinical_trial_doc.filter_output_projection.strategy_ids import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)

OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY = "target_semantic_module_id"


def _validate_strategy_identity(job: ResolvedFilterOutputProjectionJob) -> None:
    if job.strategy_id != OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID:
        raise ValueError(
            "overview semantic decomposition projection requires "
            f"strategy_id={OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID!r}"
        )


def _require_target_semantic_module_id(job: ResolvedFilterOutputProjectionJob) -> str:
    value = job.strategy_config.get(OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY)
    target = str(value or "").strip()
    if target not in BUSINESS_CONTENT_MODULES:
        raise ValueError(
            "overview semantic decomposition projection requires a supported "
            f"{OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY!r}"
        )
    return target


def project_overview_semantic_decomposition(
    *,
    projection_input: FilterOutputProjectionInput,
    job: ResolvedFilterOutputProjectionJob,
    llm_provider: LLMProvider,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> FilterOutputProjectionStepResult:
    """Run Overview assessment and assemble semantic projection output."""

    _validate_strategy_identity(job)
    target_semantic_module_id = _require_target_semantic_module_id(job)
    prepared = prepare_overview_source_items(projection_input.projection_sources)
    if not prepared.items:
        return FilterOutputProjectionStepResult(
            filter_job_id=projection_input.filter_job_id,
            doc_id=projection_input.doc_id,
            file_hash=projection_input.file_hash,
            zone_key=projection_input.zone_key,
            projected_sources=(),
            semantic_outcomes=(),
        )

    messages = build_overview_assessment_messages(
        input_json=build_overview_prompt_input_json(prepared),
    )
    outcome = invoke_llm(
        llm_provider,
        messages,
        execution_config=llm_execution_config,
        attempt_index=1,
    )
    raw_result = outcome.unwrap()
    try:
        if not isinstance(raw_result.raw_text, str) or not raw_result.raw_text.strip():
            raise ValueError("overview assessment provider returned empty response")

        parsed = parse_overview_assessment_response(raw_result.raw_text)
        assessments = validate_and_canonicalize_assessments(parsed, prepared)
        result = assemble_overview_projection_result(
            projection_input=projection_input,
            prepared=prepared,
            assessments=assessments,
            target_semantic_module_id=target_semantic_module_id,
        )
    except Exception as error:
        attach_llm_invocations(error, outcome.invocations)
        raise
    return replace(result, llm_invocations=outcome.invocations)


@dataclass(frozen=True, slots=True)
class OverviewSemanticDecompositionProjectionFacade:
    """Production facade for Overview semantic decomposition projection."""

    llm_provider: LLMProvider
    llm_execution_config: Mapping[str, Any] | None = None

    def project(
        self,
        *,
        projection_input: FilterOutputProjectionInput,
        job: ResolvedFilterOutputProjectionJob,
    ) -> FilterOutputProjectionStepResult:
        return project_overview_semantic_decomposition(
            projection_input=projection_input,
            job=job,
            llm_provider=self.llm_provider,
            llm_execution_config=self.llm_execution_config,
        )


def build_overview_semantic_decomposition_facade(
    *,
    llm_provider: LLMProvider,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> OverviewSemanticDecompositionProjectionFacade:
    """Construct the Overview projection facade with an injected provider."""

    return OverviewSemanticDecompositionProjectionFacade(
        llm_provider=llm_provider,
        llm_execution_config=llm_execution_config,
    )


__all__ = [
    "OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY",
    "OverviewSemanticDecompositionProjectionFacade",
    "build_overview_semantic_decomposition_facade",
    "project_overview_semantic_decomposition",
]
