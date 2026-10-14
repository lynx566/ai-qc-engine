from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from llm.model_registry import resolve_llm_selection


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    api_key: str
    base_url: str
    model: str
    model_alias: str
    thinking: bool | None = None
    max_tokens: int | None = None
    response_format: str | None = "json_object"
    seed: int | None = None

    def __post_init__(self) -> None:
        _validate_response_format(self.response_format)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_env() -> None:
    load_dotenv()


def _validate_response_format(value: str | None) -> None:
    if value not in ("json_object", None):
        raise ValueError(
            "response_format must be 'json_object' or None, "
            f"got {value!r}"
        )


def load_provider_config_from_profile(
    llm_profile: str,
    *,
    thinking: bool | None = None,
    response_format: str | None = "json_object",
    seed: int | None = None,
) -> ProviderConfig:
    """Load credentials and translate a resolved selection to provider config."""
    _validate_response_format(response_format)
    selection = resolve_llm_selection(llm_profile, thinking=thinking)
    model_alias = selection.canonical_profile_name
    spec = selection.profile_spec

    if spec.provider == "deepseek":
        return ProviderConfig(
            provider_name="deepseek",
            api_key=_require_env("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            model=spec.model,
            model_alias=model_alias,
            thinking=selection.thinking,
            max_tokens=spec.max_tokens,
            response_format=response_format,
            seed=seed,
        )

    if spec.provider == "bailian_qwen":
        return ProviderConfig(
            provider_name="bailian_qwen",
            api_key=_require_env("DASHSCOPE_API_KEY"),
            base_url=_require_env("BAILIAN_BASE_URL"),
            model=spec.model,
            model_alias=model_alias,
            thinking=selection.thinking,
            response_format=response_format,
            seed=seed,
        )

    raise ValueError(f"unsupported provider in llm profile {llm_profile!r}: {spec.provider!r}")
