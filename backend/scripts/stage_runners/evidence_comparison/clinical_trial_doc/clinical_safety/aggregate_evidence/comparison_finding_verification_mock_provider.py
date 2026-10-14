"""Comparison Finding Verification mock LLMProvider for standalone dev execution."""

from __future__ import annotations

import json
from dataclasses import dataclass

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDING_ID_PATTERN,
)
from llm.providers.base import LLMRawResult

_FINDINGS_SECTION_MARKER = "## Findings\n"


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationStandaloneMockProvider:
    """Return schema-valid Verification responses with every input finding confirmed."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        finding_ids = _extract_input_finding_ids(user_content)
        payload = {
            "finding_verifications": [
                {
                    "finding_id": finding_id,
                    "verification_result": "confirmed",
                }
                for finding_id in finding_ids
            ]
        }
        return LLMRawResult(
            provider_name="mock",
            model="comparison-finding-verification-standalone-mock",
            raw_text=json.dumps(payload, ensure_ascii=False),
        )


def _extract_input_finding_ids(user_content: str) -> list[str]:
    marker_index = user_content.find(_FINDINGS_SECTION_MARKER)
    if marker_index == -1:
        return []
    findings_section = user_content[marker_index + len(_FINDINGS_SECTION_MARKER) :]
    if not findings_section.strip():
        return []
    finding_ids: list[str] = []
    for line in findings_section.splitlines():
        stripped = line.strip()
        if FINDING_ID_PATTERN.fullmatch(stripped):
            finding_ids.append(stripped)
    return finding_ids


__all__ = ["ComparisonFindingVerificationStandaloneMockProvider"]
