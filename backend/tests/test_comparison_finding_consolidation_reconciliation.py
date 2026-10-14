"""Tests for pure mode-local consolidation reconciliation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    ComparisonFindingConsolidatedGroup,
    ComparisonFindingConsolidationFindingProjection,
    ComparisonFindingConsolidationInput,
    ComparisonFindingConsolidationReconciliationError,
    ComparisonFindingConsolidationReconciliationResult,
    ComparisonFindingConsolidationValidatedResponse,
    ConsolidatedFindingDraft,
    PassthroughFindingDraft,
    reconcile_mode_findings,
)

MODE = "focus_comparison"


def _projection(
    alias: str,
    finding_id: str,
    *,
    label: str = "need_review",
    sentence_aliases: tuple[str, ...] = ("T0001",),
    frozen_job_index: int = 1,
    mode: str = MODE,
) -> ComparisonFindingConsolidationFindingProjection:
    return ComparisonFindingConsolidationFindingProjection(
        conclusion_alias=alias,
        finding_id=finding_id,
        frozen_job_index=frozen_job_index,
        comparison_mode_id=mode,
        label=label,
        conclusion=f"Original {finding_id}",
        source_sentence_aliases=sentence_aliases,
    )


def _input(
    *projections: ComparisonFindingConsolidationFindingProjection,
) -> ComparisonFindingConsolidationInput:
    return ComparisonFindingConsolidationInput(
        comparison_mode_id=MODE,
        finding_projections=projections,
        source_content_text="source",
        conclusions_text="conclusions",
        user_input_text="input",
    )


def _group(
    *aliases: str,
    conclusion: str = "Unified",
    combined_sentence_aliases: tuple[str, ...] = ("T9999",),
) -> ComparisonFindingConsolidatedGroup:
    return ComparisonFindingConsolidatedGroup(
        conclusion_aliases=aliases,
        unified_conclusion=conclusion,
        combined_sentence_aliases=combined_sentence_aliases,
    )


def _response(
    *groups: ComparisonFindingConsolidatedGroup,
) -> ComparisonFindingConsolidationValidatedResponse:
    return ComparisonFindingConsolidationValidatedResponse(
        consolidated_groups=groups
    )


def test_reconciles_reversed_cross_job_group_at_earliest_original_position() -> None:
    consolidation_input = _input(
        _projection("C001", "L900", sentence_aliases=("T0001",)),
        _projection(
            "C002",
            "L020",
            label="fail",
            sentence_aliases=("T0002", "T0003"),
            frozen_job_index=2,
        ),
        _projection("C003", "L700", sentence_aliases=("T0004",)),
        _projection(
            "C004",
            "L010",
            sentence_aliases=("T0003", "T0005"),
            frozen_job_index=5,
        ),
    )

    result = reconcile_mode_findings(
        consolidation_input=consolidation_input,
        validated_response=_response(
            _group(
                "C004",
                "C002",
                conclusion="Merged B and D",
                combined_sentence_aliases=("T9999", "T9999"),
            )
        ),
    )

    assert result == ComparisonFindingConsolidationReconciliationResult(
        drafts=(
            PassthroughFindingDraft(
                retained_finding_id="L900",
                conclusion="Original L900",
                label="need_review",
                source_sentence_aliases=("T0001",),
                comparison_mode_id=MODE,
                source_finding_ids=("L900",),
            ),
            ConsolidatedFindingDraft(
                conclusion="Merged B and D",
                label="fail",
                source_sentence_aliases=("T0002", "T0003", "T0005"),
                comparison_mode_id=MODE,
                source_finding_ids=("L020", "L010"),
            ),
            PassthroughFindingDraft(
                retained_finding_id="L700",
                conclusion="Original L700",
                label="need_review",
                source_sentence_aliases=("T0004",),
                comparison_mode_id=MODE,
                source_finding_ids=("L700",),
            ),
        )
    )


def test_multiple_groups_follow_projection_scan_not_model_group_order() -> None:
    consolidation_input = _input(
        _projection("C001", "L005"),
        _projection("C002", "L004"),
        _projection("C003", "L003"),
        _projection("C004", "L002"),
        _projection("C005", "L001"),
    )

    result = reconcile_mode_findings(
        consolidation_input=consolidation_input,
        validated_response=_response(
            _group("C005", "C003", conclusion="Later group"),
            _group("C004", "C001", conclusion="Earlier group"),
        ),
    )

    assert [draft.conclusion for draft in result.drafts] == [
        "Earlier group",
        "Original L004",
        "Later group",
    ]
    assert result.drafts[0].source_finding_ids == ("L005", "L002")
    assert result.drafts[2].source_finding_ids == ("L003", "L001")
    assert result.drafts[0].label == "need_review"
    assert result.drafts[2].label == "need_review"


def test_empty_validated_groups_make_every_original_a_passthrough() -> None:
    result = reconcile_mode_findings(
        consolidation_input=_input(
            _projection("C001", "L002", label="fail"),
            _projection("C002", "L001"),
        ),
        validated_response=_response(),
    )

    assert [type(draft) for draft in result.drafts] == [
        PassthroughFindingDraft,
        PassthroughFindingDraft,
    ]
    assert [draft.retained_finding_id for draft in result.drafts] == [
        "L002",
        "L001",
    ]


def test_single_group_consumes_all_originals_exactly_once() -> None:
    consolidation_input = _input(
        _projection("C001", "L003"),
        _projection("C002", "L001"),
        _projection("C003", "L002"),
    )

    result = reconcile_mode_findings(
        consolidation_input=consolidation_input,
        validated_response=_response(_group("C003", "C001", "C002")),
    )

    assert result.drafts == (
        ConsolidatedFindingDraft(
            conclusion="Unified",
            label="need_review",
            source_sentence_aliases=("T0001",),
            comparison_mode_id=MODE,
            source_finding_ids=("L003", "L001", "L002"),
        ),
    )
    flattened = [
        finding_id
        for draft in result.drafts
        for finding_id in draft.source_finding_ids
    ]
    assert flattened == ["L003", "L001", "L002"]
    assert len(flattened) == len(set(flattened))


@pytest.mark.parametrize(
    ("consolidation_input", "validated_response", "message"),
    [
        (
            _input(
                _projection("C001", "L001"),
                _projection("C001", "L002"),
            ),
            _response(),
            "duplicate projection conclusion alias",
        ),
        (
            _input(
                _projection("C001", "L001"),
                _projection("C002", "L001"),
            ),
            _response(),
            "duplicate projection finding_id",
        ),
        (
            _input(_projection("C001", "L001", mode="scope_local")),
            _response(),
            "projection comparison_mode_id",
        ),
        (
            _input(_projection("C001", "L001", label="pass")),
            _response(),
            "unsupported projection label",
        ),
        (
            _input(
                _projection("C001", "L001"),
                _projection("C002", "L002"),
            ),
            _response(_group("C001", "C999")),
            "unknown conclusion alias",
        ),
        (
            _input(
                _projection("C001", "L001"),
                _projection("C002", "L002"),
            ),
            _response(_group("C001", "C001")),
            "duplicate group membership",
        ),
        (
            _input(
                _projection("C001", "L001"),
                _projection("C002", "L002"),
                _projection("C003", "L003"),
            ),
            _response(
                _group("C001", "C002"),
                _group("C002", "C003"),
            ),
            "duplicate group membership",
        ),
    ],
)
def test_rejects_inconsistent_manually_constructed_typed_inputs(
    consolidation_input: ComparisonFindingConsolidationInput,
    validated_response: ComparisonFindingConsolidationValidatedResponse,
    message: str,
) -> None:
    with pytest.raises(
        ComparisonFindingConsolidationReconciliationError,
        match=message,
    ):
        reconcile_mode_findings(
            consolidation_input=consolidation_input,
            validated_response=validated_response,
        )


def test_empty_input_and_empty_groups_produce_empty_result() -> None:
    assert reconcile_mode_findings(
        consolidation_input=_input(),
        validated_response=_response(),
    ) == ComparisonFindingConsolidationReconciliationResult(drafts=())
