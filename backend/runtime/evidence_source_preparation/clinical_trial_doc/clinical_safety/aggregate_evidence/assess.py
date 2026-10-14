# ruff: noqa: TRY004
"""Aggregate Evidence assess phase dev/debug harness: load inputs and persist outputs.

Phase dev/debug harness — not a canonical runtime stage.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    load_assessment_runtime_context,
    resolve_assessment_runtime_context_path,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    validate_assessment_input,
)
from llm.execution_errors import APIStructuredResponseError
from llm.invocation import llm_invocations_from_exception, serialize_llm_invocations
from llm.providers.base import LLMProvider
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    ASSESS_HEADING_SCOPES_OPERATION,
)
from runtime.assessment_registry import (
    normalize_assessment_profile_name,
    resolve_assessment_profile,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    persist_assess_execution,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.results import (
    AssessResult,
)
from runtime.io import load_json, save_json
from runtime.llm_execution import llm_execution_from_debug_artifacts
from runtime.run_layout import require_evidence_form_id_segment
from runtime.run_summaries import build_aggregate_evidence_assess_run_summary

# Backward-compatible re-export for callers importing result type from this module.
__all__ = [
    "AssessResult",
    "run_assess",
    "run_assess_with_error_handling",
]


def _resolve_assessment_profile_name(
    assessment_input: dict[str, Any],
    *,
    override: str | None,
) -> str:
    if override is not None:
        return resolve_assessment_profile(override)
    assessment_profile_ref = assessment_input.get("assessment_profile_ref")
    if not assessment_profile_ref:
        raise ValueError(
            "assessment_input missing assessment_profile_ref; pass --assessment-profile to override"
        )
    return resolve_assessment_profile(normalize_assessment_profile_name(str(assessment_profile_ref)))


def run_assess(
    *,
    run_assess_phase: Callable[..., Any],
    assessment_input_path: Path | str,
    output_dir: Path | str,
    run_id: str,
    evidence_form_id: str,
    assessment_profile_name: str | None = None,
    llm_mode: str = "mock",
    llm_profile: str | None = None,
    provider: LLMProvider | None = None,
    llm_execution_config: dict[str, Any] | None = None,
    allow_api_parse_fallback: bool = False,
    git_provenance: dict[str, str | bool | None] | None = None,
    llm_execution: dict[str, Any] | None = None,
    llm_debug_artifacts: dict[str, Any] | None = None,
    assessment_input_rel_path: str | None = None,
    assessment_runtime_context_path: Path | str | None = None,
    assessment_runtime_context_rel_path: str | None = None,
) -> AssessResult:
    """Execute Aggregate Evidence assess and write scope_assessments.json."""
    require_evidence_form_id_segment(evidence_form_id)
    resolved_input = Path(assessment_input_path).resolve()
    out_dir = Path(output_dir).resolve()

    assessment_input = load_json(resolved_input)
    if not isinstance(assessment_input, dict):
        raise ValueError("assessment_input must be a JSON object")
    validate_assessment_input(assessment_input)

    resolved_runtime_context_path = resolve_assessment_runtime_context_path(
        resolved_input,
        override_path=assessment_runtime_context_path,
    )
    assessment_runtime_context = load_assessment_runtime_context(
        resolved_input,
        override_path=resolved_runtime_context_path,
    )

    profile_name = _resolve_assessment_profile_name(
        assessment_input,
        override=assessment_profile_name,
    )

    input_rel = assessment_input_rel_path or resolved_input.name
    runtime_context_rel = assessment_runtime_context_rel_path
    if runtime_context_rel is None:
        runtime_context_rel = resolved_runtime_context_path.name

    assess_execution = run_assess_phase(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        assessment_profile_name=profile_name,
        llm_mode=llm_mode,
        llm_profile=llm_profile,
        provider=provider,
        llm_execution_config=llm_execution_config,
        assessment_input_ref=input_rel,
        assessment_runtime_context_ref=runtime_context_rel,
        allow_api_parse_fallback=allow_api_parse_fallback,
    )

    effective_llm_execution = llm_execution
    if effective_llm_execution is None and llm_mode == "api":
        effective_llm_execution = llm_execution_from_debug_artifacts(
            assess_execution.llm_debug_artifacts
        )

    return persist_assess_execution(
        execution=assess_execution,
        output_dir=out_dir,
        run_id=run_id,
        assessment_input=assessment_input,
        assessment_input_path=resolved_input,
        llm_mode=llm_mode,
        effective_llm_execution=effective_llm_execution,
        git_provenance=git_provenance,
    )


def run_assess_with_error_handling(
    *,
    run_assess_phase: Callable[..., Any],
    assessment_input_path: Path | str,
    output_dir: Path | str,
    run_id: str,
    evidence_form_id: str,
    assessment_profile_name: str | None = None,
    llm_mode: str = "mock",
    llm_profile: str | None = None,
    provider: LLMProvider | None = None,
    llm_execution_config: dict[str, Any] | None = None,
    allow_api_parse_fallback: bool = False,
    git_provenance: dict[str, str | bool | None] | None = None,
    llm_execution: dict[str, Any] | None = None,
    assessment_runtime_context_path: Path | str | None = None,
) -> AssessResult:
    """Like :func:`run_assess` but writes failure summary on API errors."""
    require_evidence_form_id_segment(evidence_form_id)
    resolved_input = Path(assessment_input_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    assessment_input = load_json(resolved_input)
    try:
        return run_assess(
            run_assess_phase=run_assess_phase,
            assessment_input_path=resolved_input,
            output_dir=out_dir,
            run_id=run_id,
            evidence_form_id=evidence_form_id,
            assessment_profile_name=assessment_profile_name,
            llm_mode=llm_mode,
            llm_profile=llm_profile,
            provider=provider,
            llm_execution_config=llm_execution_config,
            allow_api_parse_fallback=allow_api_parse_fallback,
            git_provenance=git_provenance,
            llm_execution=llm_execution,
            assessment_runtime_context_path=assessment_runtime_context_path,
        )
    except APIStructuredResponseError as exc:
        profile_name = _resolve_assessment_profile_name(
            assessment_input,
            override=assessment_profile_name,
        )
        effective_llm_execution = llm_execution
        if effective_llm_execution is None and llm_mode == "api":
            effective_llm_execution = llm_execution_from_debug_artifacts(
                exc.debug_artifacts
            )
        summary = build_aggregate_evidence_assess_run_summary(
            run_id=run_id,
            assessment_input=assessment_input,
            assessment_input_path=resolved_input,
            scope_assessments_path=None,
            scope_assessments=None,
            scope_assessment_review_path=None,
            scope_assessment_review=None,
            assessment_profile_name=profile_name,
            llm_mode=llm_mode,
            zone_key=str(assessment_input.get("zone_key") or ""),
            phase=EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
            completed_operation=ASSESS_HEADING_SCOPES_OPERATION,
            git_provenance=git_provenance,
            llm_execution=effective_llm_execution,
            run_status="failed",
            error={
                "type": type(exc).__name__,
                "message": str(exc),
                "reason": exc.failure_reason,
            },
            scope_assessment_trace=(
                exc.debug_artifacts.get("scope_assessment_trace")
                if isinstance(exc.debug_artifacts, dict)
                else None
            ),
            llm_invocations=serialize_llm_invocations(
                llm_invocations_from_exception(exc)
            ),
        )
        save_json(out_dir / "run_summary.json", summary)
        raise
