"""Comparison Finding Assessment mock LLMProvider for standalone dev execution."""

from __future__ import annotations

import json
from dataclasses import dataclass

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    SENTENCE_ALIAS_SCAN_PATTERN,
)

from llm.providers.base import LLMRawResult


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentStandaloneMockProvider:
    """Return minimal valid Assessment candidates using aliases present in the prompt."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        aliases = sorted(set(SENTENCE_ALIAS_SCAN_PATTERN.findall(user_content)))
        if not aliases:
            raise ValueError(
                "comparison finding assessment mock provider expected sentence aliases "
                "in the rendered evidence body"
            )
        payload = {
            "candidates": [
                {
                    "candidate_focus": "mock比较点",
                    "label": "fail",
                    "trigger_sentence_aliases": aliases[: min(2, len(aliases))],
                }
            ]
        }
        return LLMRawResult(
            provider_name="mock",
            model="comparison-finding-assessment-standalone-mock",
            raw_text=json.dumps(payload, ensure_ascii=False),
        )


__all__ = ["ComparisonFindingAssessmentStandaloneMockProvider"]
