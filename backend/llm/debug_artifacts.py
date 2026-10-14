"""In-memory LLM debug artifact builders (persistence owned by runtime operations)."""

from __future__ import annotations

from typing import Any

from llm.providers.base import LLMRawResult
from llm.providers.pricing import normalize_usage_summary


def format_prompt_txt(messages: list[dict[str, str]]) -> str:
    sections: list[str] = []
    for message in messages:
        role = str(message.get("role") or "unknown")
        content = str(message.get("content") or "")
        sections.append(f"[{role}]\n{content}")
    if not sections:
        return ""
    return "\n\n".join(sections) + "\n"


def build_llm_provenance(
    *,
    provider_name: str,
    model_alias: str,
    model: str,
    thinking: bool | None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "provider": provider_name,
        "model_alias": model_alias,
        "model": model,
    }
    if thinking is not None:
        provenance["thinking"] = thinking
    return provenance


def build_provider_request_metadata(
    *,
    model: str,
    model_alias: str,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    return {
        "model": model,
        "model_alias": model_alias,
        "max_tokens": max_tokens,
    }


def build_llm_messages_payload(
    *,
    provider_name: str,
    model: str,
    prompt_name: str,
    prompt_version: str,
    messages: list[dict[str, str]],
    model_alias: str | None = None,
    thinking: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": provider_name,
        "model": model,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "messages": messages,
    }
    if model_alias is not None:
        payload["model_alias"] = model_alias
    if thinking is not None:
        payload["thinking"] = thinking
    return payload


def resolve_debug_profile_identity(debug_run_context: dict[str, Any]) -> dict[str, str]:
    """Return assessment profile identity for debug run_metadata."""
    assessment = debug_run_context.get("assessment_profile_name")
    assessment_name = (
        assessment.strip()
        if isinstance(assessment, str) and assessment.strip()
        else None
    )
    if assessment_name:
        return {"assessment_profile_name": assessment_name}
    return {}


def build_run_metadata(
    debug_run_context: dict[str, Any],
    *,
    raw_result: LLMRawResult,
    llm_raw_result: dict[str, Any],
    elapsed_ms: int,
    prompt_name: str,
    prompt_version: str,
    model_alias: str,
    max_tokens: int | None = None,
    response_normalization: str | None = None,
) -> dict[str, Any]:
    cost_estimate = llm_raw_result.get("cost_estimate")
    legacy_cost = llm_raw_result.get("estimated_cost")
    cost: dict[str, Any] | None
    if isinstance(legacy_cost, dict):
        cost = dict(legacy_cost)
    else:
        cost = None

    llm_provenance = build_llm_provenance(
        provider_name=raw_result.provider_name,
        model_alias=model_alias,
        model=raw_result.model,
        thinking=raw_result.thinking,
    )
    if isinstance(cost_estimate, dict):
        llm_provenance["cost_estimate"] = dict(cost_estimate)

    metadata: dict[str, Any] = {
        "run_context": {
            "tag_output_id": debug_run_context.get("tag_output_id"),
            "doc_id": debug_run_context.get("doc_id"),
            "llm_mode": debug_run_context.get("llm_mode"),
            "source_stage": debug_run_context.get("source_stage"),
            "llm_input_bundle_ref": dict(
                debug_run_context.get("llm_input_bundle_ref") or {}
            ),
            **resolve_debug_profile_identity(debug_run_context),
        },
        "prompt": {
            "name": prompt_name,
            "version": prompt_version,
        },
        "performance": {
            "provider": raw_result.provider_name,
            "model": raw_result.model,
            "elapsed_ms": elapsed_ms,
            "finish_reason": raw_result.finish_reason,
            "usage": raw_result.usage,
            "usage_summary": normalize_usage_summary(raw_result.usage),
            "cost": cost,
            "llm": llm_provenance,
        },
        "tracing": {
            "request_id": raw_result.request_id,
            "api_version": raw_result.api_version,
            "capabilities": raw_result.capabilities,
            "response_format_applied": raw_result.response_format_applied,
        },
        "provider_request": build_provider_request_metadata(
            model=raw_result.model,
            model_alias=model_alias,
            max_tokens=max_tokens,
        ),
    }
    if response_normalization:
        metadata["response_normalization"] = response_normalization
    return metadata


def build_llm_debug_artifacts(
    *,
    messages: list[dict[str, str]],
    profile_prompt_name: str,
    profile_prompt_version: str,
    provider_name: str,
    model: str,
    model_alias: str,
    raw_result: LLMRawResult,
    debug_run_context: dict[str, Any],
    llm_raw_result: dict[str, Any],
    elapsed_ms: int,
    parse_error: str | None,
    max_tokens: int | None = None,
    execution_selection: dict[str, Any] | None = None,
    response_normalization: str | None = None,
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {
        "llm_messages": build_llm_messages_payload(
            provider_name=provider_name,
            model=model,
            prompt_name=profile_prompt_name,
            prompt_version=profile_prompt_version,
            messages=messages,
            model_alias=model_alias,
            thinking=raw_result.thinking,
        ),
        "prompt_txt": format_prompt_txt(messages),
        "raw_text": raw_result.raw_text,
        "parse_error": parse_error or "",
        "run_metadata": build_run_metadata(
            debug_run_context,
            raw_result=raw_result,
            llm_raw_result=llm_raw_result,
            elapsed_ms=elapsed_ms,
            prompt_name=profile_prompt_name,
            prompt_version=profile_prompt_version,
            model_alias=model_alias,
            max_tokens=max_tokens,
            response_normalization=response_normalization,
        ),
    }
    if execution_selection is not None:
        artifacts["run_metadata"]["execution_selection"] = dict(
            execution_selection
        )
    if response_normalization:
        artifacts["response_normalization"] = response_normalization
    return artifacts
