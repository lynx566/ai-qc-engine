"""Tests for formal findings artifact contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDINGS_ARTIFACT_TYPE,
    FINDINGS_SCHEMA_VERSION,
    build_findings,
    validate_findings,
)


def test_build_and_validate_minimal_findings() -> None:
    payload = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["S0001"]},
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "conclusion": "测试结论",
                        "label": "fail",
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
            }
        ]
    )
    assert payload["artifact_type"] == FINDINGS_ARTIFACT_TYPE
    assert payload["schema_version"] == FINDINGS_SCHEMA_VERSION == "0.2.0"
    validate_findings(payload)


@pytest.mark.parametrize("label", ["fail", "need_review"])
def test_current_findings_accepts_active_labels(label: str) -> None:
    payload = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["S0001"]},
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "conclusion": "active finding",
                        "label": label,
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
            }
        ]
    )

    validate_findings(payload)


def test_current_findings_rejects_pass() -> None:
    with pytest.raises(ValueError, match="label must be fail or need_review"):
        build_findings(
            jobs=[
                {
                    "frozen_job_index": 1,
                    "comparison_mode_id": "scope_local",
                    "comparison_groups": [
                        {"group_role": "scope", "scope_aliases": ["S0001"]},
                    ],
                    "findings": [
                        {
                            "finding_id": "L001",
                            "conclusion": "legacy pass",
                            "label": "pass",
                            "source_sentence_aliases": ["T0001"],
                        }
                    ],
                }
            ]
        )


def test_current_findings_accepts_empty_job_findings() -> None:
    payload = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["S0001"]},
                ],
                "findings": [],
            }
        ]
    )

    validate_findings(payload)


def test_legacy_findings_schema_is_rejected() -> None:
    with pytest.raises(ValueError, match="schema_version must be '0.2.0'"):
        validate_findings(
            {
                "artifact_type": "findings",
                "schema_version": "0.1.0",
                "jobs": [
                    {
                        "frozen_job_index": 1,
                        "comparison_mode_id": "scope_local",
                        "comparison_groups": [
                            {"group_role": "scope", "scope_aliases": ["S0001"]},
                        ],
                        "findings": [],
                    }
                ],
            }
        )


def test_rejects_duplicate_finding_id_across_jobs() -> None:
    with pytest.raises(ValueError, match="duplicate finding_id across artifact"):
        build_findings(
            jobs=[
                {
                    "frozen_job_index": 1,
                    "comparison_mode_id": "scope_local",
                    "comparison_groups": [
                        {"group_role": "scope", "scope_aliases": ["S0001"]},
                    ],
                    "findings": [
                        {
                            "finding_id": "L001",
                            "conclusion": "a",
                            "label": "fail",
                            "source_sentence_aliases": ["T0001"],
                        }
                    ],
                },
                {
                    "frozen_job_index": 2,
                    "comparison_mode_id": "scope_local",
                    "comparison_groups": [
                        {"group_role": "scope", "scope_aliases": ["S0002"]},
                    ],
                    "findings": [
                        {
                            "finding_id": "L001",
                            "conclusion": "b",
                            "label": "fail",
                            "source_sentence_aliases": ["T0002"],
                        }
                    ],
                },
            ]
        )


def test_rejects_invalid_label() -> None:
    with pytest.raises(ValueError, match="label must be fail or need_review"):
        build_findings(
            jobs=[
                {
                    "frozen_job_index": 1,
                    "comparison_mode_id": "ib_to_dsur",
                    "comparison_groups": [
                        {"group_role": "ib_scope", "scope_aliases": ["S0001"]},
                        {"group_role": "dsur_scopes", "scope_aliases": ["S0002"]},
                    ],
                    "findings": [
                        {
                            "finding_id": "L001",
                            "conclusion": "a",
                            "label": "unknown",
                            "source_sentence_aliases": ["T0001"],
                        }
                    ],
                }
            ]
        )
