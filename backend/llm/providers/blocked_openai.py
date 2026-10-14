"""Blocked OpenAI client used when external LLM execution is disabled."""

from __future__ import annotations

EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE = (
    "External LLM execution is disabled during tests"
)


class _BlockedCompletions:
    def create(self, *_args: object, **_kwargs: object) -> object:
        raise RuntimeError(EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE)


class _BlockedChat:
    def __init__(self) -> None:
        self.completions = _BlockedCompletions()


class BlockedOpenAIClient:
    """Minimal OpenAI client shape that rejects network-capable completion calls."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.chat = _BlockedChat()


__all__ = [
    "EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE",
    "BlockedOpenAIClient",
]
