"""Stable LLM profile aliases decoupled from vendor model names."""

from llm.execution_configs import (
    LLM_EXECUTION_CONFIG_REGISTRY,
    LLMExecutionConfig,
    UnknownLLMExecutionConfigError,
    materialize_llm_provider,
    resolve_llm_execution_config,
)
from llm.model_registry import (
    DEFAULT_LLM_PROFILE,
    LLM_PROFILE_CHOICES,
    RETIRED_LLM_PROFILES,
    LLMProfileSpec,
    ResolvedLLMSelection,
    RetiredLLMProfileError,
    UnknownLLMProfileError,
    is_retired_llm_profile_name,
    resolve_llm_profile,
    resolve_llm_selection,
)

__all__ = [
    "DEFAULT_LLM_PROFILE",
    "LLM_EXECUTION_CONFIG_REGISTRY",
    "LLM_PROFILE_CHOICES",
    "RETIRED_LLM_PROFILES",
    "LLMExecutionConfig",
    "LLMProfileSpec",
    "ResolvedLLMSelection",
    "RetiredLLMProfileError",
    "UnknownLLMExecutionConfigError",
    "UnknownLLMProfileError",
    "is_retired_llm_profile_name",
    "materialize_llm_provider",
    "resolve_llm_execution_config",
    "resolve_llm_profile",
    "resolve_llm_selection",
]
