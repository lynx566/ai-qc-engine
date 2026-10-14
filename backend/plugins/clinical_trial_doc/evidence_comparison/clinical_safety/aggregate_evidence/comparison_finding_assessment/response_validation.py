"""Structural response-contract validation for Finding Assessment responses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    SENTENCE_ALIAS_PATTERN,
)

from ..response_json_repair import repair_unescaped_quotes_in_string_fields

ComparisonFindingAssessmentCandidateLabel = Literal["fail", "need_review"]

_CANDIDATE_LABELS = frozenset({"fail", "need_review"})
_CANDIDATE_KEYS = frozenset(
    {"candidate_focus", "label", "trigger_sentence_aliases"},
)


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentCandidate:
    candidate_focus: str
    label: ComparisonFindingAssessmentCandidateLabel
    trigger_sentence_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentValidatedResponse:
    candidates: tuple[ComparisonFindingAssessmentCandidate, ...]


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            opening = lines[0].strip()
            closing = lines[-1].strip()
            if opening in {"```", "```json", "```JSON"} and closing == "```":
                return "\n".join(lines[1:-1]).strip()
    return text


def parse_comparison_finding_assessment_response(raw_text: str) -> dict[str, Any]:
    """Parse raw provider text into a JSON object."""

    json_text = _extract_json_text(raw_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        repaired_json_text = repair_unescaped_quotes_in_string_fields(
            json_text,
            allowed_field_names=frozenset({"candidate_focus"}),
        )
        try:
            payload = json.loads(repaired_json_text)
        except json.JSONDecodeError:
            raise ValueError(f"response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("response must be a JSON object")
    return payload


def _validate_sentence_alias(alias: str, *, context: str) -> str:
    if not isinstance(alias, str) or not SENTENCE_ALIAS_PATTERN.fullmatch(alias):
        raise ValueError(f"{context} must match Tdddd format: {alias!r}")
    return alias


def _validate_candidate_label(
    value: Any,
    *,
    context: str,
) -> ComparisonFindingAssessmentCandidateLabel:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    normalized = value.strip()
    if normalized not in _CANDIDATE_LABELS:
        choices = ", ".join(sorted(_CANDIDATE_LABELS))
        raise ValueError(f"{context} must be one of: {choices}; got {normalized!r}")
    return normalized  # type: ignore[return-value]


def validate_comparison_finding_assessment_response_structure(
    payload: Mapping[str, Any],
) -> ComparisonFindingAssessmentValidatedResponse:
    """Validate top-level Finding Assessment response shape only."""

    if set(payload) != {"candidates"}:
        raise ValueError("response object must contain exactly one field: candidates")
    candidates = payload["candidates"]
    if not isinstance(candidates, list):
        raise ValueError("candidates must be an array")

    validated_candidates: list[ComparisonFindingAssessmentCandidate] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidates[{index}] must be an object")
        if set(candidate) != _CANDIDATE_KEYS:
            raise ValueError(
                f"candidates[{index}] must contain exactly candidate_focus, label, "
                "and trigger_sentence_aliases"
            )
        candidate_focus = candidate["candidate_focus"]
        if not isinstance(candidate_focus, str) or not candidate_focus.strip():
            raise ValueError(
                f"candidates[{index}].candidate_focus must be a non-empty string"
            )
        label = _validate_candidate_label(
            candidate["label"],
            context=f"candidates[{index}].label",
        )
        trigger_sentence_aliases = candidate["trigger_sentence_aliases"]
        if not isinstance(trigger_sentence_aliases, list) or not trigger_sentence_aliases:
            raise ValueError(
                f"candidates[{index}].trigger_sentence_aliases must be a non-empty array"
            )
        validated_aliases = tuple(
            _validate_sentence_alias(
                alias,
                context=f"candidates[{index}].trigger_sentence_aliases[{alias_index}]",
            )
            for alias_index, alias in enumerate(trigger_sentence_aliases)
        )
        validated_candidates.append(
            ComparisonFindingAssessmentCandidate(
                candidate_focus=candidate_focus,
                label=label,
                trigger_sentence_aliases=validated_aliases,
            )
        )
    return ComparisonFindingAssessmentValidatedResponse(
        candidates=tuple(validated_candidates),
    )


def parse_and_validate_comparison_finding_assessment_response(
    raw_text: str,
) -> ComparisonFindingAssessmentValidatedResponse:
    """Parse raw provider text and validate the response contract."""

    payload = parse_comparison_finding_assessment_response(raw_text)
    return validate_comparison_finding_assessment_response_structure(payload)


def serialize_validated_response(
    validated_response: ComparisonFindingAssessmentValidatedResponse,
) -> dict[str, Any]:
    """Serialize a validated response for persistence."""

    return {
        "candidates": [
            {
                "candidate_focus": candidate.candidate_focus,
                "label": candidate.label,
                "trigger_sentence_aliases": list(candidate.trigger_sentence_aliases),
            }
            for candidate in validated_response.candidates
        ]
    }


__all__ = [
    "ComparisonFindingAssessmentCandidate",
    "ComparisonFindingAssessmentCandidateLabel",
    "ComparisonFindingAssessmentValidatedResponse",
    "parse_and_validate_comparison_finding_assessment_response",
    "parse_comparison_finding_assessment_response",
    "serialize_validated_response",
    "validate_comparison_finding_assessment_response_structure",
]
