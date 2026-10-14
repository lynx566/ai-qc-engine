"""Tests for Comparison Finding Verification response validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    parse_and_validate_comparison_finding_verification_response,
    parse_comparison_finding_verification_response,
    serialize_validated_response,
    validate_comparison_finding_verification_response_structure,
)


def _validate(raw: dict, *, input_finding_ids: list[str]) -> None:
    validate_comparison_finding_verification_response_structure(
        raw,
        input_finding_ids=input_finding_ids,
    )


def test_invalid_json_fails() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_verification_response("not-json")


def _revised_payload(conclusion: str) -> dict:
    return {
        "finding_verifications": [
            {
                "finding_id": "L001",
                "verification_result": "revised",
                "conclusion": conclusion,
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ]
    }


def test_valid_conclusion_remains_unchanged() -> None:
    payload = _revised_payload("明确将腹泻列为不良事件。")

    parsed = parse_comparison_finding_verification_response(
        json.dumps(payload, ensure_ascii=False)
    )

    assert parsed == payload


def test_fenced_valid_conclusion_remains_supported() -> None:
    payload = _revised_payload("明确将腹泻列为不良事件。")
    raw_text = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"

    validated = parse_and_validate_comparison_finding_verification_response(
        raw_text,
        input_finding_ids=["L001"],
    )

    assert validated.finding_verifications[0].conclusion == "明确将腹泻列为不良事件。"


def test_unescaped_quotes_inside_revised_conclusion_are_repaired() -> None:
    raw_text = (
        '{"finding_verifications":[{"finding_id":"L001",'
        '"verification_result":"revised","conclusion":"明确将"腹泻"列为不良事件。",'
        '"label":"fail","source_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_verification_response(
        raw_text,
        input_finding_ids=["L001"],
    )

    assert validated.finding_verifications[0].conclusion == "明确将“腹泻”列为不良事件。"


def test_unescaped_quotes_inside_additional_conclusion_are_repaired() -> None:
    raw_text = (
        '{"finding_verifications":[],"additional_findings":['
        '{"conclusion":"明确将"腹泻"列为不良事件。","label":"fail",'
        '"source_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_verification_response(
        raw_text,
        input_finding_ids=[],
    )

    assert validated.additional_findings[0].conclusion == "明确将“腹泻”列为不良事件。"


def test_escaped_quotes_inside_conclusion_remain_ascii_quotes() -> None:
    raw_text = (
        r'{"finding_verifications":[{"finding_id":"L001",'
        r'"verification_result":"revised","conclusion":"明确将\"腹泻\"列为不良事件。",'
        r'"label":"fail","source_sentence_aliases":["T0001"]}]}'
    )

    validated = parse_and_validate_comparison_finding_verification_response(
        raw_text,
        input_finding_ids=["L001"],
    )

    assert validated.finding_verifications[0].conclusion == '明确将"腹泻"列为不良事件。'


def test_unescaped_quotes_in_non_allowed_field_remain_rejected() -> None:
    raw_text = (
        '{"finding_verifications":[{"finding_id":"L001",'
        '"verification_result":"revised","conclusion":"明确将腹泻列为不良事件。",'
        '"label":"need"review","source_sentence_aliases":["T0001"]}]}'
    )

    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_verification_response(raw_text)


def test_unmatched_quote_inside_conclusion_remains_rejected() -> None:
    raw_text = (
        '{"finding_verifications":[{"finding_id":"L001",'
        '"verification_result":"revised","conclusion":"明确将"腹泻列为不良事件。",'
        '"label":"fail","source_sentence_aliases":["T0001"]}]}'
    )

    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_verification_response(raw_text)


@pytest.mark.parametrize(
    "raw_text",
    [
        (
            '{"finding_verifications":[{"finding_id":"L001",'
            '"verification_result":"revised","conclusion":"明确将腹泻列为不良事件。" '
            '"label":"fail","source_sentence_aliases":["T0001"]}]}'
        ),
        (
            '{"finding_verifications":[{"finding_id":"L001",'
            '"verification_result":"revised","conclusion":"明确将腹泻列为不良事件。",'
            '"label":"fail","source_sentence_aliases":["T0001"]}'
        ),
        (
            '{"finding_verifications":[{"finding_id":"L001",'
            '"verification_result":"revised","conclusion":"明确将腹泻列为不良事件。",'
            '"label":"fail","source_sentence_aliases":["T0001"]}]} trailing'
        ),
    ],
    ids=["missing-comma", "missing-brackets", "trailing-prose"],
)
def test_broader_structural_corruption_remains_rejected(raw_text: str) -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_comparison_finding_verification_response(raw_text)


def test_wrong_top_level_shape_fails() -> None:
    with pytest.raises(ValueError, match="finding_verifications"):
        _validate({"candidates": []}, input_finding_ids=[])


def test_unknown_top_level_field_fails() -> None:
    with pytest.raises(ValueError, match="finding_verifications and optionally"):
        _validate(
            {"finding_verifications": [], "extra": []},
            input_finding_ids=[],
        )


def test_missing_finding_verifications_fails() -> None:
    with pytest.raises(ValueError, match="finding_verifications and optionally"):
        _validate({}, input_finding_ids=[])


def test_finding_verifications_must_be_array() -> None:
    with pytest.raises(ValueError, match="must be an array"):
        _validate({"finding_verifications": "bad"}, input_finding_ids=[])


def test_confirmed_entry_valid() -> None:
    _validate(
        {
            "finding_verifications": [
                {"finding_id": "L001", "verification_result": "confirmed"},
            ]
        },
        input_finding_ids=["L001"],
    )


def test_confirmed_entry_extra_fields_fail() -> None:
    with pytest.raises(ValueError, match="exactly finding_id and verification_result"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L001",
                        "verification_result": "confirmed",
                        "conclusion": "extra",
                    }
                ]
            },
            input_finding_ids=["L001"],
        )


def test_rejected_entry_extra_fields_fail() -> None:
    with pytest.raises(ValueError, match="exactly finding_id and verification_result"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L001",
                        "verification_result": "rejected",
                        "conclusion": "extra",
                    }
                ]
            },
            input_finding_ids=["L001"],
        )


def test_revised_entry_requires_all_fields() -> None:
    with pytest.raises(ValueError, match="exactly finding_id"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L002",
                        "verification_result": "revised",
                        "conclusion": "bad",
                    }
                ]
            },
            input_finding_ids=["L002"],
        )


def test_revised_entry_valid() -> None:
    _validate(
        {
            "finding_verifications": [
                {
                    "finding_id": "L002",
                    "verification_result": "revised",
                    "conclusion": "corrected",
                    "label": "fail",
                    "source_sentence_aliases": ["T0001", "T0002"],
                }
            ]
        },
        input_finding_ids=["L002"],
    )


def test_revised_invalid_label_fails() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L002",
                        "verification_result": "revised",
                        "conclusion": "bad",
                        "label": "unknown",
                        "source_sentence_aliases": ["T0001"],
                    }
                ]
            },
            input_finding_ids=["L002"],
        )


def test_revised_empty_conclusion_fails() -> None:
    with pytest.raises(ValueError, match="conclusion must be a non-empty string"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L002",
                        "verification_result": "revised",
                        "conclusion": "   ",
                        "label": "fail",
                        "source_sentence_aliases": ["T0001"],
                    }
                ]
            },
            input_finding_ids=["L002"],
        )


def test_revised_malformed_alias_fails() -> None:
    with pytest.raises(ValueError, match="Tdddd format"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L002",
                        "verification_result": "revised",
                        "conclusion": "bad",
                        "label": "fail",
                        "source_sentence_aliases": ["BAD"],
                    }
                ]
            },
            input_finding_ids=["L002"],
        )


def test_finding_coverage_exact_match_passes() -> None:
    _validate(
        {
            "finding_verifications": [
                {"finding_id": "L001", "verification_result": "confirmed"},
                {"finding_id": "L002", "verification_result": "confirmed"},
                {"finding_id": "L003", "verification_result": "confirmed"},
            ]
        },
        input_finding_ids=["L001", "L002", "L003"],
    )


def test_finding_coverage_missing_id_fails() -> None:
    with pytest.raises(ValueError, match="exactly once"):
        _validate(
            {
                "finding_verifications": [
                    {"finding_id": "L001", "verification_result": "confirmed"},
                    {"finding_id": "L003", "verification_result": "confirmed"},
                ]
            },
            input_finding_ids=["L001", "L002", "L003"],
        )


def test_finding_coverage_unknown_id_fails() -> None:
    with pytest.raises(ValueError, match="exactly once"):
        _validate(
            {
                "finding_verifications": [
                    {"finding_id": "L001", "verification_result": "confirmed"},
                    {"finding_id": "L002", "verification_result": "confirmed"},
                    {"finding_id": "L003", "verification_result": "confirmed"},
                    {"finding_id": "L004", "verification_result": "confirmed"},
                ]
            },
            input_finding_ids=["L001", "L002", "L003"],
        )


def test_finding_coverage_duplicate_id_fails() -> None:
    with pytest.raises(ValueError, match="exactly once"):
        _validate(
            {
                "finding_verifications": [
                    {"finding_id": "L001", "verification_result": "confirmed"},
                    {"finding_id": "L001", "verification_result": "confirmed"},
                    {"finding_id": "L002", "verification_result": "confirmed"},
                    {"finding_id": "L003", "verification_result": "confirmed"},
                ]
            },
            input_finding_ids=["L001", "L002", "L003"],
        )


def test_empty_findings_input_allows_empty_verifications() -> None:
    _validate({"finding_verifications": []}, input_finding_ids=[])


def test_empty_findings_with_additional_findings_passes() -> None:
    _validate(
        {
            "finding_verifications": [],
            "additional_findings": [
                {
                    "conclusion": "missed issue",
                    "label": "fail",
                    "source_sentence_aliases": ["T0001"],
                }
            ],
        },
        input_finding_ids=[],
    )


def test_additional_findings_absent_passes() -> None:
    _validate(
        {
            "finding_verifications": [
                {"finding_id": "L001", "verification_result": "confirmed"}
            ]
        },
        input_finding_ids=["L001"],
    )


def test_additional_findings_empty_array_passes() -> None:
    _validate(
        {"finding_verifications": [], "additional_findings": []},
        input_finding_ids=[],
    )


def test_additional_findings_label_pass_fails() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        _validate(
            {
                "finding_verifications": [],
                "additional_findings": [
                    {
                        "conclusion": "issue",
                        "label": "pass",
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
            },
            input_finding_ids=[],
        )


def test_additional_findings_extra_field_fails() -> None:
    with pytest.raises(ValueError, match="exactly conclusion"):
        _validate(
            {
                "finding_verifications": [],
                "additional_findings": [
                    {
                        "conclusion": "issue",
                        "label": "fail",
                        "source_sentence_aliases": ["T0001"],
                        "finding_id": "L999",
                    }
                ],
            },
            input_finding_ids=[],
        )


def test_out_of_job_alias_syntax_passes_slice_2b_boundary() -> None:
    _validate(
        {
            "finding_verifications": [
                {
                    "finding_id": "L001",
                    "verification_result": "revised",
                    "conclusion": "corrected",
                    "label": "fail",
                    "source_sentence_aliases": ["T9999"],
                }
            ],
            "additional_findings": [
                {
                    "conclusion": "extra",
                    "label": "fail",
                    "source_sentence_aliases": ["T9998"],
                }
            ],
        },
        input_finding_ids=["L001"],
    )


def test_parse_and_validate_accepts_fenced_json() -> None:
    payload = json.dumps(
        {
            "finding_verifications": [
                {"finding_id": "L001", "verification_result": "confirmed"},
            ]
        }
    )
    raw = f"```json\n{payload}\n```"
    validated = parse_and_validate_comparison_finding_verification_response(
        raw,
        input_finding_ids=["L001"],
    )
    assert len(validated.finding_verifications) == 1


@pytest.mark.parametrize("verification_result", ["confirmed", "rejected"])
def test_terminal_verification_result_accepts_exact_keys(
    verification_result: str,
) -> None:
    validated = validate_comparison_finding_verification_response_structure(
        {
            "finding_verifications": [
                {
                    "finding_id": "L001",
                    "verification_result": verification_result,
                }
            ]
        },
        input_finding_ids=["L001"],
    )
    assert validated.finding_verifications[0].verification_result == verification_result


@pytest.mark.parametrize("legacy_result", ["correct", "incorrect"])
def test_legacy_verification_result_fails(legacy_result: str) -> None:
    with pytest.raises(ValueError, match="must be one of"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L001",
                        "verification_result": legacy_result,
                    }
                ]
            },
            input_finding_ids=["L001"],
        )


@pytest.mark.parametrize("label", ["fail", "need_review"])
def test_revised_accepts_assessment_labels(label: str) -> None:
    _validate(
        {
            "finding_verifications": [
                {
                    "finding_id": "L001",
                    "verification_result": "revised",
                    "conclusion": "修正后的问题",
                    "label": label,
                    "source_sentence_aliases": ["T0001"],
                }
            ]
        },
        input_finding_ids=["L001"],
    )


def test_revised_label_pass_fails() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        _validate(
            {
                "finding_verifications": [
                    {
                        "finding_id": "L001",
                        "verification_result": "revised",
                        "conclusion": "修正后的问题",
                        "label": "pass",
                        "source_sentence_aliases": ["T0001"],
                    }
                ]
            },
            input_finding_ids=["L001"],
        )


@pytest.mark.parametrize("label", ["fail", "need_review"])
def test_additional_finding_accepts_assessment_labels(label: str) -> None:
    _validate(
        {
            "finding_verifications": [],
            "additional_findings": [
                {
                    "conclusion": "遗漏的问题",
                    "label": label,
                    "source_sentence_aliases": ["T0001"],
                }
            ],
        },
        input_finding_ids=[],
    )


def test_serializer_preserves_rejected_and_need_review_additional_finding() -> None:
    validated = validate_comparison_finding_verification_response_structure(
        {
            "finding_verifications": [
                {"finding_id": "L001", "verification_result": "rejected"}
            ],
            "additional_findings": [
                {
                    "conclusion": "遗漏的问题",
                    "label": "need_review",
                    "source_sentence_aliases": ["T0001"],
                }
            ],
        },
        input_finding_ids=["L001"],
    )

    assert serialize_validated_response(validated) == {
        "finding_verifications": [
            {"finding_id": "L001", "verification_result": "rejected"}
        ],
        "additional_findings": [
            {
                "conclusion": "遗漏的问题",
                "label": "need_review",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    }
