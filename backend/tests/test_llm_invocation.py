"""Tests for one-call LLM invocation telemetry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.invocation import invoke_llm
from llm.providers.base import LLMRawResult


class _SuccessfulProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        assert messages == [{"role": "user", "content": "hello"}]
        return LLMRawResult(
            provider_name="test_provider",
            model="test-model",
            raw_text="{}",
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            request_id="request-123",
            api_version="api-v1",
            finish_reason="stop",
            capabilities={"json_object_response_format": True},
            response_format_applied=True,
            model_alias="test-profile",
            thinking=False,
        )


class _FailingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise TimeoutError("provider timed out")


def test_successful_invocation_records_timing_and_raw_result_metadata() -> None:
    outcome = invoke_llm(
        _SuccessfulProvider(),
        [{"role": "user", "content": "hello"}],
        execution_config={
            "config_id": "test-config",
            "profile_id": "test-profile",
            "response_format": "json_object",
            "thinking": False,
        },
        attempt_index=1,
    )

    assert outcome.error is None
    assert outcome.raw_result is not None
    record = outcome.invocation.to_dict()
    assert record["status"] == "success"
    assert isinstance(record["elapsed_ms"], int)
    assert record["elapsed_ms"] >= 0
    assert record["provider"] == "test_provider"
    assert record["model"] == "test-model"
    assert record["config_id"] == "test-config"
    assert record["profile_id"] == "test-profile"
    assert record["attempt_index"] == 1
    assert record["request_id"] == "request-123"
    assert record["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }
    assert record["api_version"] == "api-v1"
    assert record["finish_reason"] == "stop"
    assert record["response_format"] == "json_object"
    assert record["response_format_applied"] is True
    assert record["thinking"] is False
    assert record["error_type"] is None
    assert record["error_message"] is None


def test_failed_invocation_records_elapsed_and_original_error() -> None:
    outcome = invoke_llm(
        _FailingProvider(),
        [{"role": "user", "content": "hello"}],
        execution_config={
            "config_id": "test-config",
            "profile_id": "qwen3_7_plus_2026_05_26",
            "response_format": None,
            "thinking": True,
        },
        attempt_index=2,
    )

    assert isinstance(outcome.error, TimeoutError)
    assert outcome.raw_result is None
    record = outcome.invocation.to_dict()
    assert record["status"] == "failed"
    assert isinstance(record["elapsed_ms"], int)
    assert record["elapsed_ms"] >= 0
    assert record["provider"] == "bailian_qwen"
    assert record["model"] == "qwen3.7-plus-2026-05-26"
    assert record["config_id"] == "test-config"
    assert record["profile_id"] == "qwen3_7_plus_2026_05_26"
    assert record["attempt_index"] == 2
    assert record["request_id"] is None
    assert record["usage"] is None
    assert record["error_type"] == "TimeoutError"
    assert record["error_message"] == "provider timed out"

    with pytest.raises(TimeoutError, match="provider timed out"):
        outcome.unwrap()
