"""Persist one Assessment job execution from plugin semantic results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm.debug_artifacts import format_prompt_txt
from llm.execution_metadata import llm_effective_execution_fields
from llm.invocation import serialize_llm_invocations
from llm.model_registry import resolve_llm_selection
from llm.providers.base import request_fingerprint
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentJob,
    serialize_candidate_eligibility_audit,
    serialize_validated_response,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.execution import (
    ComparisonFindingAssessmentJobExecution,
)
from runtime.io import save_json

ACCEPTED_CANDIDATES_FILENAME = "accepted_candidates.json"
CANDIDATE_ELIGIBILITY_DEBUG_FILENAME = "candidate_eligibility.json"


def _serialize_job(job: ComparisonFindingAssessmentJob) -> dict[str, Any]:
    return {
        "comparison_mode_id": job.comparison_mode_id,
        "groups": [
            {
                "group_role": group.group_role,
                "scope_aliases": list(group.scope_aliases),
            }
            for group in job.groups
        ],
    }


def _runtime_request(
    *,
    llm_profile: str | None,
    thinking: bool | None,
    response_format: str | None,
    seed: int,
) -> dict[str, Any] | None:
    if llm_profile is None:
        return None
    selection = resolve_llm_selection(llm_profile, thinking=thinking)
    spec = selection.profile_spec
    return {
        "llm_profile": llm_profile,
        "model_alias": selection.canonical_profile_name,
        "provider": spec.provider,
        "model": spec.model,
        "thinking": selection.thinking,
        "response_format": response_format,
        "seed": seed,
    }


def persist_comparison_finding_assessment_job_execution(
    *,
    execution: ComparisonFindingAssessmentJobExecution,
    job_dir: Path,
    evidence_input: str,
    llm_profile: str | None,
    thinking: bool | None,
    response_format: str | None,
    seed: int,
) -> None:
    """Write one Assessment job directory from plugin semantic execution."""

    job_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = job_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    save_json(job_dir / "job.json", _serialize_job(execution.job))
    (job_dir / "evidence_input.txt").write_text(evidence_input, encoding="utf-8")

    messages = list(execution.messages or ())
    if messages:
        (debug_dir / "prompt.txt").write_text(format_prompt_txt(messages), encoding="utf-8")

    metadata: dict[str, Any] = {
        "frozen_job_index": execution.frozen_job_index,
        "execution_index": execution.execution_index,
        "comparison_mode_id": execution.job.comparison_mode_id,
        "prompt_id": execution.prompt_id,
        "prompt_version": execution.prompt_version,
        "request_fingerprint": request_fingerprint(messages) if messages else None,
    }
    runtime_request = _runtime_request(
        llm_profile=llm_profile,
        thinking=thinking,
        response_format=response_format,
        seed=seed,
    )
    if runtime_request is not None:
        save_json(debug_dir / "runtime_request.json", runtime_request)
        metadata["llm_profile"] = runtime_request["llm_profile"]
        metadata["thinking"] = runtime_request["thinking"]
        metadata["seed"] = runtime_request["seed"]

    llm_invocations = serialize_llm_invocations(execution.llm_invocations)
    last_invocation = dict(llm_invocations[-1]) if llm_invocations else {}
    elapsed_ms = last_invocation.get("elapsed_ms")

    if execution.status == "failed":
        if execution.parse_status == "failed" and execution.raw_response_text is not None:
            (job_dir / "parse_error.txt").write_text(
                f"ValueError: {execution.error_message}\n",
                encoding="utf-8",
            )
        if execution.raw_response_text is not None:
            (job_dir / "result.txt").write_text(
                execution.raw_response_text,
                encoding="utf-8",
            )
            save_json(
                debug_dir / "llm_messages.json",
                {
                    "messages": messages,
                    "raw_response": execution.raw_response_text,
                },
            )
        failure = {
            "status": "failed",
            "error_type": "Exception",
            "error_message": execution.error_message or "assessment job failed",
        }
        if elapsed_ms is not None:
            failure["elapsed_ms"] = elapsed_ms
        save_json(debug_dir / "failure.json", failure)
        save_json(
            debug_dir / "run_metadata.json",
            {
                **metadata,
                **failure,
                "parse_status": execution.parse_status,
                "validation_status": execution.validation_status,
                "llm_invocations": llm_invocations,
                **llm_effective_execution_fields(last_invocation),
            },
        )
        return

    if execution.raw_response_text is not None:
        (job_dir / "result.txt").write_text(execution.raw_response_text, encoding="utf-8")
        save_json(
            debug_dir / "llm_messages.json",
            {
                "messages": messages,
                "raw_response": execution.raw_response_text,
            },
        )

    if execution.validated_response is not None:
        save_json(
            job_dir / "validated_response.json",
            serialize_validated_response(execution.validated_response),
        )
    if execution.accepted_response is not None:
        save_json(
            job_dir / ACCEPTED_CANDIDATES_FILENAME,
            serialize_validated_response(execution.accepted_response),
        )
    if execution.eligibility is not None:
        eligibility_audit = serialize_candidate_eligibility_audit(execution.eligibility)
        save_json(debug_dir / CANDIDATE_ELIGIBILITY_DEBUG_FILENAME, eligibility_audit)
        drop_reason_counts = eligibility_audit["drop_reason_counts"]
    else:
        drop_reason_counts = {}

    save_json(
        debug_dir / "run_metadata.json",
        {
            **metadata,
            "status": "success",
            "parse_status": execution.parse_status,
            "validation_status": execution.validation_status,
            "candidate_count": execution.candidate_count,
            "received_candidate_count": execution.candidate_count,
            "accepted_candidate_count": execution.accepted_candidate_count,
            "dropped_candidate_count": execution.dropped_candidate_count,
            "drop_reason_counts": drop_reason_counts,
            "finding_count": execution.finding_count,
            **({"elapsed_ms": elapsed_ms} if elapsed_ms is not None else {}),
            "llm_invocations": llm_invocations,
            **llm_effective_execution_fields(last_invocation),
        },
    )


__all__ = [
    "ACCEPTED_CANDIDATES_FILENAME",
    "CANDIDATE_ELIGIBILITY_DEBUG_FILENAME",
    "persist_comparison_finding_assessment_job_execution",
]
