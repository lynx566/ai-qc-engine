"""Tests for generic consolidation input materialization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.input_materialization import (
    materialize_comparison_finding_consolidation_input,
)


def _aggregate_evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "primary",
                "aggregate_evidence_source_bundle_id": "bundle-primary",
                "doc_id": "doc-primary",
                "file_hash": "sha256:primary",
                "scopes": [
                    {
                        "scope_id": "scope-primary",
                        "scope_alias": "H0001",
                        "heading_path": ["Safety", "Deaths"],
                        "units": [
                            {
                                "unit_id": "unit-primary",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "sentence-primary-1",
                                        "sentence_alias": "T0001",
                                        "text": "Primary sentence one.",
                                    },
                                    {
                                        "sentence_id": "sentence-primary-2",
                                        "sentence_alias": "T0002",
                                        "text": "Primary sentence two.",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "role_id": "secondary",
                "aggregate_evidence_source_bundle_id": "bundle-secondary",
                "doc_id": "doc-secondary",
                "file_hash": "sha256:secondary",
                "scopes": [
                    {
                        "scope_id": "scope-secondary",
                        "scope_alias": "H0002",
                        "heading_path": ["Safety", "Exposure"],
                        "units": [
                            {
                                "unit_id": "unit-secondary",
                                "unit_alias": "U0002",
                                "sentences": [
                                    {
                                        "sentence_id": "sentence-secondary-1",
                                        "sentence_alias": "T0003",
                                        "text": "Secondary sentence.",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]
    )


def _row(index: int, *findings: dict, mode: str = "focus_comparison") -> dict:
    return {
        "frozen_job_index": index,
        "comparison_mode_id": mode,
        "comparison_groups": [
            {"group_role": "focus_scope", "scope_aliases": ["H0001"]}
        ],
        "findings": list(findings),
    }


def _finding(
    finding_id: str,
    conclusion: str,
    aliases: list[str],
    *,
    label: str = "fail",
) -> dict:
    return {
        "finding_id": finding_id,
        "conclusion": conclusion,
        "label": label,
        "source_sentence_aliases": aliases,
    }


def test_materializer_flattens_rows_in_order_with_deterministic_aliases() -> None:
    rows = [
        _row(
            2,
            _finding("L010", "First conclusion", ["T0002"]),
            _finding("L011", "Second conclusion", ["T0001", "T0002"]),
        ),
        _row(
            5,
            _finding(
                "L020",
                "Third conclusion",
                ["T0003"],
                label="need_review",
            ),
        ),
    ]

    first = materialize_comparison_finding_consolidation_input(
        comparison_mode_id="focus_comparison",
        aggregate_comparison_evidence=_aggregate_evidence(),
        selected_job_final_rows=rows,
    )
    second = materialize_comparison_finding_consolidation_input(
        comparison_mode_id="focus_comparison",
        aggregate_comparison_evidence=_aggregate_evidence(),
        selected_job_final_rows=rows,
    )

    assert first == second
    assert first.comparison_mode_id == "focus_comparison"
    assert [item.conclusion_alias for item in first.finding_projections] == [
        "C001",
        "C002",
        "C003",
    ]
    assert [item.finding_id for item in first.finding_projections] == [
        "L010",
        "L011",
        "L020",
    ]
    assert [item.frozen_job_index for item in first.finding_projections] == [2, 2, 5]
    assert first.finding_projections[2].label == "need_review"
    assert first.finding_projections[1].source_sentence_aliases == (
        "T0001",
        "T0002",
    )


def test_materializer_renders_complete_source_and_unlabelled_conclusions() -> None:
    materialized = materialize_comparison_finding_consolidation_input(
        comparison_mode_id="focus_comparison",
        aggregate_comparison_evidence=_aggregate_evidence(),
        selected_job_final_rows=[
            _row(
                1,
                _finding("L001", "First conclusion", ["T0001"]),
                _finding("L002", "Second conclusion", ["T0003"]),
            )
        ],
    )

    assert materialized.user_input_text.startswith("## Source Content\n")
    for fragment in (
        "Participant: primary",
        "Scope: Safety / Deaths [H0001]",
        "Unit U0001",
        "- Primary sentence one. [T0001]",
        "- Primary sentence two. [T0002]",
        "Participant: secondary",
        "Scope: Safety / Exposure [H0002]",
        "Unit U0002",
        "- Secondary sentence. [T0003]",
        "## Conclusions",
        "Conclusion C001",
        "- `conclusion`: First conclusion",
        "- `source_sentence_aliases`: T0001",
        "Conclusion C002",
        "- `source_sentence_aliases`: T0003",
    ):
        assert fragment in materialized.user_input_text
    assert "`label`" not in materialized.user_input_text
    assert materialized.user_input_text.index("Participant: primary") < (
        materialized.user_input_text.index("Participant: secondary")
    )


def test_materializer_preserves_traceable_alias_mapping_and_empty_rows() -> None:
    empty = materialize_comparison_finding_consolidation_input(
        comparison_mode_id="future_mode",
        aggregate_comparison_evidence=_aggregate_evidence(),
        selected_job_final_rows=[],
    )
    assert empty.finding_projections == ()
    assert empty.alias_mapping == ()
    assert empty.finding_count == 0
    assert empty.user_input_text.endswith("## Conclusions\n")

    populated = materialize_comparison_finding_consolidation_input(
        comparison_mode_id="focus_comparison",
        aggregate_comparison_evidence=_aggregate_evidence(),
        selected_job_final_rows=[
            _row(7, _finding("L031", "Trace me", ["T0002"]))
        ],
    )
    assert populated.alias_mapping == (
        {
            "conclusion_alias": "C001",
            "finding_id": "L031",
            "frozen_job_index": 7,
            "comparison_mode_id": "focus_comparison",
            "label": "fail",
            "conclusion": "Trace me",
            "source_sentence_aliases": ["T0002"],
        },
    )


def test_materializer_rejects_malformed_and_non_homogeneous_rows() -> None:
    with pytest.raises(ValueError, match="keys mismatch"):
        materialize_comparison_finding_consolidation_input(
            comparison_mode_id="focus_comparison",
            aggregate_comparison_evidence=_aggregate_evidence(),
            selected_job_final_rows=[{"comparison_mode_id": "focus_comparison"}],
        )

    rows = [
        _row(1, _finding("L001", "One", ["T0001"])),
        _row(
            2,
            _finding("L002", "Two", ["T0002"]),
            mode="scope_local",
        ),
    ]
    with pytest.raises(ValueError, match="must match comparison_mode_id"):
        materialize_comparison_finding_consolidation_input(
            comparison_mode_id="focus_comparison",
            aggregate_comparison_evidence=_aggregate_evidence(),
            selected_job_final_rows=rows,
        )


def test_materializer_rejects_rows_for_a_different_explicit_mode() -> None:
    with pytest.raises(ValueError, match="must match comparison_mode_id"):
        materialize_comparison_finding_consolidation_input(
            comparison_mode_id="scope_local",
            aggregate_comparison_evidence=_aggregate_evidence(),
            selected_job_final_rows=[
                _row(1, _finding("L001", "One", ["T0001"]))
            ],
        )
