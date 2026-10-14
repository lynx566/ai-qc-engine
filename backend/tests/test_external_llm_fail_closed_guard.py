"""Regression tests for the external LLM fail-closed pytest guard."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.execution_configs import (
    LLMExecutionConfig,
    resolve_llm_execution_config,
)
from llm.providers import factory as provider_factory
from llm.providers.bailian import BailianQwenProvider
from llm.providers.blocked_openai import EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE
from llm.providers.deepseek import DeepSeekProvider
from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)
from tests.external_llm_guard import EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE


def test_materialize_llm_provider_is_blocked_during_pytest() -> None:
    from llm.execution_configs import (
        CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
    )

    config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )

    with pytest.raises(RuntimeError, match=EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE):
        provider_factory.build_api_provider(
            llm_profile=config.profile_id,
            thinking=config.thinking,
        )


def test_mock_provider_construction_is_unaffected() -> None:
    provider = OverviewStandaloneMockProvider()
    assert provider.generate.__name__ == "generate"


@pytest.mark.live_llm
def test_live_llm_marker_allows_provider_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr(provider_factory, "load_env", lambda: None)

    provider = provider_factory.build_api_provider(llm_profile="qwen3_7_max")
    assert provider is not None


@pytest.mark.live_llm
def test_live_llm_marker_bypasses_execution_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from llm.providers.blocked_openai import BlockedOpenAIClient
    from llm.providers.openai_client import EXTERNAL_LLM_DISABLED_ENV

    monkeypatch.delenv(EXTERNAL_LLM_DISABLED_ENV, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(provider_factory, "load_env", lambda: None)

    provider = provider_factory.build_api_provider(
        llm_profile="deepseek_v4_flash",
        thinking=False,
    )
    assert isinstance(provider, DeepSeekProvider)
    assert not isinstance(provider._client, BlockedOpenAIClient)


def test_guard_blocks_materialize_execution_config_entrypoint() -> None:
    from llm import execution_configs

    config = LLMExecutionConfig(
        config_id="test_guard",
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=False,
    )

    with pytest.raises(RuntimeError, match=EXTERNAL_LLM_FACTORY_DISABLED_MESSAGE):
        execution_configs.materialize_llm_provider(config)


@pytest.mark.allow_external_provider_factory
def test_factory_marker_allows_real_provider_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(provider_factory, "load_env", lambda: None)

    provider = provider_factory.build_api_provider(
        llm_profile="deepseek_v4_flash",
        thinking=False,
    )

    assert isinstance(provider, DeepSeekProvider)


@pytest.mark.allow_external_provider_factory
@pytest.mark.parametrize(
    ("llm_profile", "expected_type"),
    [
        ("deepseek_v4_flash", DeepSeekProvider),
        ("qwen3_7_max", BailianQwenProvider),
    ],
)
def test_factory_marker_still_blocks_execution_without_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    llm_profile: str,
    expected_type: type,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr(provider_factory, "load_env", lambda: None)

    provider = provider_factory.build_api_provider(
        llm_profile=llm_profile,
        thinking=False,
        response_format=None,
    )
    assert isinstance(provider, expected_type)

    with pytest.raises(RuntimeError, match=EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE):
        provider.generate([{"role": "user", "content": "hi"}])


@pytest.mark.allow_external_provider_factory
def test_factory_marker_allows_fake_client_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeChoice:
        finish_reason = "stop"

        class message:
            content = "{}"

    class _FakeResponse:
        id = "fake-id"
        choices: ClassVar[list[_FakeChoice]] = [_FakeChoice()]
        usage = None
        system_fingerprint = None

    class _FakeCompletions:
        def create(self, **kwargs: Any) -> _FakeResponse:
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(provider_factory, "load_env", lambda: None)
    provider = provider_factory.build_api_provider(
        llm_profile="deepseek_v4_flash",
        thinking=False,
    )
    assert isinstance(provider, DeepSeekProvider)
    provider._client = _FakeClient()  # type: ignore[assignment]

    result = provider.generate([{"role": "user", "content": "hi"}])

    assert captured["model"] == "deepseek-v4-flash"
    assert result.raw_text == "{}"
