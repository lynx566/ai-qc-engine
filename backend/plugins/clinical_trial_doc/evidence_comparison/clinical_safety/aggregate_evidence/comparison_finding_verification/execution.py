"""In-memory Comparison Finding Verification batch/job execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from llm.invocation import LLMInvocationRecord, invoke_llm
from llm.providers.base import LLMProvider

from ..comparison_finding_assessment.jobs import ComparisonFindingAssessmentJob
from .additional_finding_eligibility import (
    AdditionalFindingEligibilityResult,
    filter_eligible_additional_findings,
)
from .finding_reconciliation import (
    ComparisonFindingVerificationJobReconciliationResult,
    assemble_verified_findings_artifact,
    reconcile_verification_job,
)
from .input_materialization import ComparisonFindingVerificationInput
from .prompts import (
    load_formal_prompt_definition,
    render_formal_prompt_messages,
    resolve_formal_prompt_id,
)
from .response_validation import (
    ComparisonFindingVerificationValidatedResponse,
    parse_and_validate_comparison_finding_verification_response,
)


def _resolve_batch_run_status(*, success_count: int, total_count: int) -> str:
    if success_count == total_count:
        return "success"
    if success_count == 0:
        return "failed"
    return "partial_failure"


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationJobExecution:
    """Semantic outcome for one Verification job execution."""

    frozen_job_index: int
    execution_index: int
    comparison_mode_id: str
    status: str
    prompt_id: str
    prompt_version: str
    parse_status: str
    validation_status: str
    verification_input: ComparisonFindingVerificationInput
    validated_response: ComparisonFindingVerificationValidatedResponse | None = None
    job_reconciliation: ComparisonFindingVerificationJobReconciliationResult | None = None
    additional_eligibility: AdditionalFindingEligibilityResult | None = None
    input_finding_count: int = 0
    finding_verification_count: int = 0
    additional_finding_count: int = 0
    confirmed_finding_count: int = 0
    revised_finding_count: int = 0
    rejected_finding_count: int = 0
    received_additional_finding_count: int = 0
    accepted_additional_finding_count: int = 0
    dropped_additional_finding_count: int = 0
    adopted_finding_count: int = 0
    error_message: str | None = None
    messages: tuple[dict[str, str], ...] | None = None
    raw_response_text: str | None = None
    llm_invocations: tuple[LLMInvocationRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationExecution:
    """Semantic outcome for one Verification batch execution."""

    job_executions: tuple[ComparisonFindingVerificationJobExecution, ...]
    run_status: str
    success_count: int
    failed_count: int
    findings_artifact: dict[str, Any] | None
    adopted_finding_count: int


def execute_comparison_finding_verification_job(
    *,
    verification_input: ComparisonFindingVerificationInput,
    frozen_job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
    execution_index: int,
    provider: LLMProvider,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> ComparisonFindingVerificationJobExecution:
    """Execute one Comparison Finding Verification job in memory."""

    prompt_id = resolve_formal_prompt_id(verification_input.comparison_mode_id)
    formal_prompt = load_formal_prompt_definition(prompt_id)
    input_finding_ids = tuple(
        str(finding["finding_id"]) for finding in verification_input.findings
    )
    messages = render_formal_prompt_messages(
        prompt_id=prompt_id,
        verification_input_text=verification_input.user_input_text,
    )
    message_tuple = tuple(messages)

    outcome = invoke_llm(
        provider,
        messages,
        execution_config=llm_execution_config,
        attempt_index=1,
    )
    if outcome.error is not None:
        return ComparisonFindingVerificationJobExecution(
            frozen_job_index=verification_input.frozen_job_index,
            execution_index=execution_index,
            comparison_mode_id=verification_input.comparison_mode_id,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            parse_status="not_attempted",
            validation_status="not_attempted",
            verification_input=verification_input,
            input_finding_count=len(input_finding_ids),
            error_message=str(outcome.error),
            messages=message_tuple,
            llm_invocations=outcome.invocations,
        )

    raw_result = outcome.unwrap()

    try:
        validated = parse_and_validate_comparison_finding_verification_response(
            raw_result.raw_text,
            input_finding_ids=input_finding_ids,
        )
    except ValueError as exc:
        return ComparisonFindingVerificationJobExecution(
            frozen_job_index=verification_input.frozen_job_index,
            execution_index=execution_index,
            comparison_mode_id=verification_input.comparison_mode_id,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            parse_status="failed",
            validation_status="not_attempted",
            verification_input=verification_input,
            input_finding_count=len(input_finding_ids),
            error_message=str(exc),
            messages=message_tuple,
            raw_response_text=raw_result.raw_text,
            llm_invocations=outcome.invocations,
        )

    additional_eligibility = filter_eligible_additional_findings(
        validated.additional_findings,
        job=frozen_job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    job_reconciliation = reconcile_verification_job(
        frozen_job_index=verification_input.frozen_job_index,
        job=frozen_job,
        original_findings=verification_input.findings,
        validated_response=validated,
        additional_eligibility=additional_eligibility,
    )
    return ComparisonFindingVerificationJobExecution(
        frozen_job_index=verification_input.frozen_job_index,
        execution_index=execution_index,
        comparison_mode_id=verification_input.comparison_mode_id,
        status="success",
        prompt_id=formal_prompt.prompt_id,
        prompt_version=formal_prompt.version,
        parse_status="success",
        validation_status="success",
        verification_input=verification_input,
        validated_response=validated,
        job_reconciliation=job_reconciliation,
        additional_eligibility=additional_eligibility,
        input_finding_count=len(input_finding_ids),
        finding_verification_count=len(validated.finding_verifications),
        additional_finding_count=len(validated.additional_findings),
        confirmed_finding_count=job_reconciliation.confirmed_finding_count,
        revised_finding_count=job_reconciliation.revised_finding_count,
        rejected_finding_count=job_reconciliation.rejected_finding_count,
        received_additional_finding_count=(
            additional_eligibility.received_additional_finding_count
        ),
        accepted_additional_finding_count=(
            additional_eligibility.accepted_additional_finding_count
        ),
        dropped_additional_finding_count=(
            additional_eligibility.dropped_additional_finding_count
        ),
        messages=message_tuple,
        raw_response_text=raw_result.raw_text,
        llm_invocations=outcome.invocations,
    )


def execute_comparison_finding_verification_jobs(
    *,
    verification_inputs: Sequence[ComparisonFindingVerificationInput],
    planned_jobs_by_index: Mapping[int, ComparisonFindingAssessmentJob],
    aggregate_comparison_evidence: Mapping[str, Any],
    assessment_findings_artifact: Mapping[str, Any],
    provider: LLMProvider,
    max_concurrency: int | None = None,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> ComparisonFindingVerificationExecution:
    """Execute Verification jobs and assemble post-verification findings."""

    if not verification_inputs:
        raise ValueError("verification_inputs must contain at least one job")

    effective_concurrency = (
        len(verification_inputs)
        if max_concurrency is None
        else min(max_concurrency, len(verification_inputs))
    )

    with ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
        futures = tuple(
            executor.submit(
                execute_comparison_finding_verification_job,
                verification_input=verification_input,
                frozen_job=planned_jobs_by_index[verification_input.frozen_job_index],
                aggregate_comparison_evidence=aggregate_comparison_evidence,
                execution_index=execution_index,
                provider=provider,
                llm_execution_config=llm_execution_config,
            )
            for execution_index, verification_input in enumerate(
                verification_inputs,
                start=1,
            )
        )
        job_executions = tuple(future.result() for future in futures)

    reconciliation_pairs = [
        (execution.job_reconciliation, execution.additional_eligibility)
        for execution in job_executions
        if execution.status == "success"
        and execution.job_reconciliation is not None
        and execution.additional_eligibility is not None
    ]

    findings_artifact: dict[str, Any] | None = None
    adopted_finding_count = 0
    if reconciliation_pairs:
        assembly = assemble_verified_findings_artifact(
            assessment_findings_artifact=assessment_findings_artifact,
            job_reconciliations=reconciliation_pairs,
        )
        findings_artifact = assembly.findings_artifact
        adopted_finding_count = assembly.adopted_finding_count
        adopted_count_by_index = {
            job_result.frozen_job_index: len(job_result.findings)
            for job_result in assembly.job_results
        }
        job_executions = tuple(
            ComparisonFindingVerificationJobExecution(
                frozen_job_index=execution.frozen_job_index,
                execution_index=execution.execution_index,
                comparison_mode_id=execution.comparison_mode_id,
                status=execution.status,
                prompt_id=execution.prompt_id,
                prompt_version=execution.prompt_version,
                parse_status=execution.parse_status,
                validation_status=execution.validation_status,
                verification_input=execution.verification_input,
                validated_response=execution.validated_response,
                job_reconciliation=execution.job_reconciliation,
                additional_eligibility=execution.additional_eligibility,
                input_finding_count=execution.input_finding_count,
                finding_verification_count=execution.finding_verification_count,
                additional_finding_count=execution.additional_finding_count,
                confirmed_finding_count=execution.confirmed_finding_count,
                revised_finding_count=execution.revised_finding_count,
                rejected_finding_count=execution.rejected_finding_count,
                received_additional_finding_count=execution.received_additional_finding_count,
                accepted_additional_finding_count=execution.accepted_additional_finding_count,
                dropped_additional_finding_count=execution.dropped_additional_finding_count,
                adopted_finding_count=adopted_count_by_index.get(
                    execution.frozen_job_index,
                    0,
                ),
                error_message=execution.error_message,
                messages=execution.messages,
                raw_response_text=execution.raw_response_text,
                llm_invocations=execution.llm_invocations,
            )
            for execution in job_executions
        )

    success_count = sum(1 for execution in job_executions if execution.status == "success")
    run_status = _resolve_batch_run_status(
        success_count=success_count,
        total_count=len(job_executions),
    )
    return ComparisonFindingVerificationExecution(
        job_executions=job_executions,
        run_status=run_status,
        success_count=success_count,
        failed_count=len(job_executions) - success_count,
        findings_artifact=findings_artifact,
        adopted_finding_count=adopted_finding_count,
    )


__all__ = [
    "ComparisonFindingVerificationExecution",
    "ComparisonFindingVerificationJobExecution",
    "execute_comparison_finding_verification_job",
    "execute_comparison_finding_verification_jobs",
]
