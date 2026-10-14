"""Static LLM provider pricing and local cost estimation (CNY)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelPricing:
    """Per-token prices in CNY."""

    input_per_token: float
    output_per_token: float
    input_cache_hit_per_token: float | None = None


# Canonical model profile -> pricing. Values use the existing CNY/token contract.
PROFILE_PRICE_TABLE: dict[str, ModelPricing] = {
    "deepseek_v4_flash": ModelPricing(
        input_per_token=1.0 / 1_000_000,
        output_per_token=2.0 / 1_000_000,
        input_cache_hit_per_token=0.02 / 1_000_000,
    ),
    "deepseek_v4_pro": ModelPricing(
        input_per_token=3.0 / 1_000_000,
        output_per_token=6.0 / 1_000_000,
        input_cache_hit_per_token=0.025 / 1_000_000,
    ),
    "qwen3_5_flash": ModelPricing(
        input_per_token=0.15 / 1_000_000,
        output_per_token=0.60 / 1_000_000,
    ),
}

# Historical model aliases map to the actual canonical model tier, independent of mode.
LEGACY_PROFILE_PRICE_ALIASES: dict[str, str] = {
    "deepseek_chat": "deepseek_v4_flash",
    "deepseek_reasoning": "deepseek_v4_flash",
    "deepseek-chat": "deepseek_v4_flash",
    "deepseek-reasoner": "deepseek_v4_flash",
    "qwen_flash": "qwen3_5_flash",
}

LEGACY_MODEL_PRICE_ALIASES: dict[tuple[str, str], str] = {
    ("deepseek", "deepseek-chat"): "deepseek_v4_flash",
    ("deepseek", "deepseek-reasoner"): "deepseek_v4_flash",
    ("deepseek", "deepseek-v4-flash"): "deepseek_v4_flash",
    ("deepseek", "deepseek-v4-pro"): "deepseek_v4_pro",
    ("bailian_qwen", "qwen3.5-flash"): "qwen3_5_flash",
}

# Backward-compatible export used by older imports/tests.
PRICE_TABLE: dict[tuple[str, str], ModelPricing] = {
    ("deepseek", "deepseek-chat"): PROFILE_PRICE_TABLE["deepseek_v4_flash"],
    ("deepseek", "deepseek-reasoner"): PROFILE_PRICE_TABLE["deepseek_v4_flash"],
    ("bailian_qwen", "qwen3.5-flash"): PROFILE_PRICE_TABLE["qwen3_5_flash"],
}


def _coerce_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _coerce_optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return max(result, 0)


def _normalize_usage_tokens(
    usage: dict[str, Any],
) -> tuple[int, int, int | None, int | None]:
    """Return input, output, and explicitly available cache hit/miss counters."""
    input_tokens = _coerce_int(
        usage.get("prompt_tokens")
        if usage.get("prompt_tokens") is not None
        else usage.get("input_tokens")
    )
    output_tokens = _coerce_int(
        usage.get("completion_tokens")
        if usage.get("completion_tokens") is not None
        else usage.get("output_tokens")
    )
    cache_hit_tokens = _coerce_optional_int(
        usage.get("prompt_cache_hit_tokens")
        if usage.get("prompt_cache_hit_tokens") is not None
        else usage.get("cache_hit_tokens")
    )
    cache_miss_tokens = _coerce_optional_int(
        usage.get("prompt_cache_miss_tokens")
        if usage.get("prompt_cache_miss_tokens") is not None
        else usage.get("cache_miss_tokens")
    )
    return input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens


def normalize_usage_summary(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return normalized usage counters for run_summary/debug artifacts."""
    if not usage:
        return None

    input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens = (
        _normalize_usage_tokens(usage)
    )
    if input_tokens == 0 and output_tokens == 0:
        return None

    summary: dict[str, Any] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    if cache_hit_tokens is not None:
        summary["cache_hit_tokens"] = cache_hit_tokens
        if input_tokens:
            summary["cache_hit_rate_pct"] = round(
                100.0 * cache_hit_tokens / input_tokens,
                2,
            )
    if cache_miss_tokens is not None:
        summary["cache_miss_tokens"] = cache_miss_tokens
    if usage.get("cache_usage_source") is not None:
        summary["cache_usage_source"] = usage["cache_usage_source"]
    return summary


def _price_per_million_tokens(price_per_token: float) -> float:
    return round(price_per_token * 1_000_000, 6)


def _resolve_pricing_with_source(
    provider_name: str,
    model: str,
    *,
    model_alias: str | None = None,
) -> tuple[ModelPricing | None, str | None]:
    if model_alias:
        alias = str(model_alias)
        alias = LEGACY_PROFILE_PRICE_ALIASES.get(alias, alias)
        pricing = PROFILE_PRICE_TABLE.get(alias)
        if pricing is not None:
            return pricing, f"PROFILE_PRICE_TABLE.{alias}"

    legacy_alias = LEGACY_MODEL_PRICE_ALIASES.get((str(provider_name), str(model)))
    if legacy_alias is not None:
        pricing = PROFILE_PRICE_TABLE.get(legacy_alias)
        if pricing is not None:
            return pricing, f"PROFILE_PRICE_TABLE.{legacy_alias}"

    legacy_pricing = PRICE_TABLE.get((str(provider_name), str(model)))
    if legacy_pricing is not None:
        mapped_alias = LEGACY_MODEL_PRICE_ALIASES.get((str(provider_name), str(model)))
        if mapped_alias is not None:
            return legacy_pricing, f"PROFILE_PRICE_TABLE.{mapped_alias}"
        return legacy_pricing, f"PRICE_TABLE.{provider_name}.{model}"

    return None, None


def build_cost_estimate_snapshot(
    pricing: ModelPricing,
    *,
    pricing_source: str,
    estimated_cost: float,
    cache_hit_input_cost: float,
    cache_miss_input_cost: float,
    output_cost: float,
    usage_basis: str,
) -> dict[str, Any]:
    """Immutable pricing snapshot captured at API call time."""
    snapshot: dict[str, Any] = {
        "currency": "CNY",
        "input_price_per_1m_tokens": _price_per_million_tokens(pricing.input_per_token),
        "output_price_per_1m_tokens": _price_per_million_tokens(
            pricing.output_per_token
        ),
        "estimated_cost": estimated_cost,
        "estimated_cost_cny": {
            "cache_hit_input": cache_hit_input_cost,
            "cache_miss_input": cache_miss_input_cost,
            "output": output_cost,
            "total": estimated_cost,
        },
        "pricing_model": pricing_source.rsplit(".", 1)[-1],
        "pricing_source": pricing_source,
        "usage_basis": usage_basis,
        "rates_per_million_tokens": {
            "cache_miss_input": _price_per_million_tokens(pricing.input_per_token),
            "output": _price_per_million_tokens(pricing.output_per_token),
        },
    }
    if pricing.input_cache_hit_per_token is not None:
        snapshot["input_cache_hit_price_per_1m_tokens"] = _price_per_million_tokens(
            pricing.input_cache_hit_per_token
        )
        snapshot["rates_per_million_tokens"]["cache_hit_input"] = (
            _price_per_million_tokens(pricing.input_cache_hit_per_token)
        )
    return snapshot


def _build_legacy_cost_record(
    *,
    cost_estimate: dict[str, Any],
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int,
) -> dict[str, Any]:
    """Backward-compatible cost payload kept under performance.cost."""
    legacy: dict[str, Any] = {
        "currency": cost_estimate["currency"],
        "estimated_cost_cny": cost_estimate["estimated_cost"],
        "estimated_cost": cost_estimate["estimated_cost"],
        "cost_source": "local_estimation",
        "pricing_source": cost_estimate["pricing_source"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    if cache_hit_tokens:
        legacy["cache_hit_tokens"] = cache_hit_tokens
        if input_tokens:
            legacy["cache_hit_rate_pct"] = round(
                100.0 * cache_hit_tokens / input_tokens,
                2,
            )
    return legacy


def _cache_pricing_basis(
    usage: dict[str, Any],
    *,
    input_tokens: int,
    cache_hit_tokens: int | None,
    cache_miss_tokens: int | None,
) -> tuple[int, int, str]:
    source = usage.get("cache_usage_source")
    if source == "unavailable":
        return 0, input_tokens, "cache_accounting_unavailable_standard_input_rate"
    if cache_hit_tokens is not None and cache_miss_tokens is not None:
        if cache_hit_tokens + cache_miss_tokens != input_tokens:
            return 0, input_tokens, "cache_closure_mismatch_standard_input_rate"
        if source == "provider_reported":
            basis = "provider_cache_accounting"
        elif source == "partially_derived":
            basis = "partially_derived_cache_accounting"
        elif source == "compatibility_fallback":
            basis = "compatibility_fallback_cache_accounting"
        else:
            basis = "explicit_cache_accounting"
        return cache_hit_tokens, cache_miss_tokens, basis
    if cache_hit_tokens is not None and cache_hit_tokens <= input_tokens:
        return (
            cache_hit_tokens,
            input_tokens - cache_hit_tokens,
            "derived_cache_miss_from_prompt_tokens",
        )
    if cache_miss_tokens is not None and cache_miss_tokens <= input_tokens:
        return (
            input_tokens - cache_miss_tokens,
            cache_miss_tokens,
            "derived_cache_hit_from_prompt_tokens",
        )
    return 0, input_tokens, "no_cache_accounting_standard_input_rate"


def estimate_llm_cost(
    provider_name: str,
    model: str,
    usage: dict[str, Any] | None,
    *,
    model_alias: str | None = None,
) -> dict[str, Any] | None:
    """
    Estimate call cost from static profile pricing.

    Returns a dict with:
    - ``cost_estimate``: immutable pricing snapshot for run artifacts
    - ``cost``: legacy-compatible record for ``performance.cost``

    Returns ``None`` when usage is missing, empty, or the model has no price entry.
    """
    if not usage:
        return None

    pricing, pricing_source = _resolve_pricing_with_source(
        provider_name,
        model,
        model_alias=model_alias,
    )
    if pricing is None or pricing_source is None:
        return None

    input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens = (
        _normalize_usage_tokens(usage)
    )
    if input_tokens == 0 and output_tokens == 0:
        return None

    if pricing.input_cache_hit_per_token is not None:
        priced_hit_tokens, priced_miss_tokens, usage_basis = _cache_pricing_basis(
            usage,
            input_tokens=input_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
        )
        raw_cache_hit_input_cost = priced_hit_tokens * pricing.input_cache_hit_per_token
        raw_cache_miss_input_cost = priced_miss_tokens * pricing.input_per_token
        cache_hit_input_cost = round(raw_cache_hit_input_cost, 6)
        cache_miss_input_cost = round(raw_cache_miss_input_cost, 6)
        input_cost = raw_cache_hit_input_cost + raw_cache_miss_input_cost
        cache_hit_tokens = priced_hit_tokens
    else:
        input_cost = input_tokens * pricing.input_per_token
        cache_hit_input_cost = 0.0
        cache_miss_input_cost = round(input_cost, 6)
        usage_basis = "standard_input_output_tokens"
        cache_hit_tokens = 0

    raw_output_cost = output_tokens * pricing.output_per_token
    output_cost = round(raw_output_cost, 6)
    estimated_cost = round(input_cost + raw_output_cost, 6)

    cost_estimate = build_cost_estimate_snapshot(
        pricing,
        pricing_source=pricing_source,
        estimated_cost=estimated_cost,
        cache_hit_input_cost=cache_hit_input_cost,
        cache_miss_input_cost=cache_miss_input_cost,
        output_cost=output_cost,
        usage_basis=usage_basis,
    )
    legacy_cost = _build_legacy_cost_record(
        cost_estimate=cost_estimate,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_hit_tokens=cache_hit_tokens,
    )
    return {
        "cost_estimate": cost_estimate,
        "cost": legacy_cost,
    }


def _resolve_pricing(
    provider_name: str,
    model: str,
    *,
    model_alias: str | None = None,
) -> ModelPricing | None:
    pricing, _ = _resolve_pricing_with_source(
        provider_name,
        model,
        model_alias=model_alias,
    )
    return pricing
