"""Aggregate Evidence Runtime-owned LLM execution-selection tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as execution_selection
from llm.model_registry import RetiredLLMProfileError


@pytest.mark.parametrize(
    (
        "requested_profile",
        "requested_thinking",
        "canonical_profile",
        "provider_name",
        "model",
        "effective_thinking",
    ),
    [
        ("deepseek_v4_flash", False, "deepseek_v4_flash", "deepseek", "deepseek-v4-flash", False),
        ("deepseek_v4_flash", True, "deepseek_v4_flash", "deepseek", "deepseek-v4-flash", True),
        ("deepseek_v4_pro", False, "deepseek_v4_pro", "deepseek", "deepseek-v4-pro", False),
        ("deepseek_v4_pro", True, "deepseek_v4_pro", "deepseek", "deepseek-v4-pro", True),
        ("qwen3_7_max", None, "qwen3_7_max", "bailian_qwen", "qwen3.7-max", None),
        ("qwen3_7_max", False, "qwen3_7_max", "bailian_qwen", "qwen3.7-max", False),
        ("qwen3_7_max", True, "qwen3_7_max", "bailian_qwen", "qwen3.7-max", True),
    ],
)
def test_runtime_selection_reaches_provider_factory(
    monkeypatch: pytest.MonkeyPatch,
    requested_profile: str,
    requested_thinking: bool | None,
    canonical_profile: str,
    provider_name: str,
    model: str,
    effective_thinking: bool | None,
) -> None:
    captured: dict[str, Any] = {}
    provider = object()

    def fake_build_api_provider(**kwargs: Any) -> object:
        captured.update(kwargs)
        return provider

    monkeypatch.setattr(
        execution_selection,
        "build_api_provider",
        fake_build_api_provider,
    )

    execution = execution_selection.build_aggregate_evidence_llm_execution(
        llm_profile=requested_profile,
        thinking=requested_thinking,
    )
    metadata = execution.metadata()

    assert execution.provider is provider
    assert captured == {
        "llm_profile": requested_profile,
        "thinking": requested_thinking,
        "response_format": "json_object",
        "seed": None,
    }
    assert metadata == {
        "requested_profile": requested_profile,
        "requested_thinking": requested_thinking,
        "canonical_profile": canonical_profile,
        "provider": provider_name,
        "model": model,
        "thinking": effective_thinking,
        "response_format": "json_object",
        "max_tokens": 10000 if canonical_profile == "deepseek_v4_flash" else (
            16000 if canonical_profile == "deepseek_v4_pro" else None
        ),
        "seed": None,
    }


@pytest.mark.parametrize(
    ("retired_profile", "replacement_fragment"),
    [
        ("deepseek_chat", "deepseek_v4_flash --no-thinking"),
        ("deepseek_reasoning", "deepseek_v4_flash --thinking"),
        ("deepseek-chat", "deepseek_v4_flash --no-thinking"),
        ("deepseek-reasoner", "deepseek_v4_flash --thinking"),
        ("qwen_flash", "qwen3_5_flash"),
    ],
)
def test_runtime_selection_rejects_retired_profiles(
    monkeypatch: pytest.MonkeyPatch,
    retired_profile: str,
    replacement_fragment: str,
) -> None:
    build_called = False

    def fake_build_api_provider(**_kwargs: Any) -> object:
        nonlocal build_called
        build_called = True
        return object()

    monkeypatch.setattr(
        execution_selection,
        "build_api_provider",
        fake_build_api_provider,
    )

    with pytest.raises(RetiredLLMProfileError, match="is retired") as exc:
        execution_selection.build_aggregate_evidence_llm_execution(
            llm_profile=retired_profile,
            thinking=None,
        )

    assert replacement_fragment in str(exc.value)
    assert build_called is False
