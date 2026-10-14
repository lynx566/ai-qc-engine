"""Persist clinical-safety aggregate Evidence Comparison stage artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    FINAL_FINDINGS_FILENAME,
    FINDINGS_FILENAME,
    validate_aggregate_comparison_evidence,
    validate_final_findings,
    validate_findings,
)
from llm.debug_artifacts import format_prompt_txt
from llm.execution_metadata import llm_effective_execution_fields
from llm.invocation import serialize_llm_invocations
from operations.evidence_comparison.stage import EvidenceComparisonStageInput
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME,
    materialize_comparison_finding_assessment_llm_input,
    serialize_candidate_eligibility_audit,
    serialize_comparison_finding_assessment_jobs,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    serialize_validated_response as serialize_assessment_validated_response,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.alias_qc import (
    serialize_alias_qc as serialize_consolidation_alias_qc,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.response_validation import (
    serialize_validated_response as serialize_consolidation_validated_response,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    serialize_additional_finding_eligibility_audit,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    serialize_validated_response as serialize_verification_validated_response,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceComparisonExecution,
    AggregateEvidenceComparisonPreFinalState,
)
from runtime.io import save_json
from runtime.run_layout import utc_now_iso

EVIDENCE_COMPARISON_STAGE = "evidence_comparison"
CLINICAL_SAFETY_EVIDENCE_SCOPE = "clinical_safety"
AGGREGATE_COMPARISON_SPECIALIZATION = "aggregate"
COMPARISON_FINDING_ASSESSMENT_STAGE_PHASE = "comparison_finding_assessment"
COMPARISON_FINDING_VERIFICATION_STAGE_PHASE = "comparison_finding_verification"
COMPARISON_FINDING_ASSESSMENT_STAGE_OPERATION = (
    "aggregate_evidence.execute_comparison_finding_assessment"
)
COMPARISON_FINDING_VERIFICATION_STAGE_OPERATION = (
    "aggregate_evidence.execute_comparison_finding_verification"
)
COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME = "jobs"
COMPARISON_FINDING_CONSOLIDATION_DIRNAME = "consolidation"
RUN_SUMMARY_FILENAME = "run_summary.json"


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonPersistResult:
    output_dir: Path
    run_id: str
    aggregate_comparison_evidence_path: Path
    comparison_finding_assessment_jobs_path: Path
    job_final_findings_path: Path | None
    final_findings_path: Path
    run_summary_path: Path


@dataclass(frozen=True, slots=True)
class _PersistedPreFinalArtifacts:
    aggregate_comparison_evidence_path: Path
    comparison_finding_assessment_jobs_path: Path
    job_final_findings_path: Path | None
    job_summaries: tuple[dict[str, Any], ...]
    consolidation_summaries: tuple[dict[str, Any], ...]


def _job_dir_name(*, frozen_job_index: int, comparison_mode_id: str) -> str:
    return f"{frozen_job_index:03d}_{comparison_mode_id}"


def _persist_assessment_job(
    *,
    execution,
    aggregate_comparison_evidence: dict[str, Any],
    job_root: Path,
    assessment_dir: Path | None = None,
) -> dict[str, Any]:
    assessment_dir = assessment_dir or (job_root / "assessment")
    assessment_dir.mkdir(parents=True, exist_ok=True)
    evidence_input = materialize_comparison_finding_assessment_llm_input(
        job=execution.job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    (assessment_dir / "evidence_input.txt").write_text(evidence_input, encoding="utf-8")

    if execution.messages:
        (assessment_dir / "prompt.txt").write_text(
            format_prompt_txt(list(execution.messages)),
            encoding="utf-8",
        )

    if execution.raw_response_text is not None:
        (assessment_dir / "result.txt").write_text(
            execution.raw_response_text,
            encoding="utf-8",
        )

    if execution.validated_response is not None:
        save_json(
            assessment_dir / "validated_response.json",
            serialize_assessment_validated_response(execution.validated_response),
        )
    if execution.accepted_response is not None:
        save_json(
            assessment_dir / "accepted_candidates.json",
            serialize_assessment_validated_response(execution.accepted_response),
        )
    if execution.eligibility is not None:
        save_json(
            assessment_dir / "candidate_eligibility.json",
            serialize_candidate_eligibility_audit(execution.eligibility),
        )

    llm_invocations = serialize_llm_invocations(execution.llm_invocations)
    return {
        "frozen_job_index": execution.frozen_job_index,
        "execution_index": execution.execution_index,
        "comparison_mode_id": execution.job.comparison_mode_id,
        "prompt_id": execution.prompt_id,
        "prompt_version": execution.prompt_version,
        "status": execution.status,
        "parse_status": execution.parse_status,
        "validation_status": execution.validation_status,
        "candidate_count": execution.candidate_count,
        "accepted_candidate_count": execution.accepted_candidate_count,
        "dropped_candidate_count": execution.dropped_candidate_count,
        "finding_count": execution.finding_count,
        "error_message": execution.error_message,
        "job_dir": job_root.as_posix(),
        "llm_invocations": llm_invocations,
        **llm_effective_execution_fields(
            llm_invocations[-1] if llm_invocations else None
        ),
    }


def _persist_verification_job(
    *,
    execution,
    job_root: Path,
) -> dict[str, Any]:
    verification_dir = job_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "verification_input.txt").write_text(
        execution.verification_input.user_input_text,
        encoding="utf-8",
    )

    if execution.messages:
        (verification_dir / "prompt.txt").write_text(
            format_prompt_txt(list(execution.messages)),
            encoding="utf-8",
        )

    if execution.raw_response_text is not None:
        (verification_dir / "result.txt").write_text(
            execution.raw_response_text,
            encoding="utf-8",
        )

    if execution.validated_response is not None:
        save_json(
            verification_dir / "validated_response.json",
            serialize_verification_validated_response(execution.validated_response),
        )
    if execution.additional_eligibility is not None:
        save_json(
            verification_dir / "additional_finding_eligibility.json",
            serialize_additional_finding_eligibility_audit(
                execution.additional_eligibility
            ),
        )

    llm_invocations = serialize_llm_invocations(execution.llm_invocations)
    return {
        "frozen_job_index": execution.frozen_job_index,
        "execution_index": execution.execution_index,
        "comparison_mode_id": execution.comparison_mode_id,
        "prompt_id": execution.prompt_id,
        "prompt_version": execution.prompt_version,
        "status": execution.status,
        "parse_status": execution.parse_status,
        "validation_status": execution.validation_status,
        "input_finding_count": execution.input_finding_count,
        "finding_verification_count": execution.finding_verification_count,
        "additional_finding_count": execution.additional_finding_count,
        "confirmed_finding_count": execution.confirmed_finding_count,
        "revised_finding_count": execution.revised_finding_count,
        "rejected_finding_count": execution.rejected_finding_count,
        "received_additional_finding_count": (
            execution.received_additional_finding_count
        ),
        "accepted_additional_finding_count": (
            execution.accepted_additional_finding_count
        ),
        "dropped_additional_finding_count": (
            execution.dropped_additional_finding_count
        ),
        "adopted_finding_count": execution.adopted_finding_count,
        "error_message": execution.error_message,
        "job_dir": job_root.as_posix(),
        "llm_invocations": llm_invocations,
        **llm_effective_execution_fields(
            llm_invocations[-1] if llm_invocations else None
        ),
    }


def _persist_consolidation_execution(
    *,
    execution,
    consolidation_root: Path,
) -> dict[str, Any]:
    mode_dir = consolidation_root / execution.comparison_mode_id
    mode_dir.mkdir(parents=True, exist_ok=True)
    for file_name in (
        "consolidation_input.txt",
        "prompt.txt",
        "result.txt",
        "validated_response.json",
        "alias_mapping.json",
        "alias_qc.json",
    ):
        artifact_path = mode_dir / file_name
        if artifact_path.exists():
            artifact_path.unlink()
    (mode_dir / "consolidation_input.txt").write_text(
        execution.consolidation_input.user_input_text,
        encoding="utf-8",
    )
    save_json(
        mode_dir / "alias_mapping.json",
        list(execution.consolidation_input.alias_mapping),
    )
    if execution.messages:
        (mode_dir / "prompt.txt").write_text(
            format_prompt_txt(list(execution.messages)),
            encoding="utf-8",
        )
    if execution.raw_response_text is not None:
        (mode_dir / "result.txt").write_text(
            execution.raw_response_text,
            encoding="utf-8",
        )
    if execution.validated_response is not None:
        save_json(
            mode_dir / "validated_response.json",
            serialize_consolidation_validated_response(
                execution.validated_response
            ),
        )
    if execution.alias_qc is not None:
        save_json(
            mode_dir / "alias_qc.json",
            serialize_consolidation_alias_qc(execution.alias_qc),
        )

    llm_invocations = serialize_llm_invocations(execution.llm_invocations)
    return {
        "comparison_mode_id": execution.comparison_mode_id,
        "prompt_id": execution.prompt_id,
        "prompt_version": execution.prompt_version,
        "status": execution.status,
        "provider_called": execution.provider_called,
        "parse_status": execution.parse_status,
        "validation_status": execution.validation_status,
        "finding_count": execution.finding_count,
        "group_count": execution.group_count,
        "alias_qc_mismatch_count": (
            execution.alias_qc.mismatch_count
            if execution.alias_qc is not None
            else None
        ),
        "alias_qc_all_groups_match": (
            execution.alias_qc.all_groups_match
            if execution.alias_qc is not None
            else None
        ),
        "error_message": execution.error_message,
        "output_dir": mode_dir.as_posix(),
        "llm_invocations": llm_invocations,
        **llm_effective_execution_fields(
            llm_invocations[-1] if llm_invocations else None
        ),
    }


def _persist_pre_final_artifacts(
    *,
    state: (
        AggregateEvidenceComparisonExecution
        | AggregateEvidenceComparisonPreFinalState
    ),
    capability_id: str,
    resolved_output: Path,
) -> _PersistedPreFinalArtifacts:
    resolved_output.mkdir(parents=True, exist_ok=True)

    aggregate_comparison_evidence_path = (
        resolved_output / AGGREGATE_COMPARISON_EVIDENCE_FILENAME
    )
    save_json(
        aggregate_comparison_evidence_path,
        state.aggregate_comparison_evidence,
    )
    validate_aggregate_comparison_evidence(state.aggregate_comparison_evidence)

    comparison_finding_assessment_jobs_path = (
        resolved_output / COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME
    )
    jobs_payload = serialize_comparison_finding_assessment_jobs(
        capability_id=capability_id,
        jobs=state.planned_jobs,
    )
    save_json(comparison_finding_assessment_jobs_path, jobs_payload)

    job_final_findings_path: Path | None = None
    if state.job_final_findings is not None:
        job_final_findings_path = resolved_output / FINDINGS_FILENAME
        save_json(job_final_findings_path, state.job_final_findings)
        validate_findings(state.job_final_findings)

    jobs_root = resolved_output / COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME
    jobs_root.mkdir(parents=True, exist_ok=True)

    verification_by_index = {}
    if state.verification is not None:
        verification_by_index = {
            job_execution.frozen_job_index: job_execution
            for job_execution in state.verification.job_executions
        }

    second_pass_by_index = {}
    if state.second_pass_assessment is not None:
        second_pass_by_index = {
            job_execution.frozen_job_index: job_execution
            for job_execution in state.second_pass_assessment.job_executions
        }

    job_summaries: list[dict[str, Any]] = []
    for assessment_execution in state.assessment.job_executions:
        job_root = jobs_root / _job_dir_name(
            frozen_job_index=assessment_execution.frozen_job_index,
            comparison_mode_id=assessment_execution.job.comparison_mode_id,
        )
        assessment_summary = _persist_assessment_job(
            execution=assessment_execution,
            aggregate_comparison_evidence=state.aggregate_comparison_evidence,
            job_root=job_root,
        )
        second_pass_execution = second_pass_by_index.get(
            assessment_execution.frozen_job_index
        )
        second_pass_summary = None
        if second_pass_execution is not None:
            second_pass_summary = _persist_assessment_job(
                execution=second_pass_execution,
                aggregate_comparison_evidence=state.aggregate_comparison_evidence,
                job_root=job_root,
                assessment_dir=job_root / "assessment" / "second_pass",
            )
        verification_execution = verification_by_index.get(
            assessment_execution.frozen_job_index
        )
        verification_summary = None
        if verification_execution is not None:
            verification_summary = _persist_verification_job(
                execution=verification_execution,
                job_root=job_root,
            )
        job_summaries.append(
            {
                "frozen_job_index": assessment_execution.frozen_job_index,
                "comparison_mode_id": assessment_execution.job.comparison_mode_id,
                "assessment": assessment_summary,
                "assessment_second_pass": second_pass_summary,
                "verification": verification_summary,
            }
        )

    consolidation_summaries: list[dict[str, Any]] = []
    consolidation_root = resolved_output / COMPARISON_FINDING_CONSOLIDATION_DIRNAME
    for consolidation_execution in state.consolidation_executions:
        consolidation_summaries.append(
            _persist_consolidation_execution(
                execution=consolidation_execution,
                consolidation_root=consolidation_root,
            )
        )

    return _PersistedPreFinalArtifacts(
        aggregate_comparison_evidence_path=aggregate_comparison_evidence_path,
        comparison_finding_assessment_jobs_path=(
            comparison_finding_assessment_jobs_path
        ),
        job_final_findings_path=job_final_findings_path,
        job_summaries=tuple(job_summaries),
        consolidation_summaries=tuple(consolidation_summaries),
    )


def _build_pre_final_run_summary(
    *,
    state: (
        AggregateEvidenceComparisonExecution
        | AggregateEvidenceComparisonPreFinalState
    ),
    persisted: _PersistedPreFinalArtifacts,
    stage_input: EvidenceComparisonStageInput,
    run_id: str,
    stage_executor_id: str,
    capability_id: str,
    git_provenance: dict[str, Any] | None,
    run_status: str,
) -> dict[str, Any]:
    participant_inputs = tuple(
        {
            "role_id": participant.role_id,
            "slot_id": participant.slot_id,
            "semantic_module_id": participant.semantic_module_id,
            "declared_output_path": participant.declared_output_path.as_posix(),
        }
        for participant in stage_input.participants
    )

    execution_dependencies = stage_input.execution_dependencies
    assessment_config = getattr(
        execution_dependencies,
        "assessment_llm_execution_config",
        None,
    )
    verification_config = getattr(
        execution_dependencies,
        "verification_llm_execution_config",
        None,
    )
    assessment_second_pass_config = getattr(
        execution_dependencies,
        "assessment_second_pass_llm_execution_config",
        None,
    )
    consolidation_config = getattr(
        execution_dependencies,
        "consolidation_llm_execution_config",
        None,
    )
    llm_execution: dict[str, Any] | None = None
    if (
        assessment_config is not None
        or assessment_second_pass_config is not None
        or verification_config is not None
        or consolidation_config is not None
    ):
        llm_execution = {
            "comparison_finding_assessment": assessment_config,
            "comparison_finding_assessment_second_pass": (
                assessment_second_pass_config
            ),
            "comparison_finding_verification": verification_config,
            "comparison_finding_consolidation": consolidation_config,
        }

    consolidation_summaries = persisted.consolidation_summaries
    payload: dict[str, Any] = {
        "run_id": run_id,
        "stage": EVIDENCE_COMPARISON_STAGE,
        "evidence_scope": CLINICAL_SAFETY_EVIDENCE_SCOPE,
        "specialization": AGGREGATE_COMPARISON_SPECIALIZATION,
        "phase": "evidence_comparison",
        "created_at": utc_now_iso(),
        "git_commit": (git_provenance or {}).get("git_commit"),
        "git_dirty": (git_provenance or {}).get("git_dirty"),
        "git_dirty_checked_at": (git_provenance or {}).get(
            "git_dirty_checked_at"
        ),
        "stage_executor_id": stage_executor_id,
        "status": run_status,
        "run_status": run_status,
        "inputs": {
            "capability_id": capability_id,
            "participants": participant_inputs,
        },
        "outputs": {
            "run_summary": RUN_SUMMARY_FILENAME,
            "aggregate_comparison_evidence": AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
            "comparison_finding_assessment_jobs": (
                COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME
            ),
            "job_final_findings": (
                FINDINGS_FILENAME
                if persisted.job_final_findings_path is not None
                else None
            ),
            "final_findings": None,
            "jobs_dir": COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME,
            "consolidation_dir": (
                COMPARISON_FINDING_CONSOLIDATION_DIRNAME
                if consolidation_summaries
                else None
            ),
        },
        "stats": {
            "planned_job_count": state.planned_job_count,
            "assessment_success_count": state.assessment_success_count,
            "assessment_failed_count": state.assessment_failed_count,
            "assessment_second_pass_success_count": (
                state.second_pass_assessment_success_count
            ),
            "assessment_second_pass_failed_count": (
                state.second_pass_assessment_failed_count
            ),
            "verification_success_count": state.verification_success_count,
            "verification_failed_count": state.verification_failed_count,
            "job_final_finding_count": state.job_final_finding_count,
            "consolidation_execution_count": len(consolidation_summaries),
            "consolidation_success_count": sum(
                summary["status"] == "success"
                for summary in consolidation_summaries
            ),
            "consolidation_failed_count": sum(
                summary["status"] != "success"
                for summary in consolidation_summaries
            ),
            "consolidation_input_finding_count": sum(
                summary["finding_count"] for summary in consolidation_summaries
            ),
            "consolidated_group_count": sum(
                summary["group_count"] for summary in consolidation_summaries
            ),
            "consolidation_alias_qc_mismatch_count": sum(
                summary["alias_qc_mismatch_count"] or 0
                for summary in consolidation_summaries
            ),
        },
        "jobs": list(persisted.job_summaries),
        "consolidation": list(consolidation_summaries),
    }
    if llm_execution is not None:
        payload["llm_execution"] = llm_execution
    return payload


def persist_unified_aggregate_evidence_comparison_execution(
    *,
    execution: AggregateEvidenceComparisonExecution,
    stage_input: EvidenceComparisonStageInput,
    output_dir: Path,
    run_id: str,
    stage_executor_id: str,
    capability_id: str,
    git_provenance: dict[str, Any] | None = None,
) -> AggregateEvidenceComparisonPersistResult:
    """Persist one unified Evidence Comparison stage run from plugin execution."""

    if not isinstance(execution, AggregateEvidenceComparisonExecution):
        raise TypeError(
            "execution must be an AggregateEvidenceComparisonExecution; "
            f"got {type(execution)!r}"
        )

    resolved_output = output_dir.resolve()
    persisted = _persist_pre_final_artifacts(
        state=execution,
        capability_id=capability_id,
        resolved_output=resolved_output,
    )

    final_findings_path = resolved_output / FINAL_FINDINGS_FILENAME
    validate_final_findings(execution.final_findings)
    save_json(final_findings_path, execution.final_findings)

    run_summary_path = resolved_output / RUN_SUMMARY_FILENAME
    run_summary_payload = _build_pre_final_run_summary(
        state=execution,
        persisted=persisted,
        stage_input=stage_input,
        run_id=run_id,
        stage_executor_id=stage_executor_id,
        capability_id=capability_id,
        git_provenance=git_provenance,
        run_status=execution.run_status,
    )
    run_summary_payload["outputs"]["final_findings"] = FINAL_FINDINGS_FILENAME
    run_summary_payload["stats"]["final_finding_count"] = (
        execution.final_finding_count
    )
    run_summary_payload["finalization"] = {
        "status": execution.final_findings["finalization_status"],
        "fallback_comparison_modes": execution.final_findings[
            "fallback_comparison_modes"
        ],
    }

    save_json(
        run_summary_path,
        run_summary_payload,
    )

    return AggregateEvidenceComparisonPersistResult(
        output_dir=resolved_output,
        run_id=run_id,
        aggregate_comparison_evidence_path=(
            persisted.aggregate_comparison_evidence_path
        ),
        comparison_finding_assessment_jobs_path=(
            persisted.comparison_finding_assessment_jobs_path
        ),
        job_final_findings_path=persisted.job_final_findings_path,
        final_findings_path=final_findings_path,
        run_summary_path=run_summary_path,
    )


def persist_aggregate_evidence_comparison_pre_final_failure(
    *,
    pre_final_state: AggregateEvidenceComparisonPreFinalState,
    finalization_error: BaseException,
    stage_input: EvidenceComparisonStageInput,
    output_dir: Path,
    run_id: str,
    stage_executor_id: str,
    capability_id: str,
    git_provenance: dict[str, Any] | None = None,
) -> None:
    """Persist settled pre-final work for a fatal deterministic finalization."""

    if not isinstance(
        pre_final_state,
        AggregateEvidenceComparisonPreFinalState,
    ):
        raise TypeError(
            "pre_final_state must be an AggregateEvidenceComparisonPreFinalState"
        )
    if not isinstance(finalization_error, BaseException):
        raise TypeError("finalization_error must be a BaseException")

    resolved_output = output_dir.resolve()
    resolved_output.mkdir(parents=True, exist_ok=True)
    stale_final_findings_path = resolved_output / FINAL_FINDINGS_FILENAME
    if stale_final_findings_path.exists():
        stale_final_findings_path.unlink()

    persisted = _persist_pre_final_artifacts(
        state=pre_final_state,
        capability_id=capability_id,
        resolved_output=resolved_output,
    )
    run_summary_payload = _build_pre_final_run_summary(
        state=pre_final_state,
        persisted=persisted,
        stage_input=stage_input,
        run_id=run_id,
        stage_executor_id=stage_executor_id,
        capability_id=capability_id,
        git_provenance=git_provenance,
        run_status="failed",
    )
    run_summary_payload.update(
        {
            "failure_reason": "execution_exception",
            "failure_message": str(finalization_error),
        }
    )
    save_json(
        resolved_output / RUN_SUMMARY_FILENAME,
        run_summary_payload,
    )


__all__ = [
    "AGGREGATE_COMPARISON_SPECIALIZATION",
    "CLINICAL_SAFETY_EVIDENCE_SCOPE",
    "COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME",
    "COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME",
    "COMPARISON_FINDING_CONSOLIDATION_DIRNAME",
    "EVIDENCE_COMPARISON_STAGE",
    "RUN_SUMMARY_FILENAME",
    "AggregateEvidenceComparisonPersistResult",
    "persist_aggregate_evidence_comparison_pre_final_failure",
    "persist_unified_aggregate_evidence_comparison_execution",
]
