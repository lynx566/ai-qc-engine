from __future__ import annotations

from llm.model_registry import DEFAULT_LLM_PROFILE

from llm.providers.base import LLMProvider
from llm.providers.config import load_env, load_provider_config_from_profile


def build_api_provider(
    *,
    llm_profile: str = DEFAULT_LLM_PROFILE,
    thinking: bool | None = None,
    response_format: str | None = "json_object",
    seed: int | None = None,
) -> LLMProvider:
    """Build an API provider from canonical model identity and execution selection."""
    load_env()
    config = load_provider_config_from_profile(
        llm_profile,
        thinking=thinking,
        response_format=response_format,
        seed=seed,
    )

    if config.provider_name == "deepseek":
        from llm.providers.deepseek import DeepSeekProvider

        return DeepSeekProvider(config)

    if config.provider_name == "bailian_qwen":
        from llm.providers.bailian import BailianQwenProvider

        return BailianQwenProvider(config)

    raise ValueError(f"unsupported provider: {config.provider_name}")


def default_llm_profile() -> str:
    return DEFAULT_LLM_PROFILE
