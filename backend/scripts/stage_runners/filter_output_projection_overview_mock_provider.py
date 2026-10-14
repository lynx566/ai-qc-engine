"""Overview-specific mock LLMProvider for standalone Filter-output projection dev runs."""

from __future__ import annotations

import json
from dataclasses import dataclass

from llm.providers.base import LLMRawResult


@dataclass(frozen=True, slots=True)
class OverviewStandaloneMockProvider:
    """Return minimal valid Overview assessments from prompt source aliases."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        content = messages[-1]["content"]
        marker = "## Overview source\n\n"
        if marker not in content:
            raise ValueError("overview mock provider expected Overview source section")
        payload = json.loads(content.split(marker, 1)[1].strip())
        aliases: list[str] = []
        for scope in payload:
            if not isinstance(scope, dict):
                continue
            for item in scope.get("source_items", []):
                if isinstance(item, dict) and isinstance(item.get("source_id"), str):
                    aliases.append(item["source_id"])
        assessments = [
            {"source_id": alias, "content_modules": ["clinical_safety"]}
            for alias in aliases
        ]
        return LLMRawResult(
            provider_name="mock",
            model="overview-standalone-mock",
            raw_text=json.dumps(
                {"sentence_assessments": assessments},
                ensure_ascii=False,
            ),
        )


__all__ = ["OverviewStandaloneMockProvider"]
