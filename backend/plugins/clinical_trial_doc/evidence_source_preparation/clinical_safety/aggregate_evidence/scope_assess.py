"""Aggregate-evidence scope assessment execution (API + mock)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    ScopeAssessmentContractError,
    build_mock_scope_assessment,
    build_scope_assessment_trace,
    build_scope_assessments_envelope,
    validate_and_canonicalize_scope_assessment_response,
    validate_scope_assessments_envelope,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from llm.debug_artifacts import (
    build_llm_debug_artifacts,
    format_prompt_txt,
)
from llm.execution_errors import APIStructuredResponseError
from llm.invocation import (
    LLMInvocationRecord,
    attach_llm_invocations,
    invoke_llm,
    serialize_llm_invocations,
)
from llm.providers.base import LLMProvider, LLMRawResult
from llm.providers.pricing import estimate_llm_cost

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.registry import (
    resolve_clinical_trial_doc_assessment_profile,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assessment_adapter import (
    ScopeAssessmentEvidence,
    build_scope_assessment_evidence_view,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assessment_semantics import (
    resolve_annotation_qc_fields,
    resolve_product_context_role,
)

FALLBACK_SOURCE_MOCK_SCOPE_ASSESSMENTS = "mock_scope_assessments"
API_RUN_STATUS_COMPLETED_WITH_FALLBACK = "completed_with_api_fallback"


def build_usable_api_result_fields(
    *,
    api_result_usable: bool,
    fallback_used: bool,
    fallback_reason: str | None = None,
    fallback_source: str | None = None,
) -> dict[str, Any]:
    return {
        "api_result_usable": api_result_usable,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "fallback_source": fallback_source,
    }


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text


def _build_llm_raw_result(
    raw_result: LLMRawResult,
    *,
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider_name": raw_result.provider_name,
        "model": raw_result.model,
        "usage": raw_result.usage,
        "request_id": raw_result.request_id,
        "finish_reason": raw_result.finish_reason,
        "capabilities": raw_result.capabilities,
    }
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    cost_result = estimate_llm_cost(
        raw_result.provider_name,
        raw_result.model,
        raw_result.usage,
        model_alias=raw_result.model_alias,
    )
    if cost_result is not None:
        payload["cost_estimate"] = cost_result["cost_estimate"]
        payload["estimated_cost"] = cost_result["cost"]
    return payload


def _resolve_provider_max_tokens(
    provider: LLMProvider,
    *,
    llm_execution_config: dict[str, Any] | None,
) -> int | None:
    if isinstance(llm_execution_config, dict):
        effective = llm_execution_config.get("max_tokens")
        if isinstance(effective, int) and not isinstance(effective, bool):
            return effective
    config = getattr(provider, "_config", None)
    if config is not None:
        return getattr(config, "max_tokens", None)
    return None


def _build_mock_raw_scope_assessments(
    heading_scopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        build_mock_scope_assessment(str(scope.get("scope_id") or ""))
        for scope in heading_scopes
        if isinstance(scope, dict) and str(scope.get("scope_id") or "").strip()
    ]


def _minimal_debug_run_context(
    *,
    assessment_input: dict[str, Any],
    assessment_profile_name: str,
    prompt_name: str,
    prompt_version: str,
    llm_mode: str,
) -> dict[str, Any]:
    return {
        "tag_output_id": f"scope_assessment_{assessment_input.get('llm_input_bundle_id')}",
        "doc_id": assessment_input.get("doc_id"),
        "assessment_profile_name": assessment_profile_name,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "llm_mode": llm_mode,
        "source_stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
    }


def _build_heading_scope_index(
    heading_scopes: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    scope_index: dict[str, dict[str, Any]] = {}
    for scope in heading_scopes:
        if not isinstance(scope, dict):
            continue
        scope_id = str(scope.get("scope_id") or "").strip()
        if scope_id:
            scope_index[scope_id] = scope
    return scope_index


def _remap_model_scope_ids_to_canonical(
    canonical_scope_assessments: Sequence[Mapping[str, Any]],
    *,
    alias_to_scope_id: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Map validated model-local scope_ids (S000x) back to artifact HS scope_ids."""
    if not alias_to_scope_id:
        raise ValueError("alias_to_scope_id is required for scope assessment response remap")

    remapped: list[dict[str, Any]] = []
    for entry in canonical_scope_assessments:
        model_scope_id = str(entry.get("scope_id") or "").strip()
        if not model_scope_id:
            raise ValueError("scope assessment scope_id is required for remap")
        canonical_scope_id = alias_to_scope_id.get(model_scope_id)
        if canonical_scope_id is None:
            raise ValueError(
                f"unknown model-local scope_id {model_scope_id!r} in scope assessment response"
            )
        canonical_token = str(canonical_scope_id).strip()
        if not canonical_token:
            raise ValueError(
                f"empty canonical scope_id mapping for model-local scope_id {model_scope_id!r}"
            )
        remapped_entry = dict(entry)
        remapped_entry["scope_id"] = canonical_token
        remapped.append(remapped_entry)
    return remapped


def _evidence_heading_scope_ids(
    evidence_heading_scopes: Sequence[Mapping[str, Any]],
) -> list[str]:
    return [
        str(scope.get("scope_id") or "").strip()
        for scope in evidence_heading_scopes
        if isinstance(scope, Mapping) and str(scope.get("scope_id") or "").strip()
    ]


def _restore_scope_entries_to_evidence_order(
    entries: Sequence[Mapping[str, Any]],
    *,
    evidence_heading_scopes: Sequence[Mapping[str, Any]],
    entry_label: str,
) -> list[dict[str, Any]]:
    """Restore formal assess outputs to assessment_input.heading_scopes order."""
    canonical_scope_ids = _evidence_heading_scope_ids(evidence_heading_scopes)
    if not canonical_scope_ids:
        raise ValueError("evidence_heading_scopes must include at least one scope_id")

    by_scope_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{entry_label} entries must be objects")
        scope_id = str(entry.get("scope_id") or "").strip()
        if not scope_id:
            raise ValueError(f"{entry_label} scope_id is required")
        if scope_id in by_scope_id:
            raise ValueError(f"duplicate scope_id in {entry_label}: {scope_id!r}")
        by_scope_id[scope_id] = dict(entry)

    entry_scope_ids = set(by_scope_id)
    canonical_set = set(canonical_scope_ids)
    missing = [scope_id for scope_id in canonical_scope_ids if scope_id not in entry_scope_ids]
    if missing:
        raise ValueError(
            f"{entry_label} missing entries for evidence heading scopes: "
            + ", ".join(missing)
        )
    extra = sorted(entry_scope_ids - canonical_set)
    if extra:
        raise ValueError(f"{entry_label} unexpected entries for scope IDs: " + ", ".join(extra))
    if entry_scope_ids != canonical_set:
        raise ValueError(
            f"{entry_label} scope_id set must match evidence_heading_scopes exactly"
        )

    return [by_scope_id[scope_id] for scope_id in canonical_scope_ids]


def _postprocess_validated_scope_assessments(
    *,
    canonical_scope_assessments: list[dict[str, Any]],
    alias_to_scope_id: Mapping[str, str],
    evidence_heading_scopes: list[dict[str, Any]],
    assessment_runtime_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remapped_scope_assessments = _remap_model_scope_ids_to_canonical(
        canonical_scope_assessments,
        alias_to_scope_id=alias_to_scope_id,
    )
    final_scope_assessments, scope_processing = _resolve_scope_assessments_with_shared_postprocess(
        raw_scope_assessments=remapped_scope_assessments,
        heading_scopes=evidence_heading_scopes,
        assessment_runtime_context=assessment_runtime_context,
    )
    return (
        _restore_scope_entries_to_evidence_order(
            final_scope_assessments,
            evidence_heading_scopes=evidence_heading_scopes,
            entry_label="final_scope_assessments",
        ),
        _restore_scope_entries_to_evidence_order(
            scope_processing,
            evidence_heading_scopes=evidence_heading_scopes,
            entry_label="scope_processing",
        ),
    )


def _resolve_scope_assessments_with_shared_postprocess(
    *,
    raw_scope_assessments: list[dict[str, Any]],
    heading_scopes: list[dict[str, Any]],
    assessment_runtime_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    heading_scope_index = _build_heading_scope_index(heading_scopes)

    final_scope_assessments: list[dict[str, Any]] = []
    scope_processing: list[dict[str, Any]] = []
    for raw_scope_assessment in raw_scope_assessments:
        scope_id = str(raw_scope_assessment.get("scope_id") or "").strip()
        scope = heading_scope_index.get(scope_id) or {"scope_id": scope_id, "units": [], "heading_path": []}
        evidence: ScopeAssessmentEvidence = build_scope_assessment_evidence_view(
            scope=scope,
            assessment_runtime_context=assessment_runtime_context,
        )

        llm_item = {
            "product_context_role": raw_scope_assessment.get("product_context_role"),
            "unit_form": raw_scope_assessment.get("unit_form"),
            "safety_role": raw_scope_assessment.get("safety_role"),
            "route_qc": raw_scope_assessment.get("route_qc"),
        }
        product_context_role, product_flags = resolve_product_context_role(
            llm_item.get("product_context_role")
        )
        qc_result = resolve_annotation_qc_fields(llm_item)
        merged_flags = [
            *product_flags,
            *qc_result.validation_flags,
        ]
        final_scope_assessment = {
            "scope_id": scope_id,
            "heading_path": [str(item) for item in (scope.get("heading_path") or [])],
            "source_unit_ids": list(evidence.source_unit_ids),
            "product_context_role": product_context_role,
            "unit_form": qc_result.unit_form,
            "safety_role": qc_result.safety_role,
            "route_qc": qc_result.route_qc,
            "post_llm_validation_flags": list(merged_flags),
        }
        final_scope_assessments.append(final_scope_assessment)
        scope_processing.append(
            {
                "scope_id": scope_id,
                "source_unit_ids": list(evidence.source_unit_ids),
                "source_sentence_ids": list(evidence.source_sentence_ids),
                "source_block_ids": list(evidence.source_block_ids),
                "raw_scope_assessment": dict(raw_scope_assessment),
                "scope_evidence_view": {
                    "candidate_text": evidence.evidence_view.candidate_text,
                    "heading_path": list(evidence.evidence_view.heading_path),
                    "candidate_sentences": [
                        {
                            "sentence_id": str(sentence.get("sentence_id") or ""),
                            "text": str(sentence.get("text") or ""),
                        }
                        for sentence in evidence.evidence_view.candidate_sentences
                    ],
                    "candidate_sentence_count": len(evidence.evidence_view.candidate_sentences),
                    "context_sentence_count": len(evidence.evidence_view.context_sentences),
                },
                "resolved_classification_fields": {
                    "product_context_role": product_context_role,
                },
                "resolved_qc_fields": {
                    "unit_form": qc_result.unit_form,
                    "safety_role": qc_result.safety_role,
                    "route_qc": dict(qc_result.route_qc),
                },
                "classification_validation_flags": list(product_flags),
                "qc_validation_flags": list(qc_result.validation_flags),
                "final_scope_assessment": dict(final_scope_assessment),
                "warnings": list(evidence.warnings),
            }
        )
    return final_scope_assessments, scope_processing


def run_scope_assessment_api(
    *,
    assessment_input: dict[str, Any],
    assessment_runtime_context: dict[str, Any],
    prompt_input_bundle: dict[str, Any],
    alias_to_scope_id: dict[str, str],
    assessment_profile_name: str,
    llm_profile: str,
    provider: LLMProvider,
    llm_execution_config: dict[str, Any] | None = None,
    allow_api_parse_fallback: bool = False,
    assessment_input_path: str | None = None,
    assessment_runtime_context_path: str | None = None,
) -> dict[str, Any]:
    profile = resolve_clinical_trial_doc_assessment_profile(assessment_profile_name)
    heading_scopes = list(prompt_input_bundle.get("heading_scopes") or [])
    evidence_heading_scopes = list(assessment_input.get("heading_scopes") or [])
    if not heading_scopes:
        raise ValueError("prompt_input_bundle.heading_scopes is required for scope assessment")
    if not evidence_heading_scopes:
        raise ValueError("assessment_input.heading_scopes is required for scope evidence")

    messages = profile.build_messages(prompt_input_bundle)
    configured_max_tokens = _resolve_provider_max_tokens(
        provider,
        llm_execution_config=llm_execution_config,
    )

    parse_error: str | None = None
    failure_reason: str | None = None
    failure_message: str | None = None
    first_failure_reason: str | None = None
    retry_attempted = False
    retry_count = 0
    raw_scope_assessments: list[Any] = []
    canonical_scope_assessments: list[dict[str, Any]] = []
    final_scope_assessments: list[dict[str, Any]] = []
    scope_processing: list[dict[str, Any]] = []
    contract_error: str | None = None
    last_raw_result: LLMRawResult | None = None
    last_llm_raw_result: dict[str, Any] | None = None
    last_elapsed_ms = 0
    llm_invocations: list[LLMInvocationRecord] = []

    attempt_messages = list(messages)
    for attempt in range(2):
        outcome = invoke_llm(
            provider,
            attempt_messages,
            execution_config=llm_execution_config,
            # Number real requests across ESP's existing business invocations.
            attempt_index=len(llm_invocations) + 1,
        )
        llm_invocations.extend(outcome.invocations)
        if outcome.error is not None:
            attach_llm_invocations(outcome.error, llm_invocations)
            raise outcome.error
        raw_result = outcome.unwrap()
        elapsed_ms = outcome.invocation.elapsed_ms
        last_raw_result = raw_result
        last_llm_raw_result = _build_llm_raw_result(raw_result, elapsed_ms=elapsed_ms)
        last_elapsed_ms = elapsed_ms
        parse_error = None
        failure_reason = None
        failure_message = None

        finish_reason = str(raw_result.finish_reason or "").strip().lower()
        completion_tokens = (raw_result.usage or {}).get("completion_tokens")
        if finish_reason == "length":
            failure_reason = "api_finish_reason_length"
            failure_message = (
                "LLM response was truncated: finish_reason=length, "
                f"completion_tokens={completion_tokens}. Refusing to parse incomplete JSON."
            )
            parse_error = failure_message
        else:
            clean_text = _extract_json_text(raw_result.raw_text)
            if not clean_text.strip():
                failure_reason = "api_empty_response"
                failure_message = (
                    "LLM response was empty/whitespace. Refusing to produce scope_assessments."
                )
                parse_error = failure_message
            else:
                try:
                    parsed = json.loads(clean_text)
                    if not isinstance(parsed, dict):
                        raise ScopeAssessmentContractError(
                            "invalid_scope_response_root",
                            "LLM response root must be a JSON object",
                        )
                    raw_scope_assessments = list(parsed.get("scope_assessments") or [])
                    canonical_scope_assessments = validate_and_canonicalize_scope_assessment_response(
                        raw_response=parsed,
                        heading_scopes=heading_scopes,
                    )
                    final_scope_assessments, scope_processing = (
                        _postprocess_validated_scope_assessments(
                            canonical_scope_assessments=canonical_scope_assessments,
                            alias_to_scope_id=alias_to_scope_id,
                            evidence_heading_scopes=evidence_heading_scopes,
                            assessment_runtime_context=assessment_runtime_context,
                        )
                    )
                except json.JSONDecodeError as exc:
                    parse_error = f"{type(exc).__name__}: {exc}"
                    failure_reason = "api_parse_error"
                    failure_message = parse_error
                except ScopeAssessmentContractError as exc:
                    contract_error = f"{exc.code}: {exc.message}"
                    parse_error = contract_error
                    failure_reason = "api_schema_validation_error"
                    failure_message = contract_error
                except ValueError as exc:
                    parse_error = f"{type(exc).__name__}: {exc}"
                    failure_reason = "api_schema_validation_error"
                    failure_message = parse_error

        if failure_reason is None:
            break

        if first_failure_reason is None:
            first_failure_reason = failure_reason

        retryable = failure_reason in {"api_parse_error", "api_finish_reason_length"}
        if retryable and attempt == 0:
            retry_attempted = True
            retry_count = 1
            retry_hint = (
                "Previous response was invalid or truncated. Return ONLY one complete, "
                "valid JSON object with top-level scope_assessments. Do not include markdown "
                "fences, commentary, or trailing text."
            )
            attempt_messages = [
                *messages,
                {"role": "system", "content": retry_hint},
            ]
            continue
        break

    assert last_raw_result is not None
    assert last_llm_raw_result is not None

    fallback_used = False
    fallback_source: str | None = None
    api_response_rejected = failure_reason is not None

    if failure_reason is not None and allow_api_parse_fallback:
        fallback_used = True
        fallback_source = FALLBACK_SOURCE_MOCK_SCOPE_ASSESSMENTS
        raw_scope_assessments = _build_mock_raw_scope_assessments(heading_scopes)
        canonical_scope_assessments = validate_and_canonicalize_scope_assessment_response(
            raw_response={"scope_assessments": raw_scope_assessments},
            heading_scopes=heading_scopes,
        )
        final_scope_assessments, scope_processing = _postprocess_validated_scope_assessments(
            canonical_scope_assessments=canonical_scope_assessments,
            alias_to_scope_id=alias_to_scope_id,
            evidence_heading_scopes=evidence_heading_scopes,
            assessment_runtime_context=assessment_runtime_context,
        )
        contract_error = None
        failure_message = None

    api_result: dict[str, Any] = {
        "api_result_usable": failure_reason is None,
        "retry_attempted": retry_attempted,
        "retry_count": retry_count,
        "api_response_rejected": api_response_rejected,
        "fallback_used": fallback_used,
        "fallback_source": fallback_source,
    }
    if first_failure_reason is not None:
        api_result["first_failure_reason"] = first_failure_reason
    if failure_reason is not None:
        api_result["final_failure_reason"] = failure_reason
        api_result["fallback_reason"] = failure_reason
    if failure_reason is None:
        api_result.update(
            build_usable_api_result_fields(
                api_result_usable=True,
                fallback_used=False,
                fallback_reason=None,
                fallback_source=None,
            )
        )

    scope_trace = build_scope_assessment_trace(
        raw_scope_assessments=raw_scope_assessments,
        canonical_scope_assessments=final_scope_assessments,
        scope_processing=scope_processing,
        contract_error=contract_error,
        api_response_rejected=api_response_rejected and not fallback_used,
        fallback_used=fallback_used,
        fallback_source=fallback_source,
    )

    scope_assessments: dict[str, Any] | None = None
    if failure_reason is None or fallback_used:
        scope_assessments = build_scope_assessments_envelope(
            assessment_input=assessment_input,
            assessment_runtime_context=assessment_runtime_context,
            canonical_scope_assessments=final_scope_assessments,
            assessment_profile_name=assessment_profile_name,
            prompt_name=profile.prompt_name,
            prompt_version=profile.prompt_version,
            llm_mode="api",
            llm_profile=llm_profile,
            debug_trace={"api_result": api_result},
            assessment_input_path=assessment_input_path,
            assessment_runtime_context_path=assessment_runtime_context_path,
        )
        scope_assessments["api_result"] = dict(api_result)
        validate_scope_assessments_envelope(scope_assessments)

    debug_run_context = _minimal_debug_run_context(
        assessment_input=assessment_input,
        assessment_profile_name=assessment_profile_name,
        prompt_name=profile.prompt_name,
        prompt_version=profile.prompt_version,
        llm_mode="api",
    )
    llm_debug_artifacts = build_llm_debug_artifacts(
        messages=messages,
        profile_prompt_name=profile.prompt_name,
        profile_prompt_version=profile.prompt_version,
        provider_name=last_raw_result.provider_name,
        model=last_raw_result.model,
        model_alias=llm_profile,
        raw_result=last_raw_result,
        debug_run_context=debug_run_context,
        llm_raw_result=last_llm_raw_result,
        elapsed_ms=last_elapsed_ms,
        parse_error=parse_error,
        max_tokens=configured_max_tokens,
        execution_selection=llm_execution_config,
    )
    llm_debug_artifacts["api_result"] = dict(api_result)
    llm_debug_artifacts["run_metadata"]["api_result"] = dict(api_result)
    llm_debug_artifacts["scope_assessment_trace"] = scope_trace
    llm_debug_artifacts["llm_invocations"] = serialize_llm_invocations(
        llm_invocations
    )
    if failure_reason is not None:
        llm_debug_artifacts["failure_reason"] = failure_reason
        llm_debug_artifacts["run_metadata"]["failure_reason"] = failure_reason
    if failure_message:
        llm_debug_artifacts["failure_message"] = failure_message
        llm_debug_artifacts["run_metadata"]["failure_message"] = failure_message

    run_status = "success"
    if fallback_used:
        run_status = API_RUN_STATUS_COMPLETED_WITH_FALLBACK
    elif failure_reason is not None:
        run_status = "failed"
        error = APIStructuredResponseError(
            failure_message or parse_error or "API scope assessment failure",
            debug_artifacts=llm_debug_artifacts,
            failure_reason=failure_reason,
        )
        attach_llm_invocations(error, llm_invocations)
        raise error

    return {
        "scope_assessments": scope_assessments,
        "llm_debug_artifacts": llm_debug_artifacts,
        "scope_assessment_trace": scope_trace,
        "assessment_profile_name": assessment_profile_name,
        "prompt_name": profile.prompt_name,
        "prompt_version": profile.prompt_version,
        "llm_mode": "api",
        "llm_profile": llm_profile,
        "llm_invocations": tuple(llm_invocations),
        "run_status": run_status,
    }


def run_scope_assessment_mock(
    *,
    assessment_input: dict[str, Any],
    assessment_runtime_context: dict[str, Any],
    prompt_input_bundle: dict[str, Any],
    alias_to_scope_id: dict[str, str],
    assessment_profile_name: str,
    assessment_input_path: str | None = None,
    assessment_runtime_context_path: str | None = None,
) -> dict[str, Any]:
    profile = resolve_clinical_trial_doc_assessment_profile(assessment_profile_name)
    heading_scopes = list(prompt_input_bundle.get("heading_scopes") or [])
    evidence_heading_scopes = list(assessment_input.get("heading_scopes") or [])
    if not heading_scopes:
        raise ValueError("prompt_input_bundle.heading_scopes is required for scope assessment")
    if not evidence_heading_scopes:
        raise ValueError("assessment_input.heading_scopes is required for scope evidence")

    raw_scope_assessments = _build_mock_raw_scope_assessments(heading_scopes)
    canonical_scope_assessments = validate_and_canonicalize_scope_assessment_response(
        raw_response={"scope_assessments": raw_scope_assessments},
        heading_scopes=heading_scopes,
    )
    final_scope_assessments, scope_processing = _postprocess_validated_scope_assessments(
        canonical_scope_assessments=canonical_scope_assessments,
        alias_to_scope_id=alias_to_scope_id,
        evidence_heading_scopes=evidence_heading_scopes,
        assessment_runtime_context=assessment_runtime_context,
    )
    scope_trace = build_scope_assessment_trace(
        raw_scope_assessments=raw_scope_assessments,
        canonical_scope_assessments=final_scope_assessments,
        scope_processing=scope_processing,
    )
    scope_assessments = build_scope_assessments_envelope(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        canonical_scope_assessments=final_scope_assessments,
        assessment_profile_name=assessment_profile_name,
        prompt_name=profile.prompt_name,
        prompt_version=profile.prompt_version,
        llm_mode="mock",
        llm_profile=None,
        assessment_input_path=assessment_input_path,
        assessment_runtime_context_path=assessment_runtime_context_path,
    )
    validate_scope_assessments_envelope(scope_assessments)

    messages = profile.build_messages(prompt_input_bundle)
    llm_debug_artifacts = {
        "llm_messages": {
            "prompt_name": profile.prompt_name,
            "prompt_version": profile.prompt_version,
            "messages": messages,
        },
        "prompt_txt": format_prompt_txt(messages),
        "raw_text": json.dumps(
            {"scope_assessments": raw_scope_assessments},
            ensure_ascii=False,
            indent=2,
        ),
        "parse_error": "",
        "run_metadata": {
            "prompt": {
                "name": profile.prompt_name,
                "version": profile.prompt_version,
            },
            "run_context": {
                "doc_id": assessment_input.get("doc_id"),
                "assessment_profile_name": assessment_profile_name,
                "llm_mode": "mock",
            },
        },
        "scope_assessment_trace": scope_trace,
    }

    return {
        "scope_assessments": scope_assessments,
        "llm_debug_artifacts": llm_debug_artifacts,
        "scope_assessment_trace": scope_trace,
        "assessment_profile_name": assessment_profile_name,
        "prompt_name": profile.prompt_name,
        "prompt_version": profile.prompt_version,
        "llm_mode": "mock",
        "llm_profile": None,
        "llm_invocations": (),
        "run_status": "success",
    }


def run_aggregate_evidence_scope_assess(
    *,
    assessment_input: dict[str, Any],
    assessment_runtime_context: dict[str, Any],
    prompt_input_bundle: dict[str, Any],
    alias_to_scope_id: dict[str, str],
    assessment_profile_name: str,
    llm_mode: str = "mock",
    llm_profile: str | None = None,
    allow_api_parse_fallback: bool = False,
    assessment_input_path: str | None = None,
    assessment_runtime_context_path: str | None = None,
    provider: LLMProvider | None = None,
    llm_execution_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute heading-scope assessment for Aggregate Evidence assess.

    Each heading scope receives one closed clinical-safety assessment artifact.
    Pre-extract hard eligibility remains code-owned route/decompose/profile checks.
    Post-extract semantic eligibility (item safety relevance, matchability) is out of scope.
    """
    if llm_mode == "api":
        if provider is None:
            raise ValueError("provider is required for API scope assessment")
        if not isinstance(llm_profile, str) or not llm_profile.strip():
            raise ValueError("llm_profile is required for API scope assessment")
        return run_scope_assessment_api(
            assessment_input=assessment_input,
            assessment_runtime_context=assessment_runtime_context,
            prompt_input_bundle=prompt_input_bundle,
            alias_to_scope_id=alias_to_scope_id,
            assessment_profile_name=assessment_profile_name,
            llm_profile=llm_profile,
            provider=provider,
            llm_execution_config=llm_execution_config,
            allow_api_parse_fallback=allow_api_parse_fallback,
            assessment_input_path=assessment_input_path,
            assessment_runtime_context_path=assessment_runtime_context_path,
        )
    if llm_mode == "mock":
        return run_scope_assessment_mock(
            assessment_input=assessment_input,
            assessment_runtime_context=assessment_runtime_context,
            prompt_input_bundle=prompt_input_bundle,
            alias_to_scope_id=alias_to_scope_id,
            assessment_profile_name=assessment_profile_name,
            assessment_input_path=assessment_input_path,
            assessment_runtime_context_path=assessment_runtime_context_path,
        )
    raise ValueError(f"unsupported llm_mode {llm_mode!r}")
