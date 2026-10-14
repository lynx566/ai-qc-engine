"""Unit tests for the production OpenAI client execution kill switch."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.providers.blocked_openai import (
    EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE,
    BlockedOpenAIClient,
)
from llm.providers.openai_client import (
    EXTERNAL_LLM_DISABLED_ENV,
    build_openai_client,
    is_external_llm_execution_disabled,
)


def test_is_external_llm_execution_disabled_truthy_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for value in ("1", "true", "yes", "on", "TRUE"):
        monkeypatch.setenv(EXTERNAL_LLM_DISABLED_ENV, value)
        assert is_external_llm_execution_disabled() is True


def test_is_external_llm_execution_disabled_false_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(EXTERNAL_LLM_DISABLED_ENV, raising=False)
    assert is_external_llm_execution_disabled() is False


def test_build_openai_client_returns_blocked_client_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(EXTERNAL_LLM_DISABLED_ENV, "1")

    client = build_openai_client(
        api_key="test-key",
        base_url="https://example.invalid",
        timeout=1.0,
    )

    assert isinstance(client, BlockedOpenAIClient)
    with pytest.raises(RuntimeError, match=EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE):
        client.chat.completions.create(model="m", messages=[])
