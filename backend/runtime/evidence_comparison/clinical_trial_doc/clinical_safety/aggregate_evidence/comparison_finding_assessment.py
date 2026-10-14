"""Standalone dev runtime for Comparison Finding Assessment LLM execution."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDINGS_FILENAME,
    validate_findings,
)
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from llm.execution_metadata import llm_effective_execution_fields
from llm.invocation import serialize_llm_invocations
from llm.providers.base import LLMProvider
from llm.providers.factory import build_api_provider
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonModeId,
    materialize_comparison_finding_assessment_llm_input,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.execution import (
    execute_comparison_finding_assessment_jobs,
    select_planned_assessment_jobs,
    validate_assessment_job_selector,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_persistence import (
    ACCEPTED_CANDIDATES_FILENAME,
    CANDIDATE_ELIGIBILITY_DEBUG_FILENAME,
    persist_comparison_finding_assessment_job_execution,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE,
    resolve_comparison_finding_assessment_plan_handoff,
    verify_participant_provenance,
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
COMPARISON_FINDING_ASSESSMENT_PHASE = "comparison_finding_assessment"
COMPARISON_FINDING_ASSESSMENT_RUN_DIR_LAYOUT = (
    "stage/evidence_scope/specialization/phase/run_id"
)
COMPARISON_FINDING_ASSESSMENT_OPERATION = (
    "aggregate_evidence.execute_comparison_finding_assessment"
)
COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME = "jobs"
RUN_SUMMARY_FILENAME = "run_summary.json"
DEFAULT_LLM_SEED = 1234


@dataclass(frozen=True)
class ComparisonFindingAssessmentJobExecutionResult:
    frozen_job_index: int
    job_index: int
    comparison_mode_id: ComparisonModeId
    prompt_id: str
    prompt_version: str
    status: str
    job_dir: Path
    parse_status: str
    validation_status: str
    candidate_count: int
    accepted_candidate_count: int = 0
    dropped_candidate_count: int = 0
    finding_count: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class ComparisonFindingAssessmentExecutionResult:
    run_id: str
    output_dir: Path
    run_summary_path: Path
    job_results: tuple[ComparisonFindingAssessmentJobExecutionResult, ...]


@dataclass(frozen=True)
class ComparisonFindingAssessmentExecutionReport:
    result: ComparisonFindingAssessmentExecutionResult
    messages: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonFindingAssessmentSuccessfulJobRecord:
    frozen_job_index: int
    execution_index: int
    comparison_mode_id: str
    job_dir: str


@dataclass(frozen=True)
class ComparisonFindingAssessmentExecutionHandoff:
    assessment_run_id: str
    assessment_run_dir: Path
    plan_run_id: str
    plan_run_dir: Path
    capability_id: str
    evidence_path: Path
    findings_path: Path
    successful_jobs: tuple[ComparisonFindingAssessmentSuccessfulJobRecord, ...]


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
        / COMPARISON_FINDING_ASSESSMENT_PHASE
    )
    session_name = requested_run_id or format_run_timestamp(utc_run_stamp())
    session_dir = resolve_unique_session_dir(
        phase_root,
        sanitize_run_segment(session_name),
    )
    return session_dir.resolve(), session_dir.name


def _prompt_definitions_summary(
    job_results: Sequence[ComparisonFindingAssessmentJobExecutionResult],
) -> dict[str, dict[str, str]]:
    definitions: dict[str, dict[str, str]] = {}
    for result in job_results:
        definitions[result.prompt_id] = {"version": result.prompt_version}
    return definitions


def run_comparison_finding_assessment_execution(
    *,
    project_root: Path,
    plan_run_dir: Path | str,
    llm_mode: str,
    llm_profile: str | None = None,
    thinking: bool | None = None,
    provider: LLMProvider | None = None,
    seed: int = DEFAULT_LLM_SEED,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
    comparison_modes: Sequence[ComparisonModeId] | None = None,
    max_jobs: int | None = None,
    frozen_job_index: int | None = None,
    max_concurrency: int | None = None,
) -> ComparisonFindingAssessmentExecutionReport:
    """Execute Comparison Finding Assessment jobs from a frozen plan run."""

    if llm_mode not in {"mock", "api"}:
        raise ValueError("llm_mode must be 'mock' or 'api'")
    if llm_mode == "api" and not llm_profile:
        raise ValueError("API execution requires explicit llm_profile")
    if max_jobs is not None and max_jobs < 1:
        raise ValueError("max_jobs must be at least 1 when provided")
    if max_concurrency is not None and (
        isinstance(max_concurrency, bool)
        or not isinstance(max_concurrency, int)
        or max_concurrency < 1
    ):
        raise ValueError("max_concurrency must be a positive integer when provided")
    validate_assessment_job_selector(
        frozen_job_index=frozen_job_index,
        comparison_modes=comparison_modes,
        max_jobs=max_jobs,
    )

    handoff = resolve_comparison_finding_assessment_plan_handoff(plan_run_dir)
    aggregate_comparison_evidence = _load_validated_evidence(handoff.evidence_path)
    verify_participant_provenance(
        expected=handoff.participant_provenance,
        evidence=aggregate_comparison_evidence,
    )

    comparison_mode_filter = (
        frozenset(comparison_modes) if comparison_modes is not None else None
    )
    selected_jobs = select_planned_assessment_jobs(
        handoff.frozen_jobs,
        frozen_job_index=frozen_job_index,
        comparison_modes=comparison_mode_filter,
        max_jobs=max_jobs,
    )
    if not selected_jobs:
        raise ValueError(
            "no assessment jobs matched the requested execution filter"
        )

    requested_response_format = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
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
    jobs_root = resolved_output / COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME
    jobs_root.mkdir(parents=True, exist_ok=True)

    execution_started = perf_counter()
    assessment_execution = execute_comparison_finding_assessment_jobs(
        selected_jobs=selected_jobs,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        provider=effective_provider,
        max_concurrency=max_concurrency,
    )
    execution_wall_elapsed_ms = round((perf_counter() - execution_started) * 1000)

    job_results: list[ComparisonFindingAssessmentJobExecutionResult] = []
    for (frozen_job_index, job), execution in zip(
        selected_jobs,
        assessment_execution.job_executions,
        strict=True,
    ):
        job_dir = jobs_root / f"{frozen_job_index:03d}_{job.comparison_mode_id}"
        evidence_input = materialize_comparison_finding_assessment_llm_input(
            job=job,
            aggregate_comparison_evidence=aggregate_comparison_evidence,
        )
        persist_comparison_finding_assessment_job_execution(
            execution=execution,
            job_dir=job_dir,
            evidence_input=evidence_input,
            llm_profile=llm_profile,
            thinking=thinking,
            response_format=requested_response_format,
            seed=seed,
        )
        job_results.append(
            ComparisonFindingAssessmentJobExecutionResult(
                frozen_job_index=execution.frozen_job_index,
                job_index=execution.execution_index,
                comparison_mode_id=execution.job.comparison_mode_id,
                prompt_id=execution.prompt_id,
                prompt_version=execution.prompt_version,
                status=execution.status,
                job_dir=job_dir,
                parse_status=execution.parse_status,
                validation_status=execution.validation_status,
                candidate_count=execution.candidate_count,
                accepted_candidate_count=execution.accepted_candidate_count,
                dropped_candidate_count=execution.dropped_candidate_count,
                finding_count=execution.finding_count,
                error_message=execution.error_message,
            )
        )

    findings_path = resolved_output / FINDINGS_FILENAME
    finding_count = assessment_execution.finding_count
    if assessment_execution.findings_artifact is not None:
        save_json(findings_path, assessment_execution.findings_artifact)

    run_status = assessment_execution.run_status
    success_count = assessment_execution.success_count
    executed_job_count_by_comparison_mode = dict(
        Counter(result.comparison_mode_id for result in job_results)
    )
    plan_run_dir_posix = handoff.plan_run_dir.as_posix()
    total_accepted_candidate_count = sum(
        result.accepted_candidate_count for result in job_results
    )
    total_dropped_candidate_count = sum(
        result.dropped_candidate_count for result in job_results
    )
    effective_concurrency = (
        len(selected_jobs)
        if max_concurrency is None
        else min(max_concurrency, len(selected_jobs))
    )
    run_summary_path = resolved_output / RUN_SUMMARY_FILENAME
    save_json(
        run_summary_path,
        {
            "run_id": resolved_run_id,
            "stage": EVIDENCE_COMPARISON_STAGE,
            "evidence_scope": CLINICAL_SAFETY_EVIDENCE_SCOPE,
            "specialization": AGGREGATE_COMPARISON_SPECIALIZATION,
            "phase": COMPARISON_FINDING_ASSESSMENT_PHASE,
            "created_at": utc_now_iso(),
            "git_commit": git_provenance["git_commit"],
            "git_dirty": git_provenance["git_dirty"],
            "git_dirty_checked_at": git_provenance["git_dirty_checked_at"],
            "upstream_run_id": handoff.plan_run_id,
            "upstream_stage": COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE,
            "status": run_status,
            "run_status": run_status,
            "run_dir_layout": COMPARISON_FINDING_ASSESSMENT_RUN_DIR_LAYOUT,
            "completed_operation": COMPARISON_FINDING_ASSESSMENT_OPERATION,
            "inputs": {
                "source_plan_run": {
                    "run_id": handoff.plan_run_id,
                    "run_dir": plan_run_dir_posix,
                    "capability_id": handoff.capability_id,
                },
                "aggregate_comparison_evidence": {
                    "path": handoff.evidence_path.as_posix(),
                    "resolved_from": "source_plan_run",
                },
                "llm_mode": llm_mode,
                "llm_profile": llm_profile,
                "thinking": thinking,
                "seed": seed,
                "frozen_job_index": frozen_job_index,
                "comparison_modes": list(comparison_modes)
                if comparison_modes is not None
                else None,
                "max_jobs": max_jobs,
                "max_concurrency": max_concurrency,
            },
            "outputs": {
                "run_summary": "run_summary.json",
                "jobs_dir": COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME,
                "findings": FINDINGS_FILENAME
                if assessment_execution.findings_artifact is not None
                else None,
            },
            "stats": {
                "frozen_job_count": len(handoff.frozen_jobs),
                "executed_job_count": len(job_results),
                "executed_job_count_by_comparison_mode": executed_job_count_by_comparison_mode,
                "success_count": success_count,
                "failed_count": len(job_results) - success_count,
                "finding_count": finding_count,
                "accepted_candidate_count": total_accepted_candidate_count,
                "dropped_candidate_count": total_dropped_candidate_count,
                "effective_concurrency": effective_concurrency,
            },
            "execution_wall_elapsed_ms": execution_wall_elapsed_ms,
            "prompt_definitions": _prompt_definitions_summary(job_results),
            "jobs": [
                {
                    "frozen_job_index": result.frozen_job_index,
                    "execution_index": result.job_index,
                    "comparison_mode_id": result.comparison_mode_id,
                    "prompt_id": result.prompt_id,
                    "prompt_version": result.prompt_version,
                    "status": result.status,
                    "parse_status": result.parse_status,
                    "validation_status": result.validation_status,
                    "candidate_count": result.candidate_count,
                    "accepted_candidate_count": result.accepted_candidate_count,
                    "dropped_candidate_count": result.dropped_candidate_count,
                    "finding_count": result.finding_count,
                    "job_dir": (
                        f"{COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME}/"
                        f"{result.frozen_job_index:03d}_{result.comparison_mode_id}"
                    ),
                    "error_message": result.error_message,
                    "llm_invocations": serialize_llm_invocations(
                        assessment_execution.job_executions[index].llm_invocations
                    ),
                    **llm_effective_execution_fields(
                        serialize_llm_invocations(
                            assessment_execution.job_executions[
                                index
                            ].llm_invocations
                        )[-1]
                        if assessment_execution.job_executions[index].llm_invocations
                        else None
                    ),
                }
                for index, result in enumerate(job_results)
            ],
        },
    )

    result = ComparisonFindingAssessmentExecutionResult(
        run_id=resolved_run_id,
        output_dir=resolved_output,
        run_summary_path=run_summary_path,
        job_results=tuple(job_results),
    )
    report_messages = [
        f"run_id: {resolved_run_id}",
        f"status: {run_status}",
        f"jobs: {success_count}/{len(job_results)} succeeded",
        f"run_summary: {run_summary_path}",
    ]
    if assessment_execution.findings_artifact is not None:
        report_messages.append(f"findings: {findings_path}")
    else:
        report_messages.append("findings: (none)")
    return ComparisonFindingAssessmentExecutionReport(
        result=result,
        messages=tuple(report_messages),
    )


def resolve_comparison_finding_assessment_execution_handoff(
    assessment_run_dir: Path | str,
) -> ComparisonFindingAssessmentExecutionHandoff:
    """Resolve upstream lineage and findings artifact from an assessment execution run."""

    resolved_assessment_run_dir = Path(assessment_run_dir).resolve()
    if not resolved_assessment_run_dir.is_dir():
        raise ValueError(
            f"assessment_run_dir must be an existing directory: "
            f"{resolved_assessment_run_dir}"
        )

    summary_path = resolved_assessment_run_dir / RUN_SUMMARY_FILENAME
    if not summary_path.is_file():
        raise ValueError(f"assessment run_summary must exist: {summary_path}")
    summary = load_json(summary_path)
    if not isinstance(summary, Mapping):
        raise TypeError("assessment run_summary must be a mapping")
    if summary.get("stage") != EVIDENCE_COMPARISON_STAGE:
        raise ValueError("assessment run_summary.stage must be evidence_comparison")
    if summary.get("phase") != COMPARISON_FINDING_ASSESSMENT_PHASE:
        raise ValueError(
            "assessment run_summary.phase must be comparison_finding_assessment"
        )

    assessment_run_id = summary.get("run_id")
    if not isinstance(assessment_run_id, str) or not assessment_run_id.strip():
        raise ValueError("assessment run_summary.run_id must be a non-empty string")

    inputs = summary.get("inputs")
    if not isinstance(inputs, Mapping):
        raise TypeError("assessment run_summary.inputs must be a mapping")

    source_plan_run = inputs.get("source_plan_run")
    if not isinstance(source_plan_run, Mapping):
        raise TypeError(
            "assessment run_summary.inputs.source_plan_run must be a mapping"
        )
    plan_run_dir_raw = source_plan_run.get("run_dir")
    if not isinstance(plan_run_dir_raw, str) or not plan_run_dir_raw.strip():
        raise ValueError(
            "assessment run_summary.inputs.source_plan_run.run_dir "
            "must be a non-empty string"
        )
    plan_run_id = source_plan_run.get("run_id")
    if not isinstance(plan_run_id, str) or not plan_run_id.strip():
        raise ValueError(
            "assessment run_summary.inputs.source_plan_run.run_id "
            "must be a non-empty string"
        )
    capability_id = source_plan_run.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError(
            "assessment run_summary.inputs.source_plan_run.capability_id "
            "must be a non-empty string"
        )

    evidence_inputs = inputs.get("aggregate_comparison_evidence")
    if not isinstance(evidence_inputs, Mapping):
        raise TypeError(
            "assessment run_summary.inputs.aggregate_comparison_evidence "
            "must be a mapping"
        )
    evidence_path_raw = evidence_inputs.get("path")
    if not isinstance(evidence_path_raw, str) or not evidence_path_raw.strip():
        raise ValueError(
            "assessment run_summary.inputs.aggregate_comparison_evidence.path "
            "must be a non-empty string"
        )

    outputs = summary.get("outputs")
    if not isinstance(outputs, Mapping):
        raise TypeError("assessment run_summary.outputs must be a mapping")
    findings_ref = outputs.get("findings")
    if findings_ref is None:
        raise ValueError(
            "assessment run has no findings artifact; "
            "cannot materialize verification input"
        )
    if not isinstance(findings_ref, str) or not findings_ref.strip():
        raise ValueError(
            "assessment run_summary.outputs.findings must be a non-empty string "
            "when present"
        )

    findings_path = Path(findings_ref.strip())
    if not findings_path.is_absolute():
        findings_path = resolved_assessment_run_dir / findings_path
    findings_path = findings_path.resolve()
    if not findings_path.is_file():
        raise ValueError(f"assessment findings artifact must exist: {findings_path}")

    findings_payload = load_json(findings_path)
    validate_findings(findings_payload)

    jobs_raw = summary.get("jobs")
    if not isinstance(jobs_raw, list):
        raise TypeError("assessment run_summary.jobs must be a list")

    successful_jobs: list[ComparisonFindingAssessmentSuccessfulJobRecord] = []
    for index, job_row in enumerate(jobs_raw):
        if not isinstance(job_row, Mapping):
            raise TypeError(f"assessment run_summary.jobs[{index}] must be a mapping")
        if job_row.get("status") != "success":
            continue
        frozen_job_index = job_row.get("frozen_job_index")
        execution_index = job_row.get("execution_index")
        comparison_mode_id = job_row.get("comparison_mode_id")
        job_dir = job_row.get("job_dir")
        if not isinstance(frozen_job_index, int) or frozen_job_index < 1:
            raise ValueError(
                f"assessment run_summary.jobs[{index}].frozen_job_index "
                "must be a positive integer"
            )
        if not isinstance(execution_index, int) or execution_index < 1:
            raise ValueError(
                f"assessment run_summary.jobs[{index}].execution_index "
                "must be a positive integer"
            )
        if not isinstance(comparison_mode_id, str) or not comparison_mode_id.strip():
            raise ValueError(
                f"assessment run_summary.jobs[{index}].comparison_mode_id "
                "must be a non-empty string"
            )
        if not isinstance(job_dir, str) or not job_dir.strip():
            raise ValueError(
                f"assessment run_summary.jobs[{index}].job_dir "
                "must be a non-empty string"
            )
        successful_jobs.append(
            ComparisonFindingAssessmentSuccessfulJobRecord(
                frozen_job_index=frozen_job_index,
                execution_index=execution_index,
                comparison_mode_id=comparison_mode_id.strip(),
                job_dir=job_dir.strip(),
            )
        )

    return ComparisonFindingAssessmentExecutionHandoff(
        assessment_run_id=assessment_run_id.strip(),
        assessment_run_dir=resolved_assessment_run_dir,
        plan_run_id=plan_run_id.strip(),
        plan_run_dir=Path(plan_run_dir_raw.strip()).resolve(),
        capability_id=capability_id.strip(),
        evidence_path=Path(evidence_path_raw.strip()).resolve(),
        findings_path=findings_path,
        successful_jobs=tuple(successful_jobs),
    )


__all__ = [
    "ACCEPTED_CANDIDATES_FILENAME",
    "CANDIDATE_ELIGIBILITY_DEBUG_FILENAME",
    "COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME",
    "COMPARISON_FINDING_ASSESSMENT_PHASE",
    "DEFAULT_LLM_SEED",
    "RUN_SUMMARY_FILENAME",
    "ComparisonFindingAssessmentExecutionHandoff",
    "ComparisonFindingAssessmentExecutionReport",
    "ComparisonFindingAssessmentExecutionResult",
    "ComparisonFindingAssessmentJobExecutionResult",
    "ComparisonFindingAssessmentSuccessfulJobRecord",
    "resolve_comparison_finding_assessment_execution_handoff",
    "run_comparison_finding_assessment_execution",
]
