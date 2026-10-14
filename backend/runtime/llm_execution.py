"""Runtime helpers for reconstructing LLM execution metadata from debug artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Real
from typing import Any

from llm.providers.base import (
    CACHE_USAGE_PARTIALLY_DERIVED,
    CACHE_USAGE_PROVIDER_REPORTED,
    CACHE_USAGE_UNAVAILABLE,
    LLMRawResult,
    prompt_cache_usage_closure,
)
from llm.providers.pricing import estimate_llm_cost


def _numeric_usage_value(usage: dict[str, Any], field: str) -> int | float | None:
    value = usage.get(field)
    if isinstance(value, Real) and not isinstance(value, bool):
        return value
    return None


def _normalized_call_cache_usage(usage: dict[str, Any]) -> dict[str, Any]:
    prompt = _numeric_usage_value(usage, "prompt_tokens")
    hit = _numeric_usage_value(usage, "prompt_cache_hit_tokens")
    miss = _numeric_usage_value(usage, "prompt_cache_miss_tokens")
    source = str(usage.get("cache_usage_source") or CACHE_USAGE_UNAVAILABLE)
    if prompt is not None:
        if hit is not None and miss is None and hit <= prompt:
            miss = prompt - hit
            if source != "compatibility_fallback":
                source = CACHE_USAGE_PARTIALLY_DERIVED
        elif miss is not None and hit is None and miss <= prompt:
            hit = prompt - miss
            source = CACHE_USAGE_PARTIALLY_DERIVED
    if hit is not None and miss is not None and "cache_usage_source" not in usage:
        source = CACHE_USAGE_PROVIDER_REPORTED
    return prompt_cache_usage_closure(
        prompt_tokens=int(prompt) if prompt is not None else None,
        prompt_cache_hit_tokens=int(hit) if hit is not None else None,
        prompt_cache_miss_tokens=int(miss) if miss is not None else None,
        cache_usage_source=source,
    )


def llm_execution_from_raw_result(
    raw_result: LLMRawResult | None,
    *,
    elapsed_ms: int | None = None,
) -> dict[str, Any] | None:
    """Build provider-neutral execution metadata from an actual provider result."""
    if raw_result is None:
        return None

    llm: dict[str, Any] = {
        "provider": raw_result.provider_name,
        "model": raw_result.model,
    }
    if raw_result.model_alias is not None:
        llm["model_alias"] = raw_result.model_alias
    if raw_result.thinking is not None:
        llm["thinking"] = raw_result.thinking

    execution: dict[str, Any] = {
        "llm_provider": raw_result.provider_name,
        "llm_model": raw_result.model,
        "llm": llm,
    }
    if elapsed_ms is not None:
        execution["elapsed_ms"] = elapsed_ms
    if raw_result.usage is not None:
        execution["usage"] = dict(raw_result.usage)
    if raw_result.finish_reason is not None:
        execution["finish_reason"] = raw_result.finish_reason
    if raw_result.request_id is not None:
        execution["request_id"] = raw_result.request_id
    if raw_result.api_version is not None:
        execution["api_version"] = raw_result.api_version
    return execution


def llm_execution_from_raw_results(
    raw_results: Sequence[LLMRawResult],
    *,
    call_count: int,
    elapsed_ms: int | None = None,
    all_calls_completed: bool,
) -> dict[str, Any] | None:
    """Aggregate neutral metadata for one operation containing multiple calls."""
    if (
        isinstance(call_count, bool)
        or not isinstance(call_count, int)
        or call_count < 0
    ):
        raise ValueError("call_count must be a non-negative integer")
    if call_count < len(raw_results):
        raise ValueError("call_count must cover every successful raw result")
    if call_count == 0:
        return None

    execution: dict[str, Any] = {
        "call_count": call_count,
        "all_calls_completed": bool(all_calls_completed),
    }
    if elapsed_ms is not None:
        execution["elapsed_ms"] = elapsed_ms

    if raw_results:
        first = raw_results[0]
        identity = (
            first.provider_name,
            first.model,
            first.model_alias,
            first.thinking,
        )
        for result in raw_results[1:]:
            current = (
                result.provider_name,
                result.model,
                result.model_alias,
                result.thinking,
            )
            if current != identity:
                raise ValueError(
                    "cannot aggregate LLM calls with conflicting provider/model identity"
                )

        llm: dict[str, Any] = {
            "provider": first.provider_name,
            "model": first.model,
        }
        if first.model_alias is not None:
            llm["model_alias"] = first.model_alias
        if first.thinking is not None:
            llm["thinking"] = first.thinking
        execution.update(
            {
                "llm_provider": first.provider_name,
                "llm_model": first.model,
                "llm": llm,
            }
        )

    usage: dict[str, Any] = {}
    for field in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ):
        values = [
            result.usage[field]
            for result in raw_results
            if result.usage is not None
            and field in result.usage
            and isinstance(result.usage[field], Real)
            and not isinstance(result.usage[field], bool)
        ]
        if values:
            usage[field] = sum(values)
    if raw_results:
        call_cache = [
            _normalized_call_cache_usage(result.usage or {}) for result in raw_results
        ]
        hit_values = [value["prompt_cache_hit_tokens"] for value in call_cache]
        miss_values = [value["prompt_cache_miss_tokens"] for value in call_cache]
        aggregate_hit = (
            sum(hit_values) if all(v is not None for v in hit_values) else None
        )
        aggregate_miss = (
            sum(miss_values) if all(v is not None for v in miss_values) else None
        )
        source_counts: dict[str, int] = {}
        for value in call_cache:
            source = value["cache_usage_source"]
            source_counts[source] = source_counts.get(source, 0) + 1
        if CACHE_USAGE_UNAVAILABLE in source_counts:
            aggregate_source = CACHE_USAGE_UNAVAILABLE
        elif CACHE_USAGE_PARTIALLY_DERIVED in source_counts:
            aggregate_source = CACHE_USAGE_PARTIALLY_DERIVED
        elif "compatibility_fallback" in source_counts:
            aggregate_source = "compatibility_fallback"
        else:
            aggregate_source = CACHE_USAGE_PROVIDER_REPORTED
        usage.update(
            prompt_cache_usage_closure(
                prompt_tokens=(
                    int(usage["prompt_tokens"])
                    if "prompt_tokens" in usage
                    and all(
                        result.usage is not None
                        and _numeric_usage_value(result.usage, "prompt_tokens")
                        is not None
                        for result in raw_results
                    )
                    else None
                ),
                prompt_cache_hit_tokens=aggregate_hit,
                prompt_cache_miss_tokens=aggregate_miss,
                cache_usage_source=aggregate_source,
            )
        )
        usage["cache_usage_source_counts"] = source_counts
    if usage:
        execution["usage"] = usage
    if raw_results and usage:
        first = raw_results[0]
        pricing = estimate_llm_cost(
            first.provider_name,
            first.model,
            usage,
            model_alias=first.model_alias,
        )
        if pricing is not None:
            execution["cost_estimate"] = pricing["cost_estimate"]
            execution["estimated_cost"] = pricing["cost"]
    return execution


def llm_execution_from_debug_artifacts(
    debug_artifacts: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not debug_artifacts:
        return None
    metadata = debug_artifacts.get("run_metadata") or {}
    performance = metadata.get("performance") or {}
    prompt = metadata.get("prompt") or {}
    llm_block = performance.get("llm") or {}
    execution: dict[str, Any] = {
        "llm_provider": llm_block.get("provider") or performance.get("provider"),
        "llm_model": llm_block.get("model") or performance.get("model"),
        "prompt_name": prompt.get("name"),
        "prompt_version": prompt.get("version"),
        "elapsed_ms": performance.get("elapsed_ms"),
    }
    if llm_block:
        llm_without_cost = {
            key: value for key, value in llm_block.items() if key != "cost_estimate"
        }
        if llm_without_cost:
            execution["llm"] = llm_without_cost

    execution_selection = metadata.get("execution_selection")
    if isinstance(execution_selection, dict):
        execution["execution_selection"] = dict(execution_selection)

    usage_summary = performance.get("usage_summary")
    if usage_summary:
        execution["usage"] = usage_summary

    cost_estimate = llm_block.get("cost_estimate")
    if cost_estimate:
        execution["cost_estimate"] = cost_estimate

    parse_error = debug_artifacts.get("parse_error")
    if parse_error:
        execution["parse_error"] = parse_error
    response_normalization = debug_artifacts.get("response_normalization")
    if not response_normalization:
        response_normalization = metadata.get("response_normalization")
    if response_normalization:
        execution["response_normalization"] = response_normalization
    cost = performance.get("cost")
    if cost:
        execution["estimated_cost"] = cost
    api_result = debug_artifacts.get("api_result") or metadata.get("api_result")
    if isinstance(api_result, dict):
        execution["api_result"] = dict(api_result)
    provider_request = metadata.get("provider_request")
    if isinstance(provider_request, dict):
        execution["provider_request"] = dict(provider_request)
    failure_reason = debug_artifacts.get("failure_reason") or metadata.get(
        "failure_reason"
    )
    if failure_reason:
        execution["failure_reason"] = failure_reason
    failure_message = debug_artifacts.get("failure_message") or metadata.get(
        "failure_message"
    )
    if failure_message:
        execution["failure_message"] = failure_message
    return execution
