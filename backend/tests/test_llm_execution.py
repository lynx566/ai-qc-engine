"""Unit tests for runtime LLM execution metadata reconstruction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.providers.base import LLMRawResult
from runtime.llm_execution import (
    llm_execution_from_debug_artifacts,
    llm_execution_from_raw_result,
    llm_execution_from_raw_results,
)


def test_llm_execution_from_raw_result_preserves_actual_provider_metadata() -> None:
    result = LLMRawResult(
        provider_name="deepseek",
        model="deepseek-v4-pro",
        raw_text="{}",
        usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        request_id="request-1",
        api_version="api-1",
        finish_reason="stop",
        model_alias="deepseek_v4_pro",
        thinking=True,
    )

    execution = llm_execution_from_raw_result(result, elapsed_ms=25)

    assert execution == {
        "llm_provider": "deepseek",
        "llm_model": "deepseek-v4-pro",
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "model_alias": "deepseek_v4_pro",
            "thinking": True,
        },
        "elapsed_ms": 25,
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        "finish_reason": "stop",
        "request_id": "request-1",
        "api_version": "api-1",
    }


def test_llm_execution_from_raw_results_aggregates_present_usage_fields() -> None:
    results = [
        LLMRawResult(
            provider_name="deepseek",
            model="deepseek-v4-pro",
            raw_text="{}",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
                "prompt_cache_hit_tokens": 2,
                "prompt_cache_miss_tokens": 8,
                "cache_usage_source": "provider_reported",
            },
            model_alias="deepseek_v4_pro",
            thinking=True,
        ),
        LLMRawResult(
            provider_name="deepseek",
            model="deepseek-v4-pro",
            raw_text="{}",
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 8,
                "total_tokens": 28,
                "prompt_cache_hit_tokens": 6,
                "prompt_cache_miss_tokens": 14,
                "cache_usage_source": "provider_reported",
            },
            model_alias="deepseek_v4_pro",
            thinking=True,
        ),
    ]

    execution = llm_execution_from_raw_results(
        results,
        call_count=2,
        elapsed_ms=50,
        all_calls_completed=True,
    )

    assert execution is not None
    assert execution["call_count"] == 2
    assert execution["all_calls_completed"] is True
    assert execution["elapsed_ms"] == 50
    assert execution["llm"]["model_alias"] == "deepseek_v4_pro"
    assert execution["usage"] == {
        "prompt_tokens": 30,
        "completion_tokens": 12,
        "total_tokens": 42,
        "prompt_cache_hit_tokens": 8,
        "prompt_cache_miss_tokens": 22,
        "prompt_cache_accounted_tokens": 30,
        "prompt_cache_unaccounted_tokens": 0,
        "prompt_cache_closure_satisfied": True,
        "cache_usage_source": "provider_reported",
        "cache_usage_source_counts": {"provider_reported": 2},
    }
    assert execution["cost_estimate"]["usage_basis"] == ("provider_cache_accounting")


def test_llm_execution_from_raw_results_rejects_conflicting_identity() -> None:
    results = [
        LLMRawResult(provider_name="a", model="m", raw_text="{}"),
        LLMRawResult(provider_name="b", model="m", raw_text="{}"),
    ]
    with pytest.raises(ValueError, match="conflicting provider/model identity"):
        llm_execution_from_raw_results(
            results,
            call_count=2,
            all_calls_completed=True,
        )


def test_llm_execution_preserves_cache_mismatch_as_open_accounting() -> None:
    result = LLMRawResult(
        provider_name="deepseek",
        model="deepseek-v4-pro",
        model_alias="deepseek_v4_pro",
        raw_text="{}",
        usage={
            "prompt_tokens": 1000,
            "completion_tokens": 10,
            "total_tokens": 1010,
            "prompt_cache_hit_tokens": 300,
            "prompt_cache_miss_tokens": 800,
            "cache_usage_source": "provider_reported",
        },
    )

    execution = llm_execution_from_raw_results(
        [result], call_count=1, all_calls_completed=True
    )

    assert execution is not None
    usage = execution["usage"]
    assert usage["prompt_cache_accounted_tokens"] == 1100
    assert usage["prompt_cache_unaccounted_tokens"] == -100
    assert usage["prompt_cache_closure_satisfied"] is False
    assert execution["cost_estimate"]["usage_basis"] == (
        "cache_closure_mismatch_standard_input_rate"
    )


def test_llm_execution_without_cache_accounting_remains_valid() -> None:
    result = LLMRawResult(
        provider_name="other",
        model="other-model",
        raw_text="{}",
        usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    )

    execution = llm_execution_from_raw_results(
        [result], call_count=1, all_calls_completed=True
    )

    assert execution is not None
    assert execution["usage"]["prompt_tokens"] == 7
    assert execution["usage"]["prompt_cache_hit_tokens"] is None
    assert execution["usage"]["prompt_cache_closure_satisfied"] is None
    assert execution["usage"]["cache_usage_source"] == "unavailable"
    assert "cost_estimate" not in execution


@pytest.mark.parametrize("debug_artifacts", [None, {}])
def test_llm_execution_from_debug_artifacts_empty_returns_none(
    debug_artifacts: dict | None,
) -> None:
    assert llm_execution_from_debug_artifacts(debug_artifacts) is None


def test_llm_execution_from_raw_result_omits_unspecified_thinking() -> None:
    result = LLMRawResult(
        provider_name="bailian_qwen",
        model="qwen3.7-max",
        raw_text="answer",
        model_alias="qwen3_7_max",
        thinking=None,
    )

    execution = llm_execution_from_raw_result(result)

    assert execution is not None
    assert "thinking" not in execution["llm"]
    assert "reasoning" not in execution["llm"]


def test_llm_execution_from_debug_artifacts_maps_run_metadata() -> None:
    debug_artifacts = {
        "run_metadata": {
            "prompt": {"name": "scope_prompt", "version": "1.2.0"},
            "performance": {
                "elapsed_ms": 42,
                "provider": "legacy_provider",
                "model": "legacy_model",
                "usage_summary": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
                "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "model_alias": "deepseek_v4_flash",
                    "reasoning": False,
                    "cost_estimate": {
                        "currency": "CNY",
                        "estimated_cost": 0.001,
                    },
                },
            },
            "provider_request": {"max_tokens": 10000, "model_alias": "deepseek_v4_flash"},
            "api_result": {"api_result_usable": True, "fallback_used": False},
        }
    }

    execution = llm_execution_from_debug_artifacts(debug_artifacts)
    assert execution is not None
    assert execution["llm_provider"] == "deepseek"
    assert execution["llm_model"] == "deepseek-v4-flash"
    assert execution["prompt_name"] == "scope_prompt"
    assert execution["prompt_version"] == "1.2.0"
    assert execution["elapsed_ms"] == 42
    assert execution["llm"] == {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "model_alias": "deepseek_v4_flash",
        "reasoning": False,
    }
    assert execution["usage"] == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    assert execution["cost_estimate"]["estimated_cost"] == pytest.approx(0.001)
    assert execution["provider_request"] == {
        "max_tokens": 10000,
        "model_alias": "deepseek_v4_flash",
    }
    assert execution["api_result"] == {
        "api_result_usable": True,
        "fallback_used": False,
    }


def test_llm_execution_from_debug_artifacts_includes_error_fields() -> None:
    debug_artifacts = {
        "parse_error": "invalid json",
        "failure_reason": "api_schema_validation_error",
        "failure_message": "schema mismatch",
        "api_result": {"api_result_usable": False, "fallback_used": True},
        "run_metadata": {
            "performance": {
                "llm": {"provider": "deepseek", "model": "deepseek-v4-flash"},
            }
        },
    }

    execution = llm_execution_from_debug_artifacts(debug_artifacts)
    assert execution is not None
    assert execution["parse_error"] == "invalid json"
    assert execution["failure_reason"] == "api_schema_validation_error"
    assert execution["failure_message"] == "schema mismatch"
    assert execution["api_result"]["api_result_usable"] is False
    assert execution["api_result"]["fallback_used"] is True
