from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.model_registry import (
    DEFAULT_LLM_PROFILE,
    LLM_PROFILE_CHOICES,
    LLM_PROFILE_REGISTRY,
    RETIRED_LLM_PROFILES,
    RetiredLLMProfileError,
    UnknownLLMProfileError,
    is_retired_llm_profile_name,
    resolve_llm_profile,
    resolve_llm_selection,
)


@pytest.mark.parametrize(
    ("profile", "model", "max_tokens"),
    [
        ("deepseek_v4_flash", "deepseek-v4-flash", 10000),
        ("deepseek_v4_pro", "deepseek-v4-pro", 16000),
    ],
)
def test_canonical_deepseek_model_profiles(
    profile: str,
    model: str,
    max_tokens: int,
) -> None:
    alias, spec = resolve_llm_profile(profile)

    assert alias == profile
    assert spec.provider == "deepseek"
    assert spec.model == model
    assert spec.max_tokens == max_tokens
    assert not hasattr(spec, "reasoning")


def test_retired_names_are_not_canonical_registry_identities() -> None:
    assert "deepseek_chat" not in LLM_PROFILE_REGISTRY
    assert "deepseek_reasoning" not in LLM_PROFILE_REGISTRY
    assert "qwen_flash" not in LLM_PROFILE_REGISTRY
    assert "deepseek_chat" not in LLM_PROFILE_CHOICES
    assert "deepseek_reasoning" not in LLM_PROFILE_CHOICES
    assert "qwen_flash" not in LLM_PROFILE_CHOICES


@pytest.mark.parametrize(
    ("name", "replacement_fragment"),
    [
        ("deepseek_chat", "deepseek_v4_flash --no-thinking"),
        ("deepseek_reasoning", "deepseek_v4_flash --thinking"),
        ("deepseek-chat", "deepseek_v4_flash --no-thinking"),
        ("deepseek-reasoner", "deepseek_v4_flash --thinking"),
        ("qwen_flash", "qwen3_5_flash"),
    ],
)
def test_retired_profile_tokens_are_rejected_with_guidance(
    name: str,
    replacement_fragment: str,
) -> None:
    assert is_retired_llm_profile_name(name) is True

    with pytest.raises(RetiredLLMProfileError, match="is retired") as profile_exc:
        resolve_llm_profile(name)
    assert replacement_fragment in str(profile_exc.value)

    with pytest.raises(RetiredLLMProfileError, match="is retired") as selection_exc:
        resolve_llm_selection(name)
    assert replacement_fragment in str(selection_exc.value)


def test_retired_profile_messages_match_registry() -> None:
    for token, message in RETIRED_LLM_PROFILES.items():
        with pytest.raises(RetiredLLMProfileError, match=message):
            resolve_llm_selection(token)


@pytest.mark.parametrize("profile", ["deepseek_v4_flash", "deepseek_v4_pro"])
def test_canonical_deepseek_default_is_non_thinking(profile: str) -> None:
    assert resolve_llm_selection(profile).thinking is False


def test_non_deepseek_explicit_thinking_fails_clearly() -> None:
    with pytest.raises(UnknownLLMProfileError, match="unknown llm profile"):
        resolve_llm_selection("unknown-profile", thinking=False)


def test_bailian_explicit_thinking_selection_is_supported() -> None:
    for profile in (
        "qwen3_7_max",
        "qwen3_7_plus",
        "qwen3_7_plus_2026_05_26",
        "qwen3_7_max_2026_05_20",
    ):
        enabled = resolve_llm_selection(profile, thinking=True)
        disabled = resolve_llm_selection(profile, thinking=False)

        assert enabled.thinking is True
        assert disabled.thinking is False


@pytest.mark.parametrize(
    ("profile", "model"),
    [
        ("qwen3_7_plus", "qwen3.7-plus"),
        ("qwen3_7_plus_2026_05_26", "qwen3.7-plus-2026-05-26"),
        ("qwen3_7_max_2026_05_20", "qwen3.7-max-2026-05-20"),
    ],
)
def test_qwen3_7_profiles_resolve_to_exact_bailian_models(
    profile: str,
    model: str,
) -> None:
    selection = resolve_llm_selection(profile)

    assert selection.canonical_profile_name == profile
    assert selection.profile_spec.provider == "bailian_qwen"
    assert selection.profile_spec.model == model
    assert selection.thinking is None


def test_qwen3_7_max_profile_resolves_to_bailian_model() -> None:
    selection = resolve_llm_selection("qwen3_7_max")

    assert selection.canonical_profile_name == "qwen3_7_max"
    assert selection.profile_spec.provider == "bailian_qwen"
    assert selection.profile_spec.model == "qwen3.7-max"
    assert selection.thinking is None


def test_qwen3_5_flash_profile_resolves_to_bailian_model() -> None:
    selection = resolve_llm_selection("qwen3_5_flash")

    assert selection.canonical_profile_name == "qwen3_5_flash"
    assert selection.profile_spec.provider == "bailian_qwen"
    assert selection.profile_spec.model == "qwen3.5-flash"
    assert selection.thinking is None


def test_unknown_profile_raises() -> None:
    with pytest.raises(UnknownLLMProfileError, match="unknown llm profile"):
        resolve_llm_profile("unknown-profile")


def test_default_profile_is_deepseek_v4_flash() -> None:
    assert DEFAULT_LLM_PROFILE == "deepseek_v4_flash"
    alias, _ = resolve_llm_profile(DEFAULT_LLM_PROFILE)
    assert alias == "deepseek_v4_flash"
