from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.providers.pricing import estimate_llm_cost


@pytest.mark.parametrize(
    (
        "profile",
        "model",
        "input_price",
        "cache_hit_price",
        "output_price",
    ),
    [
        ("deepseek_v4_flash", "deepseek-v4-flash", 1.0, 0.02, 2.0),
        ("deepseek_v4_pro", "deepseek-v4-pro", 3.0, 0.025, 6.0),
    ],
)
def test_canonical_deepseek_pricing_follows_model_tier(
    profile: str,
    model: str,
    input_price: float,
    cache_hit_price: float,
    output_price: float,
) -> None:
    result = estimate_llm_cost(
        "deepseek",
        model,
        {
            "prompt_tokens": 1_000_000,
            "prompt_cache_hit_tokens": 250_000,
            "completion_tokens": 500_000,
        },
        model_alias=profile,
    )

    assert result is not None
    snapshot = result["cost_estimate"]
    assert snapshot["currency"] == "CNY"
    assert snapshot["input_price_per_1m_tokens"] == pytest.approx(input_price)
    assert snapshot["input_cache_hit_price_per_1m_tokens"] == pytest.approx(
        cache_hit_price
    )
    assert snapshot["output_price_per_1m_tokens"] == pytest.approx(output_price)
    assert snapshot["pricing_source"] == f"PROFILE_PRICE_TABLE.{profile}"
    assert snapshot["usage_basis"] == "derived_cache_miss_from_prompt_tokens"
    assert snapshot["rates_per_million_tokens"] == {
        "cache_hit_input": cache_hit_price,
        "cache_miss_input": input_price,
        "output": output_price,
    }


def test_pricing_prefers_explicit_closed_provider_cache_accounting() -> None:
    result = estimate_llm_cost(
        "deepseek",
        "deepseek-v4-pro",
        {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 500_000,
            "prompt_cache_hit_tokens": 250_000,
            "prompt_cache_miss_tokens": 750_000,
            "cache_usage_source": "provider_reported",
        },
        model_alias="deepseek_v4_pro",
    )

    assert result is not None
    snapshot = result["cost_estimate"]
    assert snapshot["usage_basis"] == "provider_cache_accounting"
    assert snapshot["estimated_cost_cny"] == {
        "cache_hit_input": 0.00625,
        "cache_miss_input": 2.25,
        "output": 3.0,
        "total": 5.25625,
    }


@pytest.mark.parametrize(
    ("model_alias", "model"),
    [
        ("deepseek_chat", "deepseek-v4-flash"),
        ("deepseek_reasoning", "deepseek-v4-flash"),
        ("deepseek-chat", "deepseek-chat"),
        ("deepseek-reasoner", "deepseek-reasoner"),
    ],
)
def test_historical_deepseek_names_resolve_to_flash_pricing(
    model_alias: str,
    model: str,
) -> None:
    result = estimate_llm_cost(
        "deepseek",
        model,
        {"prompt_tokens": 1000, "completion_tokens": 500},
        model_alias=model_alias,
    )

    assert result is not None
    snapshot = result["cost_estimate"]
    assert snapshot["input_price_per_1m_tokens"] == pytest.approx(1.0)
    assert snapshot["output_price_per_1m_tokens"] == pytest.approx(2.0)
    assert snapshot["pricing_source"] == "PROFILE_PRICE_TABLE.deepseek_v4_flash"
