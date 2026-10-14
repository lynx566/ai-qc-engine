"""Runtime-owned LLM execution selection for Aggregate Evidence assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm.providers.base import LLMProvider
from llm.providers.factory import build_api_provider
from llm.model_registry import ResolvedLLMSelection, resolve_llm_selection

ASSESSMENT_RESPONSE_FORMAT = "json_object"
ASSESSMENT_SEED: int | None = None


@dataclass(frozen=True)
class AggregateEvidenceLLMExecution:
    """One resolved, constructed API execution dependency."""

    requested_profile: str
    requested_thinking: bool | None
    selection: ResolvedLLMSelection
    provider: LLMProvider
    response_format: str
    seed: int | None

    def metadata(self) -> dict[str, Any]:
        spec = self.selection.profile_spec
        return {
            "requested_profile": self.requested_profile,
            "requested_thinking": self.requested_thinking,
            "canonical_profile": self.selection.canonical_profile_name,
            "provider": spec.provider,
            "model": spec.model,
            "thinking": self.selection.thinking,
            "response_format": self.response_format,
            "max_tokens": spec.max_tokens,
            "seed": self.seed,
        }

    def format_pre_execution_summary(self) -> str:
        metadata = self.metadata()
        return " ".join(
            (
                f"provider={metadata['provider']}",
                f"profile={metadata['canonical_profile']}",
                f"model={metadata['model']}",
                f"thinking={_format_optional_bool(metadata['thinking'])}",
                f"response_format={metadata['response_format']}",
                f"seed={metadata['seed'] if metadata['seed'] is not None else 'unset'}",
                f"max_tokens={metadata['max_tokens']}",
            )
        )


def build_aggregate_evidence_llm_execution(
    *,
    llm_profile: str,
    thinking: bool | None,
) -> AggregateEvidenceLLMExecution:
    """Resolve the complete selection and construct its API provider in Runtime."""
    requested_profile = str(llm_profile).strip()
    selection = resolve_llm_selection(requested_profile, thinking=thinking)
    provider = build_api_provider(
        llm_profile=requested_profile,
        thinking=thinking,
        response_format=ASSESSMENT_RESPONSE_FORMAT,
        seed=ASSESSMENT_SEED,
    )
    return AggregateEvidenceLLMExecution(
        requested_profile=requested_profile,
        requested_thinking=thinking,
        selection=selection,
        provider=provider,
        response_format=ASSESSMENT_RESPONSE_FORMAT,
        seed=ASSESSMENT_SEED,
    )


def _format_optional_bool(value: object) -> str:
    if value is None:
        return "unset"
    return "true" if value is True else "false"
