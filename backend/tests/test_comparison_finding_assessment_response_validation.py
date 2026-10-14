"""Tests for Comparison Finding Assessment response parsing and validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    parse_and_validate_comparison_finding_assessment_response,
    parse_comparison_finding_assessment_response,
)


def _candidate_payload(candidate_focus: str) -> dict:
    return {
        "candidates": [
            {
                "candidate_focus": candidate_focus,
                "label": "fail",
                "trigger_sentence_aliases": ["T0001"],
            }
        ]
    }


def test_valid_json_remains_unchanged() -> None:
    payload = _candidate_payload("明确将腹泻列为不良事件。")

    parsed = parse_comparison_finding_assessment_response(
        json.dumps(payload, ensure_ascii=False)
    )

    assert parsed == payload


def test_fenced_valid_json_remains_supported() -> None:
    payload = _candidate_payload("明确将腹泻列为不良事件。")
    raw_text = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"

    validated = parse_and_validate_comparison_finding_assessment_response(raw_text)

    assert validated.candidates[0].candidate_focus == "明确将腹泻列为不良事件。"


def test_unescaped_quotes_inside_candidate_focus_are_repaired() -> None:
    raw_text = (
        '{"candidates":[{"candidate_focus":"明确将"腹泻"列为不良事件。",'
        '"label":"fail","trigger_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_assessment_response(raw_text)

    assert validated.candidates[0].candidate_focus == "明确将“腹泻”列为不良事件。"


def test_escaped_quotes_inside_candidate_focus_remain_ascii_quotes() -> None:
    raw_text = (
        r'{"candidates":[{"candidate_focus":"明确将\"腹泻\"列为不良事件。",'
        r'"label":"fail","trigger_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_assessment_response(raw_text)

    assert validated.candidates[0].candidate_focus == '明确将"腹泻"列为不良事件。'


def test_unescaped_quotes_in_non_allowed_field_remain_rejected() -> None:
    raw_text = (
        '{"candidates":[{"candidate_focus":"明确将腹泻列为不良事件。",'
        '"label":"need"review","trigger_sentence_aliases":["T0001"]}]}'
    )

    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_assessment_response(raw_text)


def test_unmatched_quote_inside_candidate_focus_remains_rejected() -> None:
    raw_text = (
        '{"candidates":[{"candidate_focus":"明确将"腹泻列为不良事件。",'
        '"label":"fail","trigger_sentence_aliases":["T0001"]}]}'
    )

    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_assessment_response(raw_text)


@pytest.mark.parametrize(
    "raw_text",
    [
        (
            '{"candidates":[{"candidate_focus":"明确将腹泻列为不良事件。" '
            '"label":"fail","trigger_sentence_aliases":["T0001"]}]}'
        ),
        (
            '{"candidates":[{"candidate_focus":"明确将腹泻列为不良事件。",'
            '"label":"fail","trigger_sentence_aliases":["T0001"]}'
        ),
        (
            '{"candidates":[{"candidate_focus":"明确将腹泻列为不良事件。",'
            '"label":"fail","trigger_sentence_aliases":["T0001"]}]} trailing'
        ),
    ],
    ids=["missing-comma", "missing-brackets", "trailing-prose"],
)
def test_broader_structural_corruption_remains_rejected(raw_text: str) -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_assessment_response(raw_text)
