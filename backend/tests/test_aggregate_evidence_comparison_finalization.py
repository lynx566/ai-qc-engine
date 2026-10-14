"""Tests for deterministic aggregate product-final finding assembly."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import (
    finalization as finalization_module,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    ComparisonFindingConsolidatedGroup,
    ComparisonFindingConsolidationExecution,
    ComparisonFindingConsolidationInput,
    ComparisonFindingConsolidationReconciliationResult,
    ComparisonFindingConsolidationValidatedResponse,
    PassthroughFindingDraft,
    ResolvedComparisonFindingConsolidationConfig,
    compute_comparison_finding_consolidation_alias_qc,
    materialize_comparison_finding_consolidation_projections,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.finalization import (
    AggregateEvidenceComparisonFinalizationError,
    finalize_aggregate_evidence_comparison,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.job_final_selection import (
    select_job_final_rows_for_mode,
)


def _finding(
    finding_id: str,
    conclusion: str,
    alias: str,
    *,
    label: str = "need_review",
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "conclusion": conclusion,
        "label": label,
        "source_sentence_aliases": [alias],
    }


def _row(
    frozen_job_index: int,
    comparison_mode_id: str,
    *findings: dict[str, object],
) -> dict[str, object]:
    return {
        "frozen_job_index": frozen_job_index,
        "comparison_mode_id": comparison_mode_id,
        "comparison_groups": [
            {"group_role": "scope", "scope_aliases": ["H0001"]}
        ],
        "findings": list(findings),
    }


def _group(
    *aliases: str,
    conclusion: str = "Unified conclusion",
    sentence_aliases: tuple[str, ...] = ("T0001", "T0002"),
) -> ComparisonFindingConsolidatedGroup:
    return ComparisonFindingConsolidatedGroup(
        conclusion_aliases=aliases,
        unified_conclusion=conclusion,
        combined_sentence_aliases=sentence_aliases,
    )


def _execution(
    rows: list[dict[str, object]],
    *,
    mode: str,
    outcome: str = "success",
    groups: tuple[ComparisonFindingConsolidatedGroup, ...] = (),
) -> ComparisonFindingConsolidationExecution:
    projections = materialize_comparison_finding_consolidation_projections(
        comparison_mode_id=mode,
        selected_job_final_rows=rows,
    )
    consolidation_input = ComparisonFindingConsolidationInput(
        comparison_mode_id=mode,
        finding_projections=projections,
        source_content_text="source",
        conclusions_text="conclusions",
        user_input_text="input",
    )
    if outcome == "noop":
        validated = ComparisonFindingConsolidationValidatedResponse(
            consolidated_groups=()
        )
        return ComparisonFindingConsolidationExecution(
            comparison_mode_id=mode,
            status="success",
            prompt_id="prompt",
            prompt_version="0.1.0",
            provider_called=False,
            parse_status="not_attempted",
            validation_status="not_attempted",
            consolidation_input=consolidation_input,
            validated_response=validated,
            alias_qc=compute_comparison_finding_consolidation_alias_qc(
                finding_projections=projections,
                validated_response=validated,
            ),
            finding_count=len(projections),
        )
    if outcome == "success":
        validated = ComparisonFindingConsolidationValidatedResponse(
            consolidated_groups=groups
        )
        return ComparisonFindingConsolidationExecution(
            comparison_mode_id=mode,
            status="success",
            prompt_id="prompt",
            prompt_version="0.1.0",
            provider_called=True,
            parse_status="success",
            validation_status="success",
            consolidation_input=consolidation_input,
            validated_response=validated,
            alias_qc=compute_comparison_finding_consolidation_alias_qc(
                finding_projections=projections,
                validated_response=validated,
            ),
            finding_count=len(projections),
            group_count=len(groups),
            raw_response_text="{}",
        )
    failure_statuses = {
        "provider_failure": ("not_attempted", "not_attempted"),
        "parse_failure": ("failed", "not_attempted"),
        "validation_failure": ("success", "failed"),
    }
    parse_status, validation_status = failure_statuses[outcome]
    return ComparisonFindingConsolidationExecution(
        comparison_mode_id=mode,
        status="failed",
        prompt_id="prompt",
        prompt_version="0.1.0",
        provider_called=True,
        parse_status=parse_status,
        validation_status=validation_status,
        consolidation_input=consolidation_input,
        finding_count=len(projections),
        error_message=outcome,
    )


def _config(*modes: str) -> ResolvedComparisonFindingConsolidationConfig:
    return ResolvedComparisonFindingConsolidationConfig(
        enabled_comparison_modes=modes  # type: ignore[arg-type]
    )


def test_shared_selector_preserves_authoritative_row_order() -> None:
    rows = [
        _row(4, "scope_local", _finding("L004", "Scope", "T0004")),
        _row(1, "focus_comparison", _finding("L001", "First", "T0001")),
        _row(3, "focus_comparison", _finding("L003", "Second", "T0003")),
    ]

    selected = select_job_final_rows_for_mode(
        job_final_rows=rows,
        comparison_mode_id="focus_comparison",
    )

    assert selected == (rows[1], rows[2])


def test_disabled_modes_identity_passthrough_in_global_row_order() -> None:
    rows = [
        _row(5, "focus_comparison", _finding("L010", "First", "T0001")),
        _row(
            2,
            "scope_local",
            _finding("L002", "Second", "T0002", label="fail"),
        ),
    ]

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=(),
        consolidation_config=_config(),
    )

    assert payload["finalization_status"] == "completed"
    assert payload["fallback_comparison_modes"] == []
    assert payload["findings"] == [
        {
            "finding_id": "L010",
            "label": "need_review",
            "conclusion": "First",
            "source_sentence_aliases": ["T0001"],
            "comparison_mode_id": "focus_comparison",
            "source_finding_ids": ["L010"],
        },
        {
            "finding_id": "L002",
            "label": "fail",
            "conclusion": "Second",
            "source_sentence_aliases": ["T0002"],
            "comparison_mode_id": "scope_local",
            "source_finding_ids": ["L002"],
        },
    ]


def test_automatic_noop_uses_identity_without_calling_b2(monkeypatch) -> None:
    rows = [
        _row(1, "focus_comparison", _finding("L007", "Only", "T0001"))
    ]
    execution = _execution(rows, mode="focus_comparison", outcome="noop")

    def _unexpected_b2_call(**_kwargs):
        raise AssertionError("automatic no-op must not call B2")

    monkeypatch.setattr(
        finalization_module,
        "reconcile_mode_findings",
        _unexpected_b2_call,
    )

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=(execution,),
        consolidation_config=_config("focus_comparison"),
    )

    assert payload["findings"][0]["finding_id"] == "L007"
    assert payload["fallback_comparison_modes"] == []


def test_validated_groups_call_b2_and_allocate_after_global_max() -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L009", "One", "T0001", label="fail"),
            _finding("L003", "Two", "T0002"),
        )
    ]
    execution = _execution(
        rows,
        mode="focus_comparison",
        groups=(_group("C002", "C001"),),
    )

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=(execution,),
        consolidation_config=_config("focus_comparison"),
    )

    assert payload["findings"] == [
        {
            "finding_id": "L010",
            "label": "fail",
            "conclusion": "Unified conclusion",
            "source_sentence_aliases": ["T0001", "T0002"],
            "comparison_mode_id": "focus_comparison",
            "source_finding_ids": ["L009", "L003"],
        }
    ]


def test_validated_empty_groups_call_b2(monkeypatch) -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "One", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    execution = _execution(rows, mode="focus_comparison")
    real_reconcile = finalization_module.reconcile_mode_findings
    calls = 0

    def _recording_reconcile(**kwargs):
        nonlocal calls
        calls += 1
        return real_reconcile(**kwargs)

    monkeypatch.setattr(
        finalization_module,
        "reconcile_mode_findings",
        _recording_reconcile,
    )

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=(execution,),
        consolidation_config=_config("focus_comparison"),
    )

    assert calls == 1
    assert [finding["finding_id"] for finding in payload["findings"]] == [
        "L001",
        "L002",
    ]


@pytest.mark.parametrize(
    "outcome",
    ["provider_failure", "parse_failure", "validation_failure"],
)
def test_operational_failures_fallback_whole_mode(outcome: str) -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "One", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    execution = _execution(rows, mode="focus_comparison", outcome=outcome)

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=(execution,),
        consolidation_config=_config("focus_comparison"),
    )

    assert payload["finalization_status"] == "completed_with_fallback"
    assert payload["fallback_comparison_modes"] == ["focus_comparison"]
    assert [finding["finding_id"] for finding in payload["findings"]] == [
        "L001",
        "L002",
    ]


def test_execution_provenance_is_checked_before_failure_fallback() -> None:
    authoritative_rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "Authoritative", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    wrong_rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "Wrong conclusion", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    execution = _execution(
        wrong_rows,
        mode="focus_comparison",
        outcome="provider_failure",
    )

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="projections.*authoritative",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=authoritative_rows,
            consolidation_executions=(execution,),
            consolidation_config=_config("focus_comparison"),
        )


def test_alias_qc_mismatch_remains_normal_success() -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "One", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    execution = _execution(
        rows,
        mode="focus_comparison",
        groups=(
            _group(
                "C001",
                "C002",
                sentence_aliases=("T9999",),
            ),
        ),
    )
    assert execution.alias_qc is not None
    assert execution.alias_qc.all_groups_match is False

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=(execution,),
        consolidation_config=_config("focus_comparison"),
    )

    assert payload["finalization_status"] == "completed"
    assert payload["fallback_comparison_modes"] == []
    assert payload["findings"][0]["source_sentence_aliases"] == [
        "T0001",
        "T0002",
    ]


def test_enabled_mode_requires_exactly_one_execution() -> None:
    rows = [
        _row(1, "focus_comparison", _finding("L001", "One", "T0001"))
    ]

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="missing consolidation execution",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(),
            consolidation_config=_config("focus_comparison"),
        )

    execution = _execution(rows, mode="focus_comparison", outcome="noop")
    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="duplicate consolidation execution",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(execution, execution),
            consolidation_config=_config("focus_comparison"),
        )


def test_execution_for_disabled_mode_is_invariant_failure() -> None:
    rows = [
        _row(1, "focus_comparison", _finding("L001", "One", "T0001"))
    ]
    execution = _execution(rows, mode="focus_comparison", outcome="noop")

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="disabled comparison mode",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(execution,),
            consolidation_config=_config(),
        )


def test_cross_mode_merge_and_id_allocation_follow_global_placement() -> None:
    focus_rows = [
        _row(
            5,
            "focus_comparison",
            _finding("L020", "Focus one", "T0001"),
            _finding("L003", "Focus two", "T0002"),
        )
    ]
    scope_rows = [
        _row(
            1,
            "scope_local",
            _finding("L004", "Scope one", "T0003"),
            _finding("L010", "Scope two", "T0004"),
        )
    ]
    rows = [*focus_rows, *scope_rows]
    executions = (
        _execution(scope_rows, mode="scope_local", groups=(_group("C001", "C002"),)),
        _execution(focus_rows, mode="focus_comparison", groups=(_group("C001", "C002"),)),
    )

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=rows,
        consolidation_executions=executions,
        consolidation_config=_config("scope_local", "focus_comparison"),
    )

    assert [finding["comparison_mode_id"] for finding in payload["findings"]] == [
        "focus_comparison",
        "scope_local",
    ]
    assert [finding["finding_id"] for finding in payload["findings"]] == [
        "L021",
        "L022",
    ]


def test_fallback_modes_use_artifact_canonical_order_not_config_order() -> None:
    scope_rows = [
        _row(
            1,
            "scope_local",
            _finding("L001", "One", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    focus_rows = [
        _row(
            2,
            "focus_comparison",
            _finding("L003", "Three", "T0003"),
            _finding("L004", "Four", "T0004"),
        )
    ]

    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=[*scope_rows, *focus_rows],
        consolidation_executions=(
            _execution(focus_rows, mode="focus_comparison", outcome="parse_failure"),
            _execution(scope_rows, mode="scope_local", outcome="provider_failure"),
        ),
        consolidation_config=_config("focus_comparison", "scope_local"),
    )

    assert payload["fallback_comparison_modes"] == [
        "scope_local",
        "focus_comparison",
    ]


def test_malformed_execution_state_is_not_fallback() -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "One", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    valid = _execution(rows, mode="focus_comparison", outcome="provider_failure")
    malformed = ComparisonFindingConsolidationExecution(
        comparison_mode_id=valid.comparison_mode_id,
        status="failed",
        prompt_id=valid.prompt_id,
        prompt_version=valid.prompt_version,
        provider_called=False,
        parse_status=valid.parse_status,
        validation_status=valid.validation_status,
        consolidation_input=valid.consolidation_input,
        finding_count=valid.finding_count,
        error_message=valid.error_message,
    )

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="invalid consolidation execution state",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(malformed,),
            consolidation_config=_config("focus_comparison"),
        )


def test_malformed_execution_input_uses_finalization_error_boundary() -> None:
    rows = [
        _row(1, "focus_comparison", _finding("L001", "One", "T0001"))
    ]
    malformed = ComparisonFindingConsolidationExecution(
        comparison_mode_id="focus_comparison",
        status="success",
        prompt_id="prompt",
        prompt_version="0.1.0",
        provider_called=False,
        parse_status="not_attempted",
        validation_status="not_attempted",
        consolidation_input=None,  # type: ignore[arg-type]
    )

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="consolidation input",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(malformed,),
            consolidation_config=_config("focus_comparison"),
        )


def test_failure_with_fewer_than_two_findings_is_not_a_legitimate_fallback() -> None:
    rows = [
        _row(1, "focus_comparison", _finding("L001", "One", "T0001"))
    ]
    malformed = _execution(
        rows,
        mode="focus_comparison",
        outcome="provider_failure",
    )

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="invalid consolidation execution state",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(malformed,),
            consolidation_config=_config("focus_comparison"),
        )


@pytest.mark.parametrize("branch", ["validated_success", "automatic_noop"])
def test_malformed_typed_execution_payload_uses_finalization_error_boundary(
    branch: str,
) -> None:
    finding_count = 2 if branch == "validated_success" else 1
    rows = [
        _row(
            1,
            "focus_comparison",
            *(
                _finding(f"L{index:03d}", f"Finding {index}", f"T{index:04d}")
                for index in range(1, finding_count + 1)
            ),
        )
    ]
    execution = _execution(
        rows,
        mode="focus_comparison",
        outcome="success" if finding_count == 2 else "noop",
    )
    malformed = (
        replace(execution, validated_response={})
        if branch == "validated_success"
        else replace(execution, alias_qc={})
    )

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="invalid consolidation execution state",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(malformed,),
            consolidation_config=_config("focus_comparison"),
        )


@pytest.mark.parametrize("bad_source_ids", [("L001", "L001"), ("L001",)])
def test_aggregate_conservation_rejects_duplicate_or_missing_sources(
    monkeypatch,
    bad_source_ids: tuple[str, ...],
) -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L001", "One", "T0001"),
            _finding("L002", "Two", "T0002"),
        )
    ]
    execution = _execution(rows, mode="focus_comparison")

    def _invalid_reconciliation(**_kwargs):
        return ComparisonFindingConsolidationReconciliationResult(
            drafts=tuple(
                PassthroughFindingDraft(
                    retained_finding_id=source_id,
                    conclusion="Invalid",
                    label="need_review",
                    source_sentence_aliases=("T0001",),
                    comparison_mode_id="focus_comparison",
                    source_finding_ids=(source_id,),
                )
                for source_id in bad_source_ids
            )
        )

    monkeypatch.setattr(
        finalization_module,
        "reconcile_mode_findings",
        _invalid_reconciliation,
    )

    with pytest.raises(AggregateEvidenceComparisonFinalizationError):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(execution,),
            consolidation_config=_config("focus_comparison"),
        )


def test_consolidated_id_overflow_fails_at_allocator_boundary() -> None:
    rows = [
        _row(
            1,
            "focus_comparison",
            _finding("L999", "One", "T0001"),
            _finding("L998", "Two", "T0002"),
        )
    ]
    execution = _execution(
        rows,
        mode="focus_comparison",
        groups=(_group("C001", "C002"),),
    )

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="L999",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(execution,),
            consolidation_config=_config("focus_comparison"),
        )


def test_empty_job_final_rows_build_empty_completed_artifact() -> None:
    payload = finalize_aggregate_evidence_comparison(
        job_final_rows=(),
        consolidation_executions=(),
        consolidation_config=_config(),
    )

    assert payload == {
        "artifact_type": "final_findings",
        "schema_version": "0.1.0",
        "finalization_status": "completed",
        "fallback_comparison_modes": [],
        "findings": [],
    }


def test_final_artifact_builder_failure_is_explicit_not_fallback(monkeypatch) -> None:
    rows = [
        _row(1, "scope_local", _finding("L001", "One", "T0001"))
    ]

    def _broken_builder(**_kwargs):
        raise ValueError("builder rejected payload")

    monkeypatch.setattr(finalization_module, "build_final_findings", _broken_builder)

    with pytest.raises(
        AggregateEvidenceComparisonFinalizationError,
        match="builder rejected payload",
    ):
        finalize_aggregate_evidence_comparison(
            job_final_rows=rows,
            consolidation_executions=(),
            consolidation_config=_config(),
        )
