from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from core.serialization import stable_json_dumps

CACHE_USAGE_PROVIDER_REPORTED = "provider_reported"
CACHE_USAGE_PARTIALLY_DERIVED = "partially_derived"
CACHE_USAGE_COMPATIBILITY_FALLBACK = "compatibility_fallback"
CACHE_USAGE_UNAVAILABLE = "unavailable"


def request_fingerprint(messages: list[dict[str, str]]) -> str:
    """Return a deterministic identity for one provider-neutral message request."""
    digest = hashlib.sha256(stable_json_dumps(messages).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def prompt_cache_usage_closure(
    *,
    prompt_tokens: int | None,
    prompt_cache_hit_tokens: int | None,
    prompt_cache_miss_tokens: int | None,
    cache_usage_source: str,
) -> dict[str, Any]:
    """Build nullable cache-accounting diagnostics without inventing counters."""
    accounted = (
        prompt_cache_hit_tokens + prompt_cache_miss_tokens
        if prompt_cache_hit_tokens is not None and prompt_cache_miss_tokens is not None
        else None
    )
    unaccounted = (
        prompt_tokens - accounted
        if prompt_tokens is not None and accounted is not None
        else None
    )
    closure_satisfied = (
        prompt_tokens == accounted
        if prompt_tokens is not None and accounted is not None
        else None
    )
    return {
        "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": prompt_cache_miss_tokens,
        "prompt_cache_accounted_tokens": accounted,
        "prompt_cache_unaccounted_tokens": unaccounted,
        "prompt_cache_closure_satisfied": closure_satisfied,
        "cache_usage_source": cache_usage_source,
    }


@dataclass(frozen=True)
class LLMRawResult:
    provider_name: str
    model: str
    raw_text: str
    usage: dict | None = None
    request_id: str | None = None
    api_version: str | None = None
    finish_reason: str | None = None
    capabilities: dict[str, bool] | None = None
    response_format_applied: bool = False
    model_alias: str | None = None
    thinking: bool | None = None


class LLMProvider(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult: ...
