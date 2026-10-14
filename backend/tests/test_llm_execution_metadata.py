"""Tests for normalized LLM execution metadata helpers."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.execution_metadata import (
    llm_effective_execution_fields,
    response_format_applied_from_raw_result,
)
from llm.providers.base import LLMRawResult


def test_response_format_applied_false_by_default() -> None:
    raw = LLMRawResult(provider_name="mock", model="mock", raw_text="{}")
    assert response_format_applied_from_raw_result(raw) is False


def test_response_format_applied_uses_explicit_field_not_capability() -> None:
    raw = LLMRawResult(
        provider_name="mock",
        model="mock",
        raw_text="{}",
        capabilities={"json_object_response_format": True},
        response_format_applied=False,
    )
    assert response_format_applied_from_raw_result(raw) is False


def test_response_format_applied_true_when_explicit_field_set() -> None:
    raw = LLMRawResult(
        provider_name="mock",
        model="mock",
        raw_text="{}",
        capabilities={"json_object_response_format": False},
        response_format_applied=True,
    )
    assert response_format_applied_from_raw_result(raw) is True


def test_llm_effective_execution_fields_from_job_metadata() -> None:
    fields = llm_effective_execution_fields(
        {
            "capabilities": {"json_object_response_format": True},
            "response_format_applied": False,
            "provider_name": "bailian_qwen",
        }
    )
    assert fields == {
        "capabilities": {"json_object_response_format": True},
        "response_format_applied": False,
    }
