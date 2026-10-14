"""Shared OpenAI client construction with an external-execution kill switch."""

from __future__ import annotations

import os
from typing import Any

from llm.providers.blocked_openai import BlockedOpenAIClient

EXTERNAL_LLM_DISABLED_ENV = "EXTERNAL_LLM_DISABLED"

_TRUTHY_DISABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def is_external_llm_execution_disabled() -> bool:
    """Return whether external LLM HTTP execution is disabled via environment."""

    value = os.environ.get(EXTERNAL_LLM_DISABLED_ENV, "").strip().lower()
    return value in _TRUTHY_DISABLED_VALUES


def build_openai_client(
    *,
    api_key: str,
    base_url: str | None,
    timeout: float,
    max_retries: int | None = None,
) -> Any:
    """Build a real OpenAI client or a blocked stub when execution is disabled."""

    if is_external_llm_execution_disabled():
        return BlockedOpenAIClient()

    from openai import OpenAI

    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url,
        "timeout": timeout,
    }
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    return OpenAI(**kwargs)


__all__ = [
    "EXTERNAL_LLM_DISABLED_ENV",
    "build_openai_client",
    "is_external_llm_execution_disabled",
]
