"""Tests for consolidation response parsing and hard validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.response_validation import (
    ComparisonFindingConsolidationParseError,
    ComparisonFindingConsolidationValidationError,
    parse_and_validate_comparison_finding_consolidation_response,
    parse_comparison_finding_consolidation_response,
    serialize_validated_response,
    validate_comparison_finding_consolidation_response_structure,
)

INPUT_ALIASES = ("C001", "C002", "C003")


def _group(
    aliases: list[str] | None = None,
    *,
    unified_conclusion: str = "合并结论",
    combined_sentence_aliases: list[str] | None = None,
) -> dict:
    return {
        "conclusion_aliases": aliases or ["C001", "C002"],
        "unified_conclusion": unified_conclusion,
        "combined_sentence_aliases": (
            ["T0001", "T0002"]
            if combined_sentence_aliases is None
            else combined_sentence_aliases
        ),
    }


def test_raw_and_fenced_json_parse_to_the_same_validated_response() -> None:
    payload = {"consolidated_groups": [_group()]}
    raw = json.dumps(payload, ensure_ascii=False)

    direct = parse_and_validate_comparison_finding_consolidation_response(
        raw,
        input_conclusion_aliases=INPUT_ALIASES,
    )
    fenced = parse_and_validate_comparison_finding_consolidation_response(
        f"```json\n{raw}\n```",
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert direct == fenced
    assert serialize_validated_response(direct) == payload


def test_empty_consolidated_groups_is_valid() -> None:
    validated = validate_comparison_finding_consolidation_response_structure(
        {"consolidated_groups": []},
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert validated.consolidated_groups == ()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "exactly one field"),
        ({"consolidated_groups": [], "extra": True}, "exactly one field"),
        ({"consolidated_groups": {}}, "must be an array"),
        ({"consolidated_groups": ["group"]}, "must be an object"),
        (
            {
                "consolidated_groups": [
                    {
                        "conclusion_aliases": ["C001", "C002"],
                        "unified_conclusion": "Valid",
                    }
                ]
            },
            "must contain exactly",
        ),
        (
            {"consolidated_groups": [_group(unified_conclusion="  ")]},
            "must be a non-empty string",
        ),
        (
            {"consolidated_groups": [_group(["C01", "C002"])]},
            "must match Cddd format",
        ),
        (
            {
                "consolidated_groups": [
                    _group(combined_sentence_aliases=["T001", "T0002"])
                ]
            },
            "must match Tdddd format",
        ),
    ],
)
def test_schema_and_field_contract_is_strict(payload: dict, message: str) -> None:
    with pytest.raises(ComparisonFindingConsolidationValidationError, match=message):
        validate_comparison_finding_consolidation_response_structure(
            payload,
            input_conclusion_aliases=INPUT_ALIASES,
        )


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        ([_group(["C001", "C999"])], "unknown conclusion alias"),
        ([_group(["C001", "C001"])], "duplicate conclusion alias within group"),
        (
            [_group(["C001", "C002"]), _group(["C002", "C003"])],
            "duplicate conclusion alias across groups",
        ),
        ([_group(["C001"])], "at least two distinct conclusion aliases"),
    ],
)
def test_alias_membership_invariants_are_hard_validation(
    groups: list[dict],
    message: str,
) -> None:
    with pytest.raises(ComparisonFindingConsolidationValidationError, match=message):
        validate_comparison_finding_consolidation_response_structure(
            {"consolidated_groups": groups},
            input_conclusion_aliases=INPUT_ALIASES,
        )


def test_reported_sentence_alias_union_mismatch_is_not_hard_validation() -> None:
    validated = validate_comparison_finding_consolidation_response_structure(
        {
            "consolidated_groups": [
                _group(combined_sentence_aliases=["T9999", "T9999"])
            ]
        },
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert validated.consolidated_groups[0].combined_sentence_aliases == (
        "T9999",
        "T9999",
    )


def test_unescaped_quotes_are_repaired_only_in_unified_conclusion() -> None:
    raw = (
        '{"consolidated_groups":[{"conclusion_aliases":["C001","C002"],'
        '"unified_conclusion":"Issue "term" differs",'
        '"combined_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_consolidation_response(
        raw,
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert validated.consolidated_groups[0].unified_conclusion == (
        "Issue “term” differs"
    )


def test_unescaped_quotes_outside_unified_conclusion_remain_parse_failure() -> None:
    raw = (
        '{"consolidated_groups":[{"conclusion_aliases":["C"001","C002"],'
        '"unified_conclusion":"Valid",'
        '"combined_sentence_aliases":["T0001"]}]}'
    )

    with pytest.raises(ComparisonFindingConsolidationParseError, match="valid JSON"):
        parse_comparison_finding_consolidation_response(raw)


def test_parse_failure_and_validation_failure_use_distinct_errors() -> None:
    with pytest.raises(ComparisonFindingConsolidationParseError):
        parse_comparison_finding_consolidation_response("not json")

    with pytest.raises(ComparisonFindingConsolidationValidationError):
        parse_and_validate_comparison_finding_consolidation_response(
            '{"consolidated_groups":{}}',
            input_conclusion_aliases=INPUT_ALIASES,
        )


@pytest.mark.parametrize("opening", ["```json", "```JSON", "```"])
def test_opening_only_fence_parses_valid_consolidation_json(opening: str) -> None:
    payload = {"consolidated_groups": [_group()]}
    raw = " \n\t" + opening + "\r\n" + json.dumps(payload) + "\n "

    validated = parse_and_validate_comparison_finding_consolidation_response(
        raw,
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert serialize_validated_response(validated) == payload


def test_opening_only_fence_preserves_existing_quote_repair() -> None:
    raw = (
        '```json\n'
        '{"consolidated_groups":[{"conclusion_aliases":["C001","C002"],'
        '"unified_conclusion":"Issue "term" differs",'
        '"combined_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_consolidation_response(
        raw,
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert validated.consolidated_groups[0].unified_conclusion == (
        "Issue \u201cterm\u201d differs"
    )


@pytest.mark.parametrize(
    "raw",
    [
        '```json\nnot json at all',
        '```json\nnot json at all\n```',
        '```json\n{"consolidated_groups":[]',
        '```json\n{"consolidated_groups":[]}\nExplanation',
        '```json\n{"consolidated_groups":[]}\n```\nExplanation',
        'Here is the result:\n```json\n{"consolidated_groups":[]}\n```',
        '```python\n{"consolidated_groups":[]}',
        '```json {"consolidated_groups":[]}',
        '```json\n{"consolidated_groups":[{"conclusion_aliases":["C"001","C002"],'
        '"unified_conclusion":"Valid","combined_sentence_aliases":["T0001"]}]}',
    ],
)
def test_fence_handling_does_not_accept_malformed_json_or_prose(raw: str) -> None:
    with pytest.raises(ComparisonFindingConsolidationParseError):
        parse_comparison_finding_consolidation_response(raw)


def test_opening_only_fence_does_not_bypass_structure_validation() -> None:
    with pytest.raises(ComparisonFindingConsolidationValidationError):
        parse_and_validate_comparison_finding_consolidation_response(
            '```json\n{"consolidated_groups":{}}',
            input_conclusion_aliases=INPUT_ALIASES,
        )


def test_opening_only_fence_preserves_backticks_inside_conclusion() -> None:
    payload = {"consolidated_groups": [_group(unified_conclusion="Issue `term` differs")]}

    validated = parse_and_validate_comparison_finding_consolidation_response(
        "```json\n" + json.dumps(payload),
        input_conclusion_aliases=INPUT_ALIASES,
    )

    assert serialize_validated_response(validated) == payload
