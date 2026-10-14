"""Neutral LLM execution configuration registry."""

from __future__ import annotations

from dataclasses import dataclass

from llm.model_registry import resolve_llm_profile
from llm.providers.base import LLMProvider
from llm.providers.factory import build_api_provider

CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID = (
    "clinical_trial_doc_fop_overview"
)
CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID = (
    "clinical_trial_doc_esp_aggregate"
)
CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID = (
    "clinical_trial_doc_ec_assessment"
)
CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID = (
    "clinical_trial_doc_ec_assessment_second_pass"
)
CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID = (
    "clinical_trial_doc_ec_verification"
)
CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID = (
    "clinical_trial_doc_ec_consolidation"
)


@dataclass(frozen=True, slots=True)
class LLMExecutionConfig:
    """Named execution policy referencing a canonical model profile."""

    config_id: str
    profile_id: str
    thinking: bool | None
    response_format: str | None = None
    seed: int | None = None

    def to_provenance_record(self) -> dict[str, object]:
        """Canonical provider-neutral execution-policy record for formal-flow metadata."""
        return {
            "config_id": self.config_id,
            "profile_id": self.profile_id,
            "thinking": self.thinking,
            "response_format": self.response_format,
            "seed": self.seed,
        }


class UnknownLLMExecutionConfigError(LookupError):
    """Raised when an LLM execution config ID cannot be resolved."""


LLM_EXECUTION_CONFIG_REGISTRY: dict[str, LLMExecutionConfig] = {
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID: LLMExecutionConfig(
        config_id=CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=None,
        response_format="json_object",
        seed=1234,
    ),
    CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID: LLMExecutionConfig(
        config_id=CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID,
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=None,
        response_format="json_object",
    ),
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID: LLMExecutionConfig(
        config_id=CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=None,
        response_format=None,
        seed=1234,
    ),
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID: LLMExecutionConfig(
        config_id=CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=True,
        response_format=None,
        seed=1234,
    ),
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID: LLMExecutionConfig(
        config_id=CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=None,
        response_format=None,
        seed=1234,
    ),
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID: LLMExecutionConfig(
        config_id=CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=None,
        response_format=None,
        seed=1234,
    ),
}


def resolve_llm_execution_config(config_id: str) -> LLMExecutionConfig:
    """Resolve a named execution config and validate its profile reference."""
    key = str(config_id).strip()
    config = LLM_EXECUTION_CONFIG_REGISTRY.get(key)
    if config is None:
        known = ", ".join(sorted(LLM_EXECUTION_CONFIG_REGISTRY))
        raise UnknownLLMExecutionConfigError(
            f"unknown llm execution config {config_id!r}; known: {known}"
        )
    resolve_llm_profile(config.profile_id)
    return config


def materialize_llm_provider(config: LLMExecutionConfig) -> LLMProvider:
    """Construct an API provider from a resolved execution config."""
    return build_api_provider(
        llm_profile=config.profile_id,
        thinking=config.thinking,
        response_format=config.response_format,
        seed=config.seed,
    )


__all__ = [
    "CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID",
    "CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID",
    "CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID",
    "CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID",
    "CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID",
    "CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID",
    "LLM_EXECUTION_CONFIG_REGISTRY",
    "LLMExecutionConfig",
    "UnknownLLMExecutionConfigError",
    "materialize_llm_provider",
    "resolve_llm_execution_config",
]
