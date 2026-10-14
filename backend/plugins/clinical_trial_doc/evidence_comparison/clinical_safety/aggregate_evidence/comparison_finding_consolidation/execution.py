"""Generic in-memory Comparison Finding Consolidation execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from llm.invocation import LLMInvocationRecord, invoke_llm
from llm.providers.base import LLMProvider

from .alias_qc import (
    ComparisonFindingConsolidationAliasQcResult,
    compute_comparison_finding_consolidation_alias_qc,
)
from .input_materialization import ComparisonFindingConsolidationInput
from .prompts import (
    load_formal_prompt_definition,
    render_formal_prompt_messages,
    resolve_formal_prompt_id,
)
from .response_validation import (
    ComparisonFindingConsolidationParseError,
    ComparisonFindingConsolidationValidatedResponse,
    ComparisonFindingConsolidationValidationError,
    parse_comparison_finding_consolidation_response,
    validate_comparison_finding_consolidation_response_structure,
)


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationExecution:
    """Outcome for one configured comparison mode's consolidation phase."""

    comparison_mode_id: str
    status: str
    prompt_id: str
    prompt_version: str
    provider_called: bool
    parse_status: str
    validation_status: str
    consolidation_input: ComparisonFindingConsolidationInput
    validated_response: ComparisonFindingConsolidationValidatedResponse | None = None
    alias_qc: ComparisonFindingConsolidationAliasQcResult | None = None
    finding_count: int = 0
    group_count: int = 0
    error_message: str | None = None
    messages: tuple[dict[str, str], ...] | None = None
    raw_response_text: str | None = None
    llm_invocations: tuple[LLMInvocationRecord, ...] = ()


def execute_comparison_finding_consolidation(
    *,
    consolidation_input: ComparisonFindingConsolidationInput,
    provider: LLMProvider,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> ComparisonFindingConsolidationExecution:
    """Execute one materialized consolidation request without mode-specific logic."""

    if not isinstance(consolidation_input, ComparisonFindingConsolidationInput):
        raise TypeError(
            "consolidation_input must be a ComparisonFindingConsolidationInput"
        )
    prompt_id = resolve_formal_prompt_id(
        consolidation_input.comparison_mode_id  # type: ignore[arg-type]
    )
    formal_prompt = load_formal_prompt_definition(prompt_id)
    messages = render_formal_prompt_messages(
        prompt_id=prompt_id,
        consolidation_input_text=consolidation_input.user_input_text,
    )
    message_tuple = tuple(messages)

    if consolidation_input.finding_count < 2:
        validated = ComparisonFindingConsolidationValidatedResponse(
            consolidated_groups=()
        )
        alias_qc = compute_comparison_finding_consolidation_alias_qc(
            finding_projections=consolidation_input.finding_projections,
            validated_response=validated,
        )
        return ComparisonFindingConsolidationExecution(
            comparison_mode_id=consolidation_input.comparison_mode_id,
            status="success",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            provider_called=False,
            parse_status="not_attempted",
            validation_status="not_attempted",
            consolidation_input=consolidation_input,
            validated_response=validated,
            alias_qc=alias_qc,
            finding_count=consolidation_input.finding_count,
            group_count=0,
            messages=message_tuple,
        )

    outcome = invoke_llm(
        provider,
        messages,
        execution_config=llm_execution_config,
        attempt_index=1,
    )
    if outcome.error is not None:
        return ComparisonFindingConsolidationExecution(
            comparison_mode_id=consolidation_input.comparison_mode_id,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            provider_called=True,
            parse_status="not_attempted",
            validation_status="not_attempted",
            consolidation_input=consolidation_input,
            finding_count=consolidation_input.finding_count,
            error_message=str(outcome.error),
            messages=message_tuple,
            llm_invocations=outcome.invocations,
        )

    raw_result = outcome.unwrap()
    try:
        parsed = parse_comparison_finding_consolidation_response(raw_result.raw_text)
    except ComparisonFindingConsolidationParseError as exc:
        return ComparisonFindingConsolidationExecution(
            comparison_mode_id=consolidation_input.comparison_mode_id,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            provider_called=True,
            parse_status="failed",
            validation_status="not_attempted",
            consolidation_input=consolidation_input,
            finding_count=consolidation_input.finding_count,
            error_message=str(exc),
            messages=message_tuple,
            raw_response_text=raw_result.raw_text,
            llm_invocations=outcome.invocations,
        )

    try:
        validated = validate_comparison_finding_consolidation_response_structure(
            parsed,
            input_conclusion_aliases=tuple(
                projection.conclusion_alias
                for projection in consolidation_input.finding_projections
            ),
        )
    except ComparisonFindingConsolidationValidationError as exc:
        return ComparisonFindingConsolidationExecution(
            comparison_mode_id=consolidation_input.comparison_mode_id,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            provider_called=True,
            parse_status="success",
            validation_status="failed",
            consolidation_input=consolidation_input,
            finding_count=consolidation_input.finding_count,
            error_message=str(exc),
            messages=message_tuple,
            raw_response_text=raw_result.raw_text,
            llm_invocations=outcome.invocations,
        )

    alias_qc = compute_comparison_finding_consolidation_alias_qc(
        finding_projections=consolidation_input.finding_projections,
        validated_response=validated,
    )
    return ComparisonFindingConsolidationExecution(
        comparison_mode_id=consolidation_input.comparison_mode_id,
        status="success",
        prompt_id=formal_prompt.prompt_id,
        prompt_version=formal_prompt.version,
        provider_called=True,
        parse_status="success",
        validation_status="success",
        consolidation_input=consolidation_input,
        validated_response=validated,
        alias_qc=alias_qc,
        finding_count=consolidation_input.finding_count,
        group_count=len(validated.consolidated_groups),
        messages=message_tuple,
        raw_response_text=raw_result.raw_text,
        llm_invocations=outcome.invocations,
    )


__all__ = [
    "ComparisonFindingConsolidationExecution",
    "execute_comparison_finding_consolidation",
]
