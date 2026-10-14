from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.model_registry import RetiredLLMProfileError, UnknownLLMProfileError
from llm.providers.bailian import BailianQwenProvider
from llm.providers.capabilities import ProviderCapabilities
from llm.providers.config import (
    ProviderConfig,
    load_provider_config_from_profile,
)
from llm.providers.deepseek import DeepSeekProvider
from llm.providers.factory import build_api_provider

pytestmark = pytest.mark.allow_external_provider_factory


@pytest.mark.parametrize(
    ("profile", "thinking", "model", "expected_thinking", "max_tokens"),
    [
        ("deepseek_v4_flash", False, "deepseek-v4-flash", False, 10000),
        ("deepseek_v4_flash", True, "deepseek-v4-flash", True, 10000),
        ("deepseek_v4_pro", False, "deepseek-v4-pro", False, 16000),
        ("deepseek_v4_pro", True, "deepseek-v4-pro", True, 16000),
    ],
)
def test_provider_config_supports_deepseek_model_thinking_matrix(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    thinking: bool,
    model: str,
    expected_thinking: bool,
    max_tokens: int,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = load_provider_config_from_profile(profile, thinking=thinking)

    assert config.provider_name == "deepseek"
    assert config.model_alias == profile
    assert config.model == model
    assert config.thinking is expected_thinking
    assert config.max_tokens == max_tokens
    assert config.response_format == "json_object"


@pytest.mark.parametrize(
    ("profile", "replacement_fragment"),
    [
        ("deepseek_chat", "deepseek_v4_flash --no-thinking"),
        ("deepseek_reasoning", "deepseek_v4_flash --thinking"),
        ("deepseek-chat", "deepseek_v4_flash --no-thinking"),
        ("deepseek-reasoner", "deepseek_v4_flash --thinking"),
        ("qwen_flash", "qwen3_5_flash"),
    ],
)
def test_provider_config_rejects_retired_profiles(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    replacement_fragment: str,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    with pytest.raises(RetiredLLMProfileError, match="is retired") as exc:
        load_provider_config_from_profile(profile)
    assert replacement_fragment in str(exc.value)


def test_factory_rejects_retired_profile_without_constructing_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    build_called = False

    def _unexpected_provider(_config: ProviderConfig) -> ProviderConfig:
        nonlocal build_called
        build_called = True
        return _config

    monkeypatch.setattr(
        "llm.providers.deepseek.DeepSeekProvider",
        _unexpected_provider,
    )

    with pytest.raises(RetiredLLMProfileError, match="deepseek_reasoning is retired"):
        build_api_provider(llm_profile="deepseek_reasoning", thinking=False)

    assert build_called is False


def test_factory_can_build_v4_pro_with_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    monkeypatch.setattr(
        "llm.providers.deepseek.DeepSeekProvider",
        lambda config: config,
    )

    config = build_api_provider(llm_profile="deepseek_v4_pro", thinking=True)

    assert isinstance(config, ProviderConfig)
    assert config.model_alias == "deepseek_v4_pro"
    assert config.model == "deepseek-v4-pro"
    assert config.thinking is True
    assert config.max_tokens == 16000
    assert config.response_format == "json_object"


def test_factory_propagates_none_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    monkeypatch.setattr(
        "llm.providers.deepseek.DeepSeekProvider",
        lambda config: config,
    )

    config = build_api_provider(
        llm_profile="deepseek_v4_pro",
        response_format=None,
    )

    assert isinstance(config, ProviderConfig)
    assert config.response_format is None


def test_default_factory_selection_remains_flash_non_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    monkeypatch.setattr(
        "llm.providers.deepseek.DeepSeekProvider",
        lambda config: config,
    )

    config = build_api_provider()

    assert isinstance(config, ProviderConfig)
    assert config.model_alias == "deepseek_v4_flash"
    assert config.model == "deepseek-v4-flash"
    assert config.thinking is False
    assert config.max_tokens == 10000
    assert config.response_format == "json_object"


@pytest.mark.parametrize(
    ("profile", "model", "thinking", "max_tokens"),
    [
        ("deepseek_v4_flash", "deepseek-v4-flash", False, 10000),
        ("deepseek_v4_flash", "deepseek-v4-flash", True, 10000),
        ("deepseek_v4_pro", "deepseek-v4-pro", False, 16000),
        ("deepseek_v4_pro", "deepseek-v4-pro", True, 16000),
    ],
)
def test_deepseek_request_matrix(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    model: str,
    thinking: bool,
    max_tokens: int,
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
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile=profile,
        thinking=thinking,
    )
    assert isinstance(provider, DeepSeekProvider)
    provider._client = _FakeClient()  # type: ignore[assignment]

    result = provider.generate([{"role": "user", "content": "hi"}])

    assert captured["model"] == model
    assert captured["extra_body"] == {
        "thinking": {"type": "enabled" if thinking else "disabled"}
    }
    assert captured["max_tokens"] == max_tokens
    assert captured["response_format"] == {"type": "json_object"}
    if thinking:
        assert captured["reasoning_effort"] == "high"
    else:
        assert "reasoning_effort" not in captured
    assert result.thinking is thinking
    assert result.capabilities is not None
    assert result.capabilities["thinking_mode"] is thinking
    assert "reasoning_mode" not in result.capabilities


def test_deepseek_explicit_json_object_response_format_is_applied(
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
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile="deepseek_v4_pro",
        response_format="json_object",
    )
    assert isinstance(provider, DeepSeekProvider)
    provider._client = _FakeClient()  # type: ignore[assignment]

    provider.generate([{"role": "user", "content": "hi"}])

    assert captured["response_format"] == {"type": "json_object"}


def test_deepseek_none_response_format_omits_request_kwarg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeChoice:
        finish_reason = "stop"

        class message:
            content = "free text"

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
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile="deepseek_v4_pro",
        response_format=None,
    )
    assert isinstance(provider, DeepSeekProvider)
    provider._client = _FakeClient()  # type: ignore[assignment]

    provider.generate([{"role": "user", "content": "hi"}])

    assert "response_format" not in captured


@pytest.mark.parametrize(
    ("response_format", "supports_json_object", "expect_response_format_kwarg"),
    [
        (None, False, False),
        (None, True, False),
        ("json_object", False, False),
        ("json_object", True, True),
    ],
)
def test_deepseek_response_format_gating_separates_capability_and_applied(
    monkeypatch: pytest.MonkeyPatch,
    response_format: str | None,
    supports_json_object: bool,
    expect_response_format_kwarg: bool,
) -> None:
    captured: dict[str, Any] = {}
    caps = ProviderCapabilities(
        supports_json_object_response_format=supports_json_object,
    )
    monkeypatch.setattr(DeepSeekProvider, "capabilities", caps)

    config = ProviderConfig(
        provider_name="deepseek",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-pro",
        model_alias="deepseek_v4_pro",
        thinking=False,
        response_format=response_format,
    )
    provider = DeepSeekProvider(config)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    result = provider.generate([{"role": "user", "content": "hi"}])

    assert result.capabilities is not None
    assert (
        result.capabilities["json_object_response_format"] is supports_json_object
    )
    assert result.response_format_applied is expect_response_format_kwarg
    if expect_response_format_kwarg:
        assert captured["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in captured


def test_invalid_response_format_is_rejected_before_env_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="response_format"):
        load_provider_config_from_profile(
            "deepseek_v4_pro",
            response_format="text",
        )


def test_unknown_profile_thinking_override_fails_before_env_lookup() -> None:
    with pytest.raises(UnknownLLMProfileError, match="unknown llm profile"):
        load_provider_config_from_profile("unknown-profile", thinking=True)


def _fake_openai_client(captured: dict[str, Any]) -> object:
    class _FakeChoice:
        finish_reason = "stop"

        class message:
            content = "answer"

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

    return _FakeClient()


def test_bailian_non_streaming_request_preserves_raw_result_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    caps = ProviderCapabilities(supports_json_object_response_format=True)
    monkeypatch.setattr(BailianQwenProvider, "capabilities", caps)

    class _FakeUsage:
        prompt_tokens = 11
        completion_tokens = 7
        total_tokens = 18

    class _FakeChoice:
        finish_reason = "stop"

        class message:
            content = '{"status":"ok"}'

    class _FakeResponse:
        id = "completion-body-id"
        choices: ClassVar[list[_FakeChoice]] = [_FakeChoice()]
        usage = _FakeUsage()
        system_fingerprint = "system-fingerprint-v1"
        model = "response-model-is-not-the-configured-contract"

    class _FakeCompletions:
        def create(self, **kwargs: Any) -> _FakeResponse:
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    config = ProviderConfig(
        provider_name="bailian_qwen",
        api_key="test-key",
        base_url="https://example.com/v1",
        model="qwen3.7-plus-2026-05-26",
        model_alias="qwen3_7_plus_2026_05_26",
        thinking=True,
        response_format="json_object",
        seed=1234,
    )
    provider = BailianQwenProvider(config)
    provider._client = _FakeClient()  # type: ignore[assignment]
    messages = [{"role": "user", "content": "return JSON"}]

    result = provider.generate(messages)

    assert captured == {
        "model": "qwen3.7-plus-2026-05-26",
        "messages": messages,
        "stream": False,
        "extra_body": {"enable_thinking": True},
        "seed": 1234,
        "response_format": {"type": "json_object"},
    }
    assert result.provider_name == "bailian_qwen"
    assert result.model == "qwen3.7-plus-2026-05-26"
    assert result.model_alias == "qwen3_7_plus_2026_05_26"
    assert result.raw_text == '{"status":"ok"}'
    assert result.request_id == "completion-body-id"
    assert result.api_version == "system-fingerprint-v1"
    assert result.finish_reason == "stop"
    assert result.usage == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert result.capabilities == {
        "json_object_response_format": True,
        "enable_thinking": True,
    }
    assert result.response_format_applied is True
    assert result.thinking is True


def test_bailian_non_streaming_provider_exception_propagates() -> None:
    provider_error = RuntimeError("provider unavailable")

    class _FailingCompletions:
        def create(self, **_kwargs: Any) -> object:
            raise provider_error

    class _FakeChat:
        completions = _FailingCompletions()

    class _FakeClient:
        chat = _FakeChat()

    config = ProviderConfig(
        provider_name="bailian_qwen",
        api_key="test-key",
        base_url="https://example.com/v1",
        model="qwen3.7-plus-2026-05-26",
        model_alias="qwen3_7_plus_2026_05_26",
        response_format=None,
    )
    provider = BailianQwenProvider(config)
    provider._client = _FakeClient()  # type: ignore[assignment]

    with pytest.raises(RuntimeError) as exc_info:
        provider.generate([{"role": "user", "content": "return JSON"}])

    assert exc_info.value is provider_error


@pytest.mark.parametrize(
    ("thinking", "expected_extra_body", "expected_thinking"),
    [
        (True, {"enable_thinking": True}, True),
        (False, {"enable_thinking": False}, False),
    ],
)
def test_bailian_explicit_thinking_request_mapping(
    monkeypatch: pytest.MonkeyPatch,
    thinking: bool,
    expected_extra_body: dict[str, bool],
    expected_thinking: bool,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile="qwen3_7_max",
        thinking=thinking,
        response_format=None,
    )
    assert isinstance(provider, BailianQwenProvider)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    result = provider.generate([{"role": "user", "content": "hi"}])

    assert captured["model"] == "qwen3.7-max"
    assert captured["extra_body"] == expected_extra_body
    assert "reasoning_effort" not in captured
    assert "thinking" not in captured.get("extra_body", {})
    assert result.thinking is expected_thinking
    assert result.capabilities is not None
    assert result.capabilities["enable_thinking"] is expected_thinking


@pytest.mark.parametrize(
    ("response_format", "supports_json_object", "expect_response_format_kwarg"),
    [
        (None, False, False),
        (None, True, False),
        ("json_object", False, False),
        ("json_object", True, True),
    ],
)
def test_bailian_response_format_gating_requires_request_and_capability(
    monkeypatch: pytest.MonkeyPatch,
    response_format: str | None,
    supports_json_object: bool,
    expect_response_format_kwarg: bool,
) -> None:
    captured: dict[str, Any] = {}
    caps = ProviderCapabilities(
        supports_json_object_response_format=supports_json_object,
    )
    monkeypatch.setattr(BailianQwenProvider, "capabilities", caps)

    config = ProviderConfig(
        provider_name="bailian_qwen",
        api_key="test-key",
        base_url="https://example.com/v1",
        model="qwen3.7-max",
        model_alias="qwen3_7_max",
        response_format=response_format,
    )
    provider = BailianQwenProvider(config)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    result = provider.generate([{"role": "user", "content": "hi"}])

    assert result.capabilities is not None
    assert (
        result.capabilities["json_object_response_format"] is supports_json_object
    )
    assert result.response_format_applied is expect_response_format_kwarg
    if expect_response_format_kwarg:
        assert captured["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in captured


def test_bailian_unspecified_thinking_omits_enable_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile="qwen3_7_max",
        response_format=None,
    )
    assert isinstance(provider, BailianQwenProvider)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    result = provider.generate([{"role": "user", "content": "hi"}])

    assert captured["model"] == "qwen3.7-max"
    assert "extra_body" not in captured
    assert "reasoning_effort" not in captured
    assert result.thinking is None
    assert result.capabilities is not None
    assert "enable_thinking" not in result.capabilities


def test_bailian_runtime_config_preserves_explicit_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")

    config = load_provider_config_from_profile("qwen3_7_max", thinking=True)

    assert config.provider_name == "bailian_qwen"
    assert config.model_alias == "qwen3_7_max"
    assert config.model == "qwen3.7-max"
    assert config.thinking is True


def test_bailian_runtime_config_uses_configured_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")

    config = load_provider_config_from_profile("qwen3_7_max")

    assert config.base_url == "https://example.invalid/compatible-mode/v1"


@pytest.mark.parametrize("base_url", [None, ""], ids=["missing", "empty"])
def test_bailian_runtime_config_requires_base_url(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str | None,
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    if base_url is None:
        monkeypatch.delenv("BAILIAN_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("BAILIAN_BASE_URL", base_url)

    with pytest.raises(
        RuntimeError,
        match="^Missing required environment variable: BAILIAN_BASE_URL$",
    ):
        load_provider_config_from_profile("qwen3_7_max")


def test_bailian_seed_forwarding(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile="qwen3_7_plus",
        response_format=None,
        seed=1234,
    )
    assert isinstance(provider, BailianQwenProvider)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    provider.generate([{"role": "user", "content": "hi"}])

    assert captured["seed"] == 1234


def test_bailian_omits_seed_when_unspecified(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile="qwen3_7_max",
        response_format=None,
    )
    assert isinstance(provider, BailianQwenProvider)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    provider.generate([{"role": "user", "content": "hi"}])

    assert "seed" not in captured


def test_production_build_api_provider_leaves_seed_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = load_provider_config_from_profile("deepseek_v4_pro")

    assert config.seed is None


@pytest.mark.parametrize(
    ("profile", "model"),
    [
        ("qwen3_7_plus", "qwen3.7-plus"),
        ("qwen3_7_plus_2026_05_26", "qwen3.7-plus-2026-05-26"),
        ("qwen3_7_max_2026_05_20", "qwen3.7-max-2026-05-20"),
    ],
)
def test_bailian_snapshot_profiles_use_exact_vendor_model(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    model: str,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)
    provider = build_api_provider(
        llm_profile=profile,
        response_format=None,
    )
    assert isinstance(provider, BailianQwenProvider)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    provider.generate([{"role": "user", "content": "hi"}])

    assert captured["model"] == model
