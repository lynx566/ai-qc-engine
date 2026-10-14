"""Normalize LLM call metadata for execution records and run summaries."""

from __future__ import annotations

from typing import Any

from llm.providers.base import LLMRawResult


def response_format_applied_from_raw_result(raw_result: LLMRawResult) -> bool:
    """Whether JSON Object was applied on the provider request for this call."""
    return bool(raw_result.response_format_applied)


def llm_effective_execution_fields(
    invocation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract capability/applied fields for run summaries and job indexes."""
    if not invocation:
        return {"response_format_applied": False}
    fields: dict[str, Any] = {
        "response_format_applied": bool(
            invocation.get("response_format_applied", False)
        ),
    }
    capabilities = invocation.get("capabilities")
    if capabilities is not None:
        fields["capabilities"] = dict(capabilities)
    return fields


__all__ = [
    "llm_effective_execution_fields",
    "response_format_applied_from_raw_result",
]
