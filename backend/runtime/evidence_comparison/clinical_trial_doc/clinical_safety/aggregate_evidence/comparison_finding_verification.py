"""Standalone dev runtime for Comparison Finding Verification LLM execution."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDINGS_FILENAME,
)
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from llm.execution_metadata import llm_effective_execution_fields
from llm.invocation import serialize_llm_invocations
from llm.providers.base import LLMProvider
from llm.providers.factory import build_api_provider
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification.execution import (
    execute_comparison_finding_verification_jobs,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_PHASE,
    resolve_comparison_finding_assessment_execution_handoff,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    resolve_comparison_finding_assessment_plan_handoff,
    verify_participant_provenance,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_handoff import (
    materialize_comparison_finding_verification_inputs_from_assessment_run,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_persistence import (
    VALIDATED_RESPONSE_FILENAME,
    VERIFICATION_INPUT_FILENAME,
    persist_comparison_finding_verification_job_execution,
)
from runtime.io import load_json, save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import (
    resolve_unique_session_dir,
    sanitize_run_segment,
    utc_now_iso,
)
from runtime.run_provenance import snapshot_git_provenance_before_run

EVIDENCE_COMPARISON_STAGE = "evidence_comparison"
CLINICAL_SAFETY_EVIDENCE_SCOPE = "clinical_safety"
AGGREGATE_COMPARISON_SPECIALIZATION = "aggregate"
COMPARISON_FINDING_VERIFICATION_PHASE = "comparison_finding_verification"
COMPARISON_FINDING_VERIFICATION_RUN_DIR_LAYOUT = (
    "stage/evidence_scope/specialization/phase/run_id"
)
COMPARISON_FINDING_VERIFICATION_OPERATION = (
    "aggregate_evidence.execute_comparison_finding_verification"
)
COMPARISON_FINDING_VERIFICATION_JOBS_DIRNAME = "jobs"
RUN_SUMMARY_FILENAME = "run_summary.json"
DEFAULT_LLM_SEED = 1234


@dataclass(frozen=True)
class ComparisonFindingVerificationJobExecutionResult:
    frozen_job_index: int
    execution_index: int
    comparison_mode_id: str
    prompt_id: str
    prompt_version: str
    status: str
    job_dir: Path
    parse_status: str
    validation_status: str
    input_finding_count: int
    finding_verification_count: int
    additional_finding_count: int
    confirmed_finding_count: int = 0
    revised_finding_count: int = 0
    rejected_finding_count: int = 0
    received_additional_finding_count: int = 0
    accepted_additional_finding_count: int = 0
    dropped_additional_finding_count: int = 0
    adopted_finding_count: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class ComparisonFindingVerificationExecutionResult:
    run_id: str
    output_dir: Path
    run_summary_path: Path
    source_assessment_run_dir: Path
    job_results: tuple[ComparisonFindingVerificationJobExecutionResult, ...]


@dataclass(frozen=True)
class ComparisonFindingVerificationExecutionReport:
    result: ComparisonFindingVerificationExecutionResult
    messages: tuple[str, ...]


def _resolve_output(
    *,
    project_root: Path,
    output_dir: Path | str | None,
    run_id: str | None,
) -> tuple[Path, str]:
    requested_run_id = run_id.strip() if run_id is not None else ""
    if run_id is not None and not requested_run_id:
        raise ValueError("run_id must be a non-empty string when provided")

    if output_dir is not None:
        resolved_output = Path(output_dir).resolve()
        resolved_output.mkdir(parents=True, exist_ok=True)
        resolved_run_id = requested_run_id or format_run_timestamp(utc_run_stamp())
        return resolved_output, resolved_run_id

    phase_root = (
        project_root.resolve()
        / "runs"
        / EVIDENCE_COMPARISON_STAGE
        / CLINICAL_SAFETY_EVIDENCE_SCOPE
        / AGGREGATE_COMPARISON_SPECIALIZATION
        / COMPARISON_FINDING_VERIFICATION_PHASE
    )
    session_name = requested_run_id or format_run_timestamp(utc_run_stamp())
    session_dir = resolve_unique_session_dir(
        phase_root,
        sanitize_run_segment(session_name),
    )
    return session_dir.resolve(), session_dir.name


def _load_validated_evidence(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(
            f"aggregate_comparison_evidence must point to an existing file: {resolved}"
        )
    payload = load_json(resolved)
    from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
        validate_aggregate_comparison_evidence,
    )

    validate_aggregate_comparison_evidence(payload)
    return payload


def _prompt_definitions_summary(
    job_results: Sequence[ComparisonFindingVerificationJobExecutionResult],
) -> dict[str, dict[str, str]]:
    definitions: dict[str, dict[str, str]] = {}
    for result in job_results:
        definitions[result.prompt_id] = {"version": result.prompt_version}
    return definitions


def run_comparison_finding_verification_execution(
    *,
    project_root: Path,
    assessment_run_dir: Path | str,
    llm_mode: str,
    llm_profile: str | None = None,
    thinking: bool | None = None,
    provider: LLMProvider | None = None,
    seed: int = DEFAULT_LLM_SEED,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
    max_concurrency: int | None = None,
) -> ComparisonFindingVerificationExecutionReport:
    """Execute Comparison Finding Verification jobs from an Assessment execution run."""

    if llm_mode not in {"mock", "api"}:
        raise ValueError("llm_mode must be 'mock' or 'api'")
    if llm_mode == "api" and not llm_profile:
        raise ValueError("API execution requires explicit llm_profile")
    if max_concurrency is not None and (
        isinstance(max_concurrency, bool)
        or not isinstance(max_concurrency, int)
        or max_concurrency < 1
    ):
        raise ValueError("max_concurrency must be a positive integer when provided")

    assessment_handoff = resolve_comparison_finding_assessment_execution_handoff(
        assessment_run_dir
    )
    verification_inputs = (
        materialize_comparison_finding_verification_inputs_from_assessment_run(
            assessment_handoff.assessment_run_dir
        )
    )
    if not verification_inputs:
        raise ValueError(
            "assessment run has no successful jobs eligible for verification"
        )

    plan_handoff = resolve_comparison_finding_assessment_plan_handoff(
        assessment_handoff.plan_run_dir
    )
    aggregate_comparison_evidence = _load_validated_evidence(
        assessment_handoff.evidence_path
    )
    verify_participant_provenance(
        expected=plan_handoff.participant_provenance,
        evidence=aggregate_comparison_evidence,
    )
    frozen_jobs_by_index = {
        index: job for index, job in enumerate(plan_handoff.frozen_jobs, start=1)
    }
    assessment_findings = load_json(assessment_handoff.findings_path)

    requested_response_format = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
    ).response_format
    effective_provider = provider
    if effective_provider is None:
        if llm_mode == "mock":
            raise ValueError("mock execution requires an injected provider")
        effective_provider = build_api_provider(
            llm_profile=llm_profile,
            thinking=thinking,
            response_format=requested_response_format,
            seed=seed,
        )

    git_provenance = snapshot_git_provenance_before_run(root=project_root)
    resolved_output, resolved_run_id = _resolve_output(
        project_root=project_root,
        output_dir=output_dir,
        run_id=run_id,
    )
    jobs_root = resolved_output / COMPARISON_FINDING_VERIFICATION_JOBS_DIRNAME
    jobs_root.mkdir(parents=True, exist_ok=True)

    effective_concurrency = (
        len(verification_inputs)
        if max_concurrency is None
        else min(max_concurrency, len(verification_inputs))
    )

    execution_started = perf_counter()
    verification_execution = execute_comparison_finding_verification_jobs(
        verification_inputs=verification_inputs,
        planned_jobs_by_index=frozen_jobs_by_index,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        assessment_findings_artifact=assessment_findings,
        provider=effective_provider,
        max_concurrency=max_concurrency,
    )
    execution_wall_elapsed_ms = round((perf_counter() - execution_started) * 1000)

    job_results: list[ComparisonFindingVerificationJobExecutionResult] = []
    for execution in verification_execution.job_executions:
        job_dir = (
            jobs_root
            / f"{execution.frozen_job_index:03d}_{execution.comparison_mode_id}"
        )
        persist_comparison_finding_verification_job_execution(
            execution=execution,
            job_dir=job_dir,
            llm_profile=llm_profile,
            thinking=thinking,
            response_format=requested_response_format,
            seed=seed,
        )
        job_results.append(
            ComparisonFindingVerificationJobExecutionResult(
                frozen_job_index=execution.frozen_job_index,
                execution_index=execution.execution_index,
                comparison_mode_id=execution.comparison_mode_id,
                prompt_id=execution.prompt_id,
                prompt_version=execution.prompt_version,
                status=execution.status,
                job_dir=job_dir,
                parse_status=execution.parse_status,
                validation_status=execution.validation_status,
                input_finding_count=execution.input_finding_count,
                finding_verification_count=execution.finding_verification_count,
                additional_finding_count=execution.additional_finding_count,
                confirmed_finding_count=execution.confirmed_finding_count,
                revised_finding_count=execution.revised_finding_count,
                rejected_finding_count=execution.rejected_finding_count,
                received_additional_finding_count=(
                    execution.received_additional_finding_count
                ),
                accepted_additional_finding_count=(
                    execution.accepted_additional_finding_count
                ),
                dropped_additional_finding_count=(
                    execution.dropped_additional_finding_count
                ),
                adopted_finding_count=execution.adopted_finding_count,
                error_message=execution.error_message,
            )
        )

    findings_path: Path | None = None
    adopted_finding_count = verification_execution.adopted_finding_count
    if verification_execution.findings_artifact is not None:
        findings_path = resolved_output / FINDINGS_FILENAME
        save_json(findings_path, verification_execution.findings_artifact)

    run_status = verification_execution.run_status
    success_count = verification_execution.success_count
    executed_job_count_by_comparison_mode = dict(
        Counter(result.comparison_mode_id for result in job_results)
    )
    successful_results = [
        result for result in job_results if result.status == "success"
    ]
    assessment_run_dir_posix = assessment_handoff.assessment_run_dir.as_posix()
    plan_run_dir_posix = assessment_handoff.plan_run_dir.as_posix()
    run_summary_path = resolved_output / RUN_SUMMARY_FILENAME
    save_json(
        run_summary_path,
        {
            "run_id": resolved_run_id,
            "stage": EVIDENCE_COMPARISON_STAGE,
            "evidence_scope": CLINICAL_SAFETY_EVIDENCE_SCOPE,
            "specialization": AGGREGATE_COMPARISON_SPECIALIZATION,
            "phase": COMPARISON_FINDING_VERIFICATION_PHASE,
            "created_at": utc_now_iso(),
            "git_commit": git_provenance["git_commit"],
            "git_dirty": git_provenance["git_dirty"],
            "git_dirty_checked_at": git_provenance["git_dirty_checked_at"],
            "upstream_run_id": assessment_handoff.assessment_run_id,
            "upstream_stage": COMPARISON_FINDING_ASSESSMENT_PHASE,
            "status": run_status,
            "run_status": run_status,
            "run_dir_layout": COMPARISON_FINDING_VERIFICATION_RUN_DIR_LAYOUT,
            "completed_operation": COMPARISON_FINDING_VERIFICATION_OPERATION,
            "inputs": {
                "source_assessment_run": {
                    "run_id": assessment_handoff.assessment_run_id,
                    "run_dir": assessment_run_dir_posix,
                },
                "source_plan_run": {
                    "run_id": assessment_handoff.plan_run_id,
                    "run_dir": plan_run_dir_posix,
                    "capability_id": assessment_handoff.capability_id,
                },
                "aggregate_comparison_evidence": {
                    "path": assessment_handoff.evidence_path.as_posix(),
                    "resolved_from": "source_assessment_run",
                },
                "findings": {
                    "path": assessment_handoff.findings_path.as_posix(),
                    "resolved_from": "source_assessment_run",
                },
                "llm_mode": llm_mode,
                "llm_profile": llm_profile,
                "thinking": thinking,
                "seed": seed,
                "max_concurrency": max_concurrency,
            },
            "outputs": {
                "run_summary": RUN_SUMMARY_FILENAME,
                "jobs_dir": COMPARISON_FINDING_VERIFICATION_JOBS_DIRNAME,
                "findings": FINDINGS_FILENAME if findings_path is not None else None,
            },
            "stats": {
                "executed_job_count": len(job_results),
                "executed_job_count_by_comparison_mode": executed_job_count_by_comparison_mode,
                "success_count": success_count,
                "failed_count": len(job_results) - success_count,
                "effective_concurrency": effective_concurrency,
                "input_finding_count": sum(
                    result.input_finding_count for result in successful_results
                ),
                "confirmed_finding_count": sum(
                    result.confirmed_finding_count for result in successful_results
                ),
                "revised_finding_count": sum(
                    result.revised_finding_count for result in successful_results
                ),
                "rejected_finding_count": sum(
                    result.rejected_finding_count for result in successful_results
                ),
                "received_additional_finding_count": sum(
                    result.received_additional_finding_count
                    for result in successful_results
                ),
                "accepted_additional_finding_count": sum(
                    result.accepted_additional_finding_count
                    for result in successful_results
                ),
                "dropped_additional_finding_count": sum(
                    result.dropped_additional_finding_count
                    for result in successful_results
                ),
                "adopted_finding_count": adopted_finding_count,
            },
            "execution_wall_elapsed_ms": execution_wall_elapsed_ms,
            "prompt_definitions": _prompt_definitions_summary(job_results),
            "jobs": [
                {
                    "frozen_job_index": result.frozen_job_index,
                    "execution_index": result.execution_index,
                    "comparison_mode_id": result.comparison_mode_id,
                    "prompt_id": result.prompt_id,
                    "prompt_version": result.prompt_version,
                    "status": result.status,
                    "parse_status": result.parse_status,
                    "validation_status": result.validation_status,
                    "input_finding_count": result.input_finding_count,
                    "finding_verification_count": result.finding_verification_count,
                    "additional_finding_count": result.additional_finding_count,
                    "confirmed_finding_count": result.confirmed_finding_count,
                    "revised_finding_count": result.revised_finding_count,
                    "rejected_finding_count": result.rejected_finding_count,
                    "received_additional_finding_count": (
                        result.received_additional_finding_count
                    ),
                    "accepted_additional_finding_count": (
                        result.accepted_additional_finding_count
                    ),
                    "dropped_additional_finding_count": (
                        result.dropped_additional_finding_count
                    ),
                    "adopted_finding_count": result.adopted_finding_count,
                    "job_dir": (
                        f"{COMPARISON_FINDING_VERIFICATION_JOBS_DIRNAME}/"
                        f"{result.frozen_job_index:03d}_{result.comparison_mode_id}"
                    ),
                    "error_message": result.error_message,
                    "llm_invocations": serialize_llm_invocations(
                        verification_execution.job_executions[index].llm_invocations
                    ),
                    **llm_effective_execution_fields(
                        serialize_llm_invocations(
                            verification_execution.job_executions[
                                index
                            ].llm_invocations
                        )[-1]
                        if verification_execution.job_executions[index].llm_invocations
                        else None
                    ),
                }
                for index, result in enumerate(job_results)
            ],
        },
    )

    result = ComparisonFindingVerificationExecutionResult(
        run_id=resolved_run_id,
        output_dir=resolved_output,
        run_summary_path=run_summary_path,
        source_assessment_run_dir=assessment_handoff.assessment_run_dir,
        job_results=tuple(job_results),
    )
    report_messages = [
        f"run_id: {resolved_run_id}",
        f"status: {run_status}",
        f"jobs: {success_count}/{len(job_results)} succeeded",
        f"run_summary: {run_summary_path}",
        f"source_assessment_run: {assessment_run_dir_posix}",
    ]
    if findings_path is not None:
        report_messages.append(f"findings: {findings_path}")
    else:
        report_messages.append("findings: (none)")
    return ComparisonFindingVerificationExecutionReport(
        result=result,
        messages=tuple(report_messages),
    )


__all__ = [
    "COMPARISON_FINDING_VERIFICATION_JOBS_DIRNAME",
    "COMPARISON_FINDING_VERIFICATION_PHASE",
    "DEFAULT_LLM_SEED",
    "FINDINGS_FILENAME",
    "RUN_SUMMARY_FILENAME",
    "VALIDATED_RESPONSE_FILENAME",
    "VERIFICATION_INPUT_FILENAME",
    "ComparisonFindingVerificationExecutionReport",
    "ComparisonFindingVerificationExecutionResult",
    "ComparisonFindingVerificationJobExecutionResult",
    "run_comparison_finding_verification_execution",
]
