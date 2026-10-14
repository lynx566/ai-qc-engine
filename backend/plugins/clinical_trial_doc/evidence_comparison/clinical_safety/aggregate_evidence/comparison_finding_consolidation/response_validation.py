"""Parsing and hard validation for consolidation responses."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    SENTENCE_ALIAS_PATTERN,
)

from ..response_json_repair import repair_unescaped_quotes_in_string_fields

CONCLUSION_ALIAS_PATTERN = re.compile(r"^C\d{3}$")
_GROUP_KEYS = frozenset(
    {
        "conclusion_aliases",
        "unified_conclusion",
        "combined_sentence_aliases",
    }
)


class ComparisonFindingConsolidationParseError(ValueError):
    """Raised when provider text cannot be parsed as a JSON object."""


class ComparisonFindingConsolidationValidationError(ValueError):
    """Raised when parsed JSON violates the hard response contract."""


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidatedGroup:
    conclusion_aliases: tuple[str, ...]
    unified_conclusion: str
    combined_sentence_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationValidatedResponse:
    consolidated_groups: tuple[ComparisonFindingConsolidatedGroup, ...]


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            opening = lines[0].strip()
            if opening in {"```", "```json", "```JSON"}:
                if len(lines) >= 3 and lines[-1].strip() == "```":
                    return "\n".join(lines[1:-1]).strip()
                return "\n".join(lines[1:]).strip()
    return text


def parse_comparison_finding_consolidation_response(
    raw_text: str,
) -> dict[str, Any]:
    """Parse provider text, applying quote repair only to unified conclusions."""

    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")
    json_text = _extract_json_text(raw_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        repaired = repair_unescaped_quotes_in_string_fields(
            json_text,
            allowed_field_names=frozenset({"unified_conclusion"}),
        )
        try:
            payload = json.loads(repaired)
        except json.JSONDecodeError:
            raise ComparisonFindingConsolidationParseError(
                f"response is not valid JSON: {exc}"
            ) from exc
    if not isinstance(payload, dict):
        raise ComparisonFindingConsolidationParseError(
            "response must be a JSON object"
        )
    return payload


def _validate_conclusion_alias(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or CONCLUSION_ALIAS_PATTERN.fullmatch(value) is None:
        raise ComparisonFindingConsolidationValidationError(
            f"{context} must match Cddd format: {value!r}"
        )
    return value


def _validate_sentence_alias(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or SENTENCE_ALIAS_PATTERN.fullmatch(value) is None:
        raise ComparisonFindingConsolidationValidationError(
            f"{context} must match Tdddd format: {value!r}"
        )
    return value


def validate_comparison_finding_consolidation_response_structure(
    payload: Mapping[str, Any],
    *,
    input_conclusion_aliases: Sequence[str],
) -> ComparisonFindingConsolidationValidatedResponse:
    """Apply the structural and C-membership hard-validation contract."""

    if not isinstance(payload, Mapping):
        raise ComparisonFindingConsolidationValidationError(
            "response must be an object"
        )
    if set(payload) != {"consolidated_groups"}:
        raise ComparisonFindingConsolidationValidationError(
            "response object must contain exactly one field: consolidated_groups"
        )
    groups = payload["consolidated_groups"]
    if not isinstance(groups, list):
        raise ComparisonFindingConsolidationValidationError(
            "consolidated_groups must be an array"
        )

    input_aliases = tuple(
        _validate_conclusion_alias(alias, context="input_conclusion_aliases[]")
        for alias in input_conclusion_aliases
    )
    if len(set(input_aliases)) != len(input_aliases):
        raise ComparisonFindingConsolidationValidationError(
            "input_conclusion_aliases must not contain duplicates"
        )
    known_aliases = frozenset(input_aliases)
    aliases_used_across_groups: set[str] = set()
    validated_groups: list[ComparisonFindingConsolidatedGroup] = []

    for group_index, group in enumerate(groups):
        group_path = f"consolidated_groups[{group_index}]"
        if not isinstance(group, dict):
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path} must be an object"
            )
        if set(group) != _GROUP_KEYS:
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path} must contain exactly conclusion_aliases, "
                "unified_conclusion, and combined_sentence_aliases"
            )

        aliases_raw = group["conclusion_aliases"]
        if not isinstance(aliases_raw, list):
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path}.conclusion_aliases must be an array"
            )
        aliases = tuple(
            _validate_conclusion_alias(
                alias,
                context=f"{group_path}.conclusion_aliases[{alias_index}]",
            )
            for alias_index, alias in enumerate(aliases_raw)
        )
        if len(set(aliases)) != len(aliases):
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path} contains duplicate conclusion alias within group"
            )
        if not aliases:
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path} must contain at least two distinct conclusion aliases"
            )
        for alias in aliases:
            if alias not in known_aliases:
                raise ComparisonFindingConsolidationValidationError(
                    f"{group_path} contains unknown conclusion alias {alias!r}"
                )
            if alias in aliases_used_across_groups:
                raise ComparisonFindingConsolidationValidationError(
                    f"duplicate conclusion alias across groups: {alias!r}"
                )
            aliases_used_across_groups.add(alias)

        unified_conclusion = group["unified_conclusion"]
        if not isinstance(unified_conclusion, str) or not unified_conclusion.strip():
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path}.unified_conclusion must be a non-empty string"
            )

        combined_raw = group["combined_sentence_aliases"]
        if not isinstance(combined_raw, list):
            raise ComparisonFindingConsolidationValidationError(
                f"{group_path}.combined_sentence_aliases must be an array"
            )
        combined = tuple(
            _validate_sentence_alias(
                alias,
                context=f"{group_path}.combined_sentence_aliases[{alias_index}]",
            )
            for alias_index, alias in enumerate(combined_raw)
        )
        # A well-formed singleton owns its raw alias but performs no merge.
        if len(aliases) == 1:
            continue
        validated_groups.append(
            ComparisonFindingConsolidatedGroup(
                conclusion_aliases=aliases,
                unified_conclusion=unified_conclusion.strip(),
                combined_sentence_aliases=combined,
            )
        )

    return ComparisonFindingConsolidationValidatedResponse(
        consolidated_groups=tuple(validated_groups)
    )


def parse_and_validate_comparison_finding_consolidation_response(
    raw_text: str,
    *,
    input_conclusion_aliases: Sequence[str],
) -> ComparisonFindingConsolidationValidatedResponse:
    payload = parse_comparison_finding_consolidation_response(raw_text)
    return validate_comparison_finding_consolidation_response_structure(
        payload,
        input_conclusion_aliases=input_conclusion_aliases,
    )


def serialize_validated_response(
    validated_response: ComparisonFindingConsolidationValidatedResponse,
) -> dict[str, Any]:
    return {
        "consolidated_groups": [
            {
                "conclusion_aliases": list(group.conclusion_aliases),
                "unified_conclusion": group.unified_conclusion,
                "combined_sentence_aliases": list(
                    group.combined_sentence_aliases
                ),
            }
            for group in validated_response.consolidated_groups
        ]
    }


__all__ = [
    "CONCLUSION_ALIAS_PATTERN",
    "ComparisonFindingConsolidatedGroup",
    "ComparisonFindingConsolidationParseError",
    "ComparisonFindingConsolidationValidatedResponse",
    "ComparisonFindingConsolidationValidationError",
    "parse_and_validate_comparison_finding_consolidation_response",
    "parse_comparison_finding_consolidation_response",
    "serialize_validated_response",
    "validate_comparison_finding_consolidation_response_structure",
]
