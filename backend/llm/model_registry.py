"""Canonical LLM model profiles and execution selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMProfileSpec:
    """Provider adapter settings that describe model identity only."""

    provider: str
    model: str
    max_tokens: int | None = None


LLM_PROFILE_REGISTRY: dict[str, LLMProfileSpec] = {
    "deepseek_v4_flash": LLMProfileSpec(
        provider="deepseek",
        model="deepseek-v4-flash",
        max_tokens=10000,
    ),
    "deepseek_v4_pro": LLMProfileSpec(
        provider="deepseek",
        model="deepseek-v4-pro",
        max_tokens=16000,
    ),
    "qwen3_5_flash": LLMProfileSpec(
        provider="bailian_qwen",
        model="qwen3.5-flash",
    ),
    "qwen3_7_max": LLMProfileSpec(
        provider="bailian_qwen",
        model="qwen3.7-max",
    ),
    "qwen3_7_plus": LLMProfileSpec(
        provider="bailian_qwen",
        model="qwen3.7-plus",
    ),
    "qwen3_7_plus_2026_05_26": LLMProfileSpec(
        provider="bailian_qwen",
        model="qwen3.7-plus-2026-05-26",
    ),
    "qwen3_7_max_2026_05_20": LLMProfileSpec(
        provider="bailian_qwen",
        model="qwen3.7-max-2026-05-20",
    ),
}


# Providers that accept explicit --thinking / --no-thinking CLI overrides.
THINKING_SELECTION_PROVIDERS: frozenset[str] = frozenset(
    {"deepseek", "bailian_qwen"}
)


@dataclass(frozen=True)
class ResolvedLLMSelection:
    """A canonical model profile paired with its resolved execution mode."""

    canonical_profile_name: str
    profile_spec: LLMProfileSpec
    thinking: bool | None


# Retired mode-bearing profile tokens. Execution must reject these explicitly.
# Historical pricing lookup may still map the same strings via pricing.py.
RETIRED_LLM_PROFILES: dict[str, str] = {
    "deepseek_chat": (
        "deepseek_chat is retired. "
        "Use --llm-profile deepseek_v4_flash --no-thinking."
    ),
    "deepseek_reasoning": (
        "deepseek_reasoning is retired. "
        "Use --llm-profile deepseek_v4_flash --thinking."
    ),
    "deepseek-chat": (
        "deepseek-chat is retired. "
        "Use --llm-profile deepseek_v4_flash --no-thinking."
    ),
    "deepseek-reasoner": (
        "deepseek-reasoner is retired. "
        "Use --llm-profile deepseek_v4_flash --thinking."
    ),
    "qwen_flash": (
        "qwen_flash is retired. "
        "Use --llm-profile qwen3_5_flash."
    ),
}

DEFAULT_LLM_PROFILE = "deepseek_v4_flash"

LLM_PROFILE_CHOICES: tuple[str, ...] = tuple(sorted(LLM_PROFILE_REGISTRY.keys()))


class UnknownLLMProfileError(ValueError):
    """Raised when an LLM profile alias cannot be resolved."""


class RetiredLLMProfileError(ValueError):
    """Raised when a retired mode-bearing profile token is used for execution."""


def is_retired_llm_profile_name(name: str) -> bool:
    return str(name).strip() in RETIRED_LLM_PROFILES


def _raise_if_retired_llm_profile(name: str) -> None:
    key = str(name).strip()
    message = RETIRED_LLM_PROFILES.get(key)
    if message is not None:
        raise RetiredLLMProfileError(message)


def resolve_llm_profile(name: str) -> tuple[str, LLMProfileSpec]:
    """Resolve a canonical profile name to model identity + spec."""
    key = str(name).strip()
    _raise_if_retired_llm_profile(key)
    spec = LLM_PROFILE_REGISTRY.get(key)
    if spec is None:
        raise UnknownLLMProfileError(
            f"unknown llm profile {name!r}; choices: {', '.join(LLM_PROFILE_CHOICES)}"
        )
    return key, spec


def resolve_llm_selection(
    name: str,
    *,
    thinking: bool | None = None,
) -> ResolvedLLMSelection:
    """Resolve model identity and thinking mode with explicit precedence."""
    key = str(name).strip()
    _raise_if_retired_llm_profile(key)
    canonical, spec = resolve_llm_profile(key)

    if thinking is not None and spec.provider not in THINKING_SELECTION_PROVIDERS:
        raise ValueError(
            f"thinking execution selection is not supported for provider {spec.provider!r}"
        )

    if thinking is not None:
        resolved_thinking = bool(thinking)
    elif spec.provider == "bailian_qwen":
        resolved_thinking = None
    else:
        resolved_thinking = False
    return ResolvedLLMSelection(
        canonical_profile_name=canonical,
        profile_spec=spec,
        thinking=resolved_thinking,
    )
