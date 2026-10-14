"""Neutral runtime-only dependencies for Filter-output projection execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm.providers.base import LLMProvider


@dataclass(frozen=True, slots=True)
class FilterOutputProjectionRuntimeDependencies:
    """Runtime-injected dependencies consumed by installed facade construction."""

    llm_provider: LLMProvider | None = None
    llm_execution_config: dict[str, Any] | None = None


__all__ = ["FilterOutputProjectionRuntimeDependencies"]
