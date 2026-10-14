"""LLM debug run_metadata profile identity contract tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.providers.base import LLMRawResult
from llm.debug_artifacts import (
    build_llm_debug_artifacts,
    build_run_metadata,
    resolve_debug_profile_identity,
)

_CANONICAL = "clinical_safety_aggregate_heading_scope_assessment_zh"


def test_resolve_debug_profile_identity_active_payload() -> None:
    fields = resolve_debug_profile_identity(
        {"assessment_profile_name": _CANONICAL},
    )
    assert fields == {"assessment_profile_name": _CANONICAL}


def test_resolve_debug_profile_identity_omits_unknown_profile() -> None:
    assert resolve_debug_profile_identity({}) == {}


def test_build_run_metadata_active_assessment_does_not_emit_null_tag_profile_name() -> None:
    metadata = build_run_metadata(
        {
            "tag_output_id": "scope_assessment_test",
            "doc_id": "doc_test",
            "assessment_profile_name": _CANONICAL,
            "llm_mode": "api",
            "source_stage": "evidence_source_preparation",
        },
        raw_result=LLMRawResult(
            provider_name="fake",
            model="fake-model",
            raw_text="{}",
            usage={},
            request_id="req_test",
            finish_reason="stop",
            model_alias="deepseek_v4_flash",
            thinking=False,
        ),
        llm_raw_result={},
        elapsed_ms=1,
        prompt_name=_CANONICAL,
        prompt_version="0.2.1",
        model_alias="deepseek_v4_flash",
    )
    run_context = metadata["run_context"]
    assert run_context["assessment_profile_name"] == _CANONICAL
    assert "tag_profile_name" not in run_context


@pytest.mark.parametrize("response_format_applied", [False, True])
def test_build_run_metadata_preserves_capability_and_applied_independently(
    response_format_applied: bool,
) -> None:
    metadata = build_run_metadata(
        {},
        raw_result=LLMRawResult(
            provider_name="fake",
            model="fake-model",
            raw_text="{}",
            capabilities={"json_object_response_format": True},
            response_format_applied=response_format_applied,
        ),
        llm_raw_result={},
        elapsed_ms=1,
        prompt_name="test_prompt",
        prompt_version="1.0.0",
        model_alias="fake-model",
    )

    assert metadata["tracing"]["capabilities"] == {
        "json_object_response_format": True,
    }
    assert (
        metadata["tracing"]["response_format_applied"]
        is response_format_applied
    )


def test_qwen_unspecified_thinking_omits_false_from_debug_artifacts() -> None:
    raw_result = LLMRawResult(
        provider_name="bailian_qwen",
        model="qwen3.7-max",
        raw_text="answer",
        usage={},
        model_alias="qwen3_7_max",
        thinking=None,
    )
    artifacts = build_llm_debug_artifacts(
        messages=[{"role": "user", "content": "hi"}],
        profile_prompt_name="test_prompt",
        profile_prompt_version="1.0.0",
        provider_name="bailian_qwen",
        model="qwen3.7-max",
        model_alias="qwen3_7_max",
        raw_result=raw_result,
        debug_run_context={"tag_output_id": "t1", "doc_id": "d1"},
        llm_raw_result={},
        elapsed_ms=1,
        parse_error=None,
        execution_selection={
            "requested_profile": "qwen3_7_max",
            "requested_thinking": None,
            "canonical_profile": "qwen3_7_max",
            "provider": "bailian_qwen",
            "model": "qwen3.7-max",
            "thinking": None,
        },
    )

    assert artifacts["run_metadata"]["execution_selection"]["thinking"] is None
    llm_block = artifacts["run_metadata"]["performance"]["llm"]
    assert "thinking" not in llm_block
    assert "reasoning" not in llm_block
    assert "thinking" not in artifacts["llm_messages"]
    assert "reasoning" not in artifacts["llm_messages"]


@pytest.mark.parametrize("thinking", [True, False])
def test_qwen_explicit_thinking_preserved_in_debug_artifacts(
    thinking: bool,
) -> None:
    raw_result = LLMRawResult(
        provider_name="bailian_qwen",
        model="qwen3.7-max",
        raw_text="answer",
        usage={},
        model_alias="qwen3_7_max",
        thinking=thinking,
    )
    artifacts = build_llm_debug_artifacts(
        messages=[{"role": "user", "content": "hi"}],
        profile_prompt_name="test_prompt",
        profile_prompt_version="1.0.0",
        provider_name="bailian_qwen",
        model="qwen3.7-max",
        model_alias="qwen3_7_max",
        raw_result=raw_result,
        debug_run_context={"tag_output_id": "t1", "doc_id": "d1"},
        llm_raw_result={},
        elapsed_ms=1,
        parse_error=None,
    )

    assert artifacts["run_metadata"]["performance"]["llm"]["thinking"] is thinking
    assert artifacts["llm_messages"]["thinking"] is thinking
