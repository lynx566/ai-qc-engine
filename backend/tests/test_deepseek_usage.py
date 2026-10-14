from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.providers.deepseek import _normalize_deepseek_usage


def _usage(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "prompt_tokens": 1000,
        "completion_tokens": 100,
        "total_tokens": 1100,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_deepseek_official_cache_fields_close_provider_accounting() -> None:
    usage = _normalize_deepseek_usage(
        _usage(prompt_cache_hit_tokens=300, prompt_cache_miss_tokens=700)
    )

    assert usage["prompt_cache_hit_tokens"] == 300
    assert usage["prompt_cache_miss_tokens"] == 700
    assert usage["prompt_cache_accounted_tokens"] == 1000
    assert usage["prompt_cache_unaccounted_tokens"] == 0
    assert usage["prompt_cache_closure_satisfied"] is True
    assert usage["cache_usage_source"] == "provider_reported"


def test_deepseek_official_fields_take_precedence_over_nested_cached_tokens() -> None:
    usage = _normalize_deepseek_usage(
        _usage(
            prompt_cache_hit_tokens=300,
            prompt_cache_miss_tokens=700,
            prompt_tokens_details=SimpleNamespace(cached_tokens=999),
        )
    )

    assert usage["prompt_cache_hit_tokens"] == 300
    assert usage["cache_usage_source"] == "provider_reported"


def test_deepseek_nested_cached_tokens_is_a_marked_compatibility_fallback() -> None:
    usage = _normalize_deepseek_usage(
        _usage(prompt_tokens_details=SimpleNamespace(cached_tokens=250))
    )

    assert usage["prompt_cache_hit_tokens"] == 250
    assert usage["prompt_cache_miss_tokens"] == 750
    assert usage["cache_usage_source"] == "compatibility_fallback"
    assert usage["prompt_cache_closure_satisfied"] is True


def test_deepseek_derives_one_missing_official_component_and_marks_it() -> None:
    usage = _normalize_deepseek_usage(_usage(prompt_cache_hit_tokens=400))

    assert usage["prompt_cache_hit_tokens"] == 400
    assert usage["prompt_cache_miss_tokens"] == 600
    assert usage["cache_usage_source"] == "partially_derived"


def test_deepseek_unavailable_cache_fields_remain_nullable() -> None:
    usage = _normalize_deepseek_usage(_usage())

    assert usage["prompt_cache_hit_tokens"] is None
    assert usage["prompt_cache_miss_tokens"] is None
    assert usage["prompt_cache_accounted_tokens"] is None
    assert usage["prompt_cache_unaccounted_tokens"] is None
    assert usage["prompt_cache_closure_satisfied"] is None
    assert usage["cache_usage_source"] == "unavailable"


def test_deepseek_cache_mismatch_is_not_silently_closed() -> None:
    usage = _normalize_deepseek_usage(
        _usage(prompt_cache_hit_tokens=300, prompt_cache_miss_tokens=800)
    )

    assert usage["prompt_cache_accounted_tokens"] == 1100
    assert usage["prompt_cache_unaccounted_tokens"] == -100
    assert usage["prompt_cache_closure_satisfied"] is False
