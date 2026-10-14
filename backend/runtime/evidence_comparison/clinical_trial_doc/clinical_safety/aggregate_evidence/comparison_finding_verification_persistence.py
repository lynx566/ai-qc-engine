"""Persist one Verification job execution from plugin semantic results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm.debug_artifacts import format_prompt_txt
from llm.execution_metadata import llm_effective_execution_fields
from llm.invocation import serialize_llm_invocations
from llm.model_registry import resolve_llm_selection
from llm.providers.base import request_fingerprint
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    ADDITIONAL_FINDING_ELIGIBILITY_DEBUG_FILENAME,
    serialize_additional_finding_eligibility_audit,
    serialize_validated_response,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification.execution import (
    ComparisonFindingVerificationJobExecution,
)
from runtime.io import save_json

VALIDATED_RESPONSE_FILENAME = "validated_response.json"
VERIFICATION_INPUT_FILENAME = "verification_input.txt"


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


def _serialize_job_input(
    execution: ComparisonFindingVerificationJobExecution,
) -> dict[str, Any]:
    verification_input = execution.verification_input
    return {
        "frozen_job_index": verification_input.frozen_job_index,
        "comparison_mode_id": verification_input.comparison_mode_id,
        "comparison_groups": [
            dict(group) for group in verification_input.comparison_groups
        ],
        "input_finding_count": len(verification_input.findings),
    }


def persist_comparison_finding_verification_job_execution(
    *,
    execution: ComparisonFindingVerificationJobExecution,
    job_dir: Path,
    llm_profile: str | None,
    thinking: bool | None,
    response_format: str | None,
    seed: int,
) -> None:
    """Write one Verification job directory from plugin semantic execution."""

    job_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = job_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    save_json(job_dir / "job.json", _serialize_job_input(execution))
    (job_dir / VERIFICATION_INPUT_FILENAME).write_text(
        execution.verification_input.user_input_text,
        encoding="utf-8",
    )

    messages = list(execution.messages or ())
    if messages:
        (debug_dir / "prompt.txt").write_text(format_prompt_txt(messages), encoding="utf-8")

    metadata: dict[str, Any] = {
        "frozen_job_index": execution.frozen_job_index,
        "execution_index": execution.execution_index,
        "comparison_mode_id": execution.comparison_mode_id,
        "prompt_id": execution.prompt_id,
        "prompt_version": execution.prompt_version,
        "request_fingerprint": request_fingerprint(messages) if messages else None,
        "input_finding_count": execution.input_finding_count,
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
            "error_message": execution.error_message or "verification job failed",
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
            job_dir / VALIDATED_RESPONSE_FILENAME,
            serialize_validated_response(execution.validated_response),
        )
    if execution.additional_eligibility is not None:
        save_json(
            debug_dir / ADDITIONAL_FINDING_ELIGIBILITY_DEBUG_FILENAME,
            serialize_additional_finding_eligibility_audit(
                execution.additional_eligibility
            ),
        )

    save_json(
        debug_dir / "run_metadata.json",
        {
            **metadata,
            "status": "success",
            "parse_status": execution.parse_status,
            "validation_status": execution.validation_status,
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
            **({"elapsed_ms": elapsed_ms} if elapsed_ms is not None else {}),
            "llm_invocations": llm_invocations,
            **llm_effective_execution_fields(last_invocation),
        },
    )


__all__ = [
    "VALIDATED_RESPONSE_FILENAME",
    "VERIFICATION_INPUT_FILENAME",
    "persist_comparison_finding_verification_job_execution",
]
