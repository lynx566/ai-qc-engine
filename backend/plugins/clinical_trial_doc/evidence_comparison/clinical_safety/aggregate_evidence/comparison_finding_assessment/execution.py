"""In-memory Comparison Finding Assessment batch/job execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from llm.invocation import LLMInvocationRecord, invoke_llm
from llm.providers.base import LLMProvider

from .candidate_eligibility import (
    CandidateEligibilityResult,
    filter_eligible_candidates,
)
from .finding_assembly import (
    assemble_findings_for_jobs,
    build_findings_artifact_from_bundles,
)
from .input_materialization import materialize_comparison_finding_assessment_llm_input
from .job_sentence_aliases import collect_job_allowed_sentence_aliases
from .jobs import ComparisonFindingAssessmentJob
from .prompts import (
    load_formal_prompt_definition,
    render_formal_prompt_messages,
    resolve_formal_prompt_id,
)
from .response_validation import (
    ComparisonFindingAssessmentValidatedResponse,
    parse_and_validate_comparison_finding_assessment_response,
)


def _resolve_batch_run_status(*, success_count: int, total_count: int) -> str:
    if success_count == total_count:
        return "success"
    if success_count == 0:
        return "failed"
    return "partial_failure"


def select_planned_assessment_jobs(
    jobs: Sequence[ComparisonFindingAssessmentJob],
    *,
    frozen_job_index: int | None = None,
    comparison_modes: frozenset[str] | None = None,
    max_jobs: int | None = None,
) -> tuple[tuple[int, ComparisonFindingAssessmentJob], ...]:
    """Select frozen jobs using the same semantics as the standalone runtime."""

    if frozen_job_index is not None:
        if frozen_job_index < 1 or frozen_job_index > len(jobs):
            raise ValueError(
                f"frozen_job_index must be between 1 and {len(jobs)}, "
                f"got {frozen_job_index}"
            )
        job = jobs[frozen_job_index - 1]
        return ((frozen_job_index, job),)

    selected: list[tuple[int, ComparisonFindingAssessmentJob]] = []
    for index, job in enumerate(jobs, start=1):
        if comparison_modes is not None and job.comparison_mode_id not in comparison_modes:
            continue
        selected.append((index, job))
        if max_jobs is not None and len(selected) >= max_jobs:
            break
    return tuple(selected)


def validate_assessment_job_selector(
    *,
    frozen_job_index: int | None,
    comparison_modes: Sequence[str] | None,
    max_jobs: int | None,
) -> None:
    subset_active = comparison_modes is not None or max_jobs is not None
    if frozen_job_index is not None and subset_active:
        raise ValueError(
            "frozen_job_index cannot be combined with comparison_modes or max_jobs"
        )


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentJobExecution:
    """Semantic outcome for one Assessment job execution."""

    frozen_job_index: int
    execution_index: int
    job: ComparisonFindingAssessmentJob
    status: str
    prompt_id: str
    prompt_version: str
    parse_status: str
    validation_status: str
    validated_response: ComparisonFindingAssessmentValidatedResponse | None = None
    accepted_response: ComparisonFindingAssessmentValidatedResponse | None = None
    eligibility: CandidateEligibilityResult | None = None
    candidate_count: int = 0
    accepted_candidate_count: int = 0
    dropped_candidate_count: int = 0
    finding_count: int = 0
    error_message: str | None = None
    messages: tuple[dict[str, str], ...] | None = None
    raw_response_text: str | None = None
    llm_invocations: tuple[LLMInvocationRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentExecution:
    """Semantic outcome for one Assessment batch execution."""

    job_executions: tuple[ComparisonFindingAssessmentJobExecution, ...]
    run_status: str
    success_count: int
    failed_count: int
    findings_artifact: dict[str, Any] | None
    finding_count: int


def execute_comparison_finding_assessment_job(
    *,
    frozen_job_index: int,
    execution_index: int,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
    provider: LLMProvider,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> ComparisonFindingAssessmentJobExecution:
    """Execute one Comparison Finding Assessment job in memory."""

    prompt_id = resolve_formal_prompt_id(job.comparison_mode_id)
    formal_prompt = load_formal_prompt_definition(prompt_id)
    evidence_input = materialize_comparison_finding_assessment_llm_input(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    collect_job_allowed_sentence_aliases(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    messages = render_formal_prompt_messages(
        prompt_id=prompt_id,
        evidence_input=evidence_input,
    )
    message_tuple = tuple(messages)

    outcome = invoke_llm(
        provider,
        messages,
        execution_config=llm_execution_config,
        attempt_index=1,
    )
    if outcome.error is not None:
        return ComparisonFindingAssessmentJobExecution(
            frozen_job_index=frozen_job_index,
            execution_index=execution_index,
            job=job,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            parse_status="not_attempted",
            validation_status="not_attempted",
            error_message=str(outcome.error),
            messages=message_tuple,
            llm_invocations=outcome.invocations,
        )

    raw_result = outcome.unwrap()

    try:
        validated = parse_and_validate_comparison_finding_assessment_response(
            raw_result.raw_text,
        )
    except ValueError as exc:
        return ComparisonFindingAssessmentJobExecution(
            frozen_job_index=frozen_job_index,
            execution_index=execution_index,
            job=job,
            status="failed",
            prompt_id=formal_prompt.prompt_id,
            prompt_version=formal_prompt.version,
            parse_status="failed",
            validation_status="not_attempted",
            candidate_count=0,
            error_message=str(exc),
            messages=message_tuple,
            raw_response_text=raw_result.raw_text,
            llm_invocations=outcome.invocations,
        )

    eligibility = filter_eligible_candidates(
        validated,
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    accepted_candidate_count = eligibility.accepted_candidate_count
    dropped_candidate_count = eligibility.dropped_candidate_count
    return ComparisonFindingAssessmentJobExecution(
        frozen_job_index=frozen_job_index,
        execution_index=execution_index,
        job=job,
        status="success",
        prompt_id=formal_prompt.prompt_id,
        prompt_version=formal_prompt.version,
        parse_status="success",
        validation_status="success",
        validated_response=validated,
        accepted_response=eligibility.accepted_response,
        eligibility=eligibility,
        candidate_count=len(validated.candidates),
        accepted_candidate_count=accepted_candidate_count,
        dropped_candidate_count=dropped_candidate_count,
        finding_count=accepted_candidate_count,
        messages=message_tuple,
        raw_response_text=raw_result.raw_text,
        llm_invocations=outcome.invocations,
    )


def execute_comparison_finding_assessment_jobs(
    *,
    selected_jobs: Sequence[tuple[int, ComparisonFindingAssessmentJob]],
    aggregate_comparison_evidence: Mapping[str, Any],
    provider: LLMProvider,
    max_concurrency: int | None = None,
    llm_execution_config: Mapping[str, Any] | None = None,
) -> ComparisonFindingAssessmentExecution:
    """Execute selected Assessment jobs and assemble findings in frozen-job order."""

    if not selected_jobs:
        raise ValueError("selected_jobs must contain at least one job")

    effective_concurrency = (
        len(selected_jobs)
        if max_concurrency is None
        else min(max_concurrency, len(selected_jobs))
    )

    with ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
        futures = tuple(
            executor.submit(
                execute_comparison_finding_assessment_job,
                frozen_job_index=frozen_job_index,
                execution_index=execution_index,
                job=job,
                aggregate_comparison_evidence=aggregate_comparison_evidence,
                provider=provider,
                llm_execution_config=llm_execution_config,
            )
            for execution_index, (frozen_job_index, job) in enumerate(
                selected_jobs,
                start=1,
            )
        )
        job_executions = tuple(future.result() for future in futures)

    assembly_inputs: list[
        tuple[int, ComparisonFindingAssessmentJob, ComparisonFindingAssessmentValidatedResponse]
    ] = []
    for (frozen_job_index, job), execution in zip(
        selected_jobs,
        job_executions,
        strict=True,
    ):
        if execution.status != "success" or execution.accepted_response is None:
            continue
        assembly_inputs.append((frozen_job_index, job, execution.accepted_response))

    findings_artifact: dict[str, Any] | None = None
    finding_count = 0
    if assembly_inputs:
        bundles = assemble_findings_for_jobs(assembly_inputs)
        findings_artifact = build_findings_artifact_from_bundles(bundles)
        finding_count = sum(len(bundle.findings) for bundle in bundles)

    success_count = sum(1 for execution in job_executions if execution.status == "success")
    run_status = _resolve_batch_run_status(
        success_count=success_count,
        total_count=len(job_executions),
    )
    return ComparisonFindingAssessmentExecution(
        job_executions=job_executions,
        run_status=run_status,
        success_count=success_count,
        failed_count=len(job_executions) - success_count,
        findings_artifact=findings_artifact,
        finding_count=finding_count,
    )


__all__ = [
    "ComparisonFindingAssessmentExecution",
    "ComparisonFindingAssessmentJobExecution",
    "execute_comparison_finding_assessment_job",
    "execute_comparison_finding_assessment_jobs",
    "select_planned_assessment_jobs",
    "validate_assessment_job_selector",
]
