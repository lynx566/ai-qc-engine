"""Tests for non-failing consolidation sentence-alias QC."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.alias_qc import (
    compute_comparison_finding_consolidation_alias_qc,
    serialize_alias_qc,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.input_materialization import (
    ComparisonFindingConsolidationFindingProjection,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.response_validation import (
    ComparisonFindingConsolidatedGroup,
    ComparisonFindingConsolidationValidatedResponse,
)


def _projection(alias: str, sentence_aliases: tuple[str, ...]):
    return ComparisonFindingConsolidationFindingProjection(
        conclusion_alias=alias,
        finding_id=f"L{int(alias[1:]):03d}",
        frozen_job_index=1,
        comparison_mode_id="runtime_mode",
        label="fail",
        conclusion=f"Conclusion {alias}",
        source_sentence_aliases=sentence_aliases,
    )


def _response(reported: tuple[str, ...]):
    return ComparisonFindingConsolidationValidatedResponse(
        consolidated_groups=(
            ComparisonFindingConsolidatedGroup(
                conclusion_aliases=("C001", "C002"),
                unified_conclusion="Unified",
                combined_sentence_aliases=reported,
            ),
        )
    )


def test_alias_qc_exactly_matches_first_occurrence_union() -> None:
    result = compute_comparison_finding_consolidation_alias_qc(
        finding_projections=(
            _projection("C001", ("T0002", "T0001")),
            _projection("C002", ("T0001", "T0003")),
        ),
        validated_response=_response(("T0002", "T0001", "T0003")),
    )

    group = result.groups[0]
    assert group.expected_sentence_aliases == ("T0002", "T0001", "T0003")
    assert group.reported_sentence_aliases == ("T0002", "T0001", "T0003")
    assert group.missing_sentence_aliases == ()
    assert group.unexpected_sentence_aliases == ()
    assert group.duplicate_reported_sentence_aliases == ()
    assert group.combined_aliases_match is True
    assert result.mismatch_count == 0
    assert result.all_groups_match is True


def test_alias_qc_records_missing_unexpected_duplicates_without_failing() -> None:
    result = compute_comparison_finding_consolidation_alias_qc(
        finding_projections=(
            _projection("C001", ("T0001", "T0002")),
            _projection("C002", ("T0002", "T0003")),
        ),
        validated_response=_response(("T0001", "T9999", "T9999")),
    )

    group = result.groups[0]
    assert group.expected_sentence_aliases == ("T0001", "T0002", "T0003")
    assert group.reported_sentence_aliases == ("T0001", "T9999", "T9999")
    assert group.missing_sentence_aliases == ("T0002", "T0003")
    assert group.unexpected_sentence_aliases == ("T9999",)
    assert group.duplicate_reported_sentence_aliases == ("T9999",)
    assert group.combined_aliases_match is False
    assert result.mismatch_count == 1
    assert result.all_groups_match is False
    assert serialize_alias_qc(result) == {
        "all_groups_match": False,
        "mismatch_count": 1,
        "groups": [
            {
                "group_index": 1,
                "conclusion_aliases": ["C001", "C002"],
                "expected": ["T0001", "T0002", "T0003"],
                "reported": ["T0001", "T9999", "T9999"],
                "missing": ["T0002", "T0003"],
                "unexpected": ["T9999"],
                "duplicates": ["T9999"],
                "combined_aliases_match": False,
            }
        ],
    }
