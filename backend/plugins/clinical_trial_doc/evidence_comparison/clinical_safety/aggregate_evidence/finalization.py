"""Pure deterministic product-final assembly for aggregate findings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.final_findings import (
    FINAL_FINDINGS_COMPARISON_MODE_ORDER,
    build_final_findings,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDING_ID_PATTERN,
    build_findings,
)

from .comparison_finding_consolidation.alias_qc import (
    ComparisonFindingConsolidationAliasQcResult,
)
from .comparison_finding_consolidation.config import (
    ResolvedComparisonFindingConsolidationConfig,
)
from .comparison_finding_consolidation.execution import (
    ComparisonFindingConsolidationExecution,
)
from .comparison_finding_consolidation.input_materialization import (
    ComparisonFindingConsolidationFindingProjection,
    ComparisonFindingConsolidationInput,
    materialize_comparison_finding_consolidation_projections,
)
from .comparison_finding_consolidation.reconciliation import (
    ConsolidatedFindingDraft,
    PassthroughFindingDraft,
    ReconciledFindingDraft,
    ReconciledFindingLabel,
    reconcile_mode_findings,
)
from .comparison_finding_consolidation.response_validation import (
    ComparisonFindingConsolidationValidatedResponse,
)
from .comparison_mode import ComparisonModeId
from .job_final_selection import select_job_final_rows_for_mode

_ExecutionRoute = Literal["validated_success", "automatic_noop", "fallback"]


class AggregateEvidenceComparisonFinalizationError(ValueError):
    """Raised when deterministic aggregate finalization invariants fail."""


def _validate_job_final_rows(
    job_final_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(job_final_rows, Sequence) or isinstance(
        job_final_rows, (str, bytes)
    ):
        raise TypeError("job_final_rows must be a sequence")
    rows = tuple(job_final_rows)
    if not rows:
        return rows
    try:
        build_findings(jobs=rows)
    except (TypeError, ValueError) as exc:
        raise AggregateEvidenceComparisonFinalizationError(
            f"invalid job-final rows: {exc}"
        ) from exc
    return rows


def _index_executions(
    *,
    consolidation_executions: Sequence[ComparisonFindingConsolidationExecution],
    consolidation_config: ResolvedComparisonFindingConsolidationConfig,
) -> dict[str, ComparisonFindingConsolidationExecution]:
    if not isinstance(
        consolidation_config,
        ResolvedComparisonFindingConsolidationConfig,
    ):
        raise TypeError(
            "consolidation_config must be a "
            "ResolvedComparisonFindingConsolidationConfig"
        )
    if not isinstance(consolidation_executions, Sequence) or isinstance(
        consolidation_executions, (str, bytes)
    ):
        raise TypeError("consolidation_executions must be a sequence")

    by_mode: dict[str, ComparisonFindingConsolidationExecution] = {}
    for index, execution in enumerate(consolidation_executions):
        if not isinstance(execution, ComparisonFindingConsolidationExecution):
            raise TypeError(
                f"consolidation_executions[{index}] must be a "
                "ComparisonFindingConsolidationExecution"
            )
        mode = execution.comparison_mode_id
        if mode in by_mode:
            raise AggregateEvidenceComparisonFinalizationError(
                f"duplicate consolidation execution for comparison mode {mode!r}"
            )
        by_mode[mode] = execution

    enabled_modes = set(consolidation_config.enabled_comparison_modes)
    execution_modes = set(by_mode)
    missing = enabled_modes - execution_modes
    if missing:
        raise AggregateEvidenceComparisonFinalizationError(
            "missing consolidation execution for enabled comparison mode(s): "
            f"{sorted(missing)!r}"
        )
    extra = execution_modes - enabled_modes
    if extra:
        raise AggregateEvidenceComparisonFinalizationError(
            "consolidation execution supplied for disabled comparison mode(s): "
            f"{sorted(extra)!r}"
        )
    return by_mode


def _expected_projections(
    *,
    mode: str,
    selected_rows: Sequence[Mapping[str, Any]],
) -> tuple[ComparisonFindingConsolidationFindingProjection, ...]:
    try:
        return materialize_comparison_finding_consolidation_projections(
            comparison_mode_id=mode,
            selected_job_final_rows=selected_rows,
        )
    except (TypeError, ValueError) as exc:
        raise AggregateEvidenceComparisonFinalizationError(
            f"cannot project authoritative rows for mode {mode!r}: {exc}"
        ) from exc


def _validate_execution_provenance(
    *,
    mode: str,
    execution: ComparisonFindingConsolidationExecution,
    expected_projections: tuple[
        ComparisonFindingConsolidationFindingProjection, ...
    ],
) -> None:
    if execution.comparison_mode_id != mode:
        raise AggregateEvidenceComparisonFinalizationError(
            "consolidation execution comparison mode does not match routing mode"
        )
    consolidation_input = execution.consolidation_input
    if not isinstance(consolidation_input, ComparisonFindingConsolidationInput):
        raise AggregateEvidenceComparisonFinalizationError(
            "consolidation input must be a "
            "ComparisonFindingConsolidationInput"
        )
    if consolidation_input.comparison_mode_id != mode:
        raise AggregateEvidenceComparisonFinalizationError(
            "consolidation input comparison mode does not match routing mode"
        )
    if consolidation_input.finding_projections != expected_projections:
        raise AggregateEvidenceComparisonFinalizationError(
            "execution projections do not match authoritative selected "
            f"job-final rows for mode {mode!r}"
        )


def _invalid_execution_state(
    execution: ComparisonFindingConsolidationExecution,
) -> AggregateEvidenceComparisonFinalizationError:
    return AggregateEvidenceComparisonFinalizationError(
        "invalid consolidation execution state for comparison mode "
        f"{execution.comparison_mode_id!r}"
    )


def _classify_execution(
    execution: ComparisonFindingConsolidationExecution,
) -> _ExecutionRoute:
    finding_count = execution.consolidation_input.finding_count
    if execution.finding_count != finding_count:
        raise _invalid_execution_state(execution)

    if execution.status == "success" and execution.provider_called:
        if not (
            finding_count >= 2
            and execution.parse_status == "success"
            and execution.validation_status == "success"
            and isinstance(
                execution.validated_response,
                ComparisonFindingConsolidationValidatedResponse,
            )
            and isinstance(
                execution.alias_qc,
                ComparisonFindingConsolidationAliasQcResult,
            )
            and execution.group_count
            == len(execution.validated_response.consolidated_groups)
            and execution.error_message is None
        ):
            raise _invalid_execution_state(execution)
        return "validated_success"

    if execution.status == "success" and not execution.provider_called:
        if not (
            finding_count < 2
            and execution.parse_status == "not_attempted"
            and execution.validation_status == "not_attempted"
            and isinstance(
                execution.validated_response,
                ComparisonFindingConsolidationValidatedResponse,
            )
            and execution.validated_response.consolidated_groups == ()
            and isinstance(
                execution.alias_qc,
                ComparisonFindingConsolidationAliasQcResult,
            )
            and execution.alias_qc.groups == ()
            and execution.group_count == 0
            and execution.error_message is None
        ):
            raise _invalid_execution_state(execution)
        return "automatic_noop"

    recognized_failure_statuses = {
        ("not_attempted", "not_attempted"),
        ("failed", "not_attempted"),
        ("success", "failed"),
    }
    if execution.status == "failed":
        if not (
            finding_count >= 2
            and execution.provider_called
            and (execution.parse_status, execution.validation_status)
            in recognized_failure_statuses
            and execution.validated_response is None
            and execution.alias_qc is None
            and execution.group_count == 0
        ):
            raise _invalid_execution_state(execution)
        return "fallback"

    raise _invalid_execution_state(execution)


def _identity_drafts(
    *,
    mode: str,
    projections: Sequence[ComparisonFindingConsolidationFindingProjection],
) -> tuple[PassthroughFindingDraft, ...]:
    typed_mode = cast(ComparisonModeId, mode)
    return tuple(
        PassthroughFindingDraft(
            retained_finding_id=projection.finding_id,
            conclusion=projection.conclusion,
            label=cast(ReconciledFindingLabel, projection.label),
            source_sentence_aliases=projection.source_sentence_aliases,
            comparison_mode_id=typed_mode,
            source_finding_ids=(projection.finding_id,),
        )
        for projection in projections
    )


def _global_positions(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    positions: dict[str, int] = {}
    for row in rows:
        for finding in row["findings"]:
            finding_id = finding["finding_id"]
            if finding_id in positions:
                raise AggregateEvidenceComparisonFinalizationError(
                    f"duplicate job-final finding_id: {finding_id!r}"
                )
            positions[finding_id] = len(positions)
    return positions


def _merge_and_validate_drafts(
    *,
    drafts: Sequence[ReconciledFindingDraft],
    global_position_by_finding_id: Mapping[str, int],
) -> tuple[ReconciledFindingDraft, ...]:
    claimed_ids: set[str] = set()
    placed: list[tuple[int, ReconciledFindingDraft]] = []
    claimed_placements: set[int] = set()
    for draft in drafts:
        unknown = set(draft.source_finding_ids) - set(
            global_position_by_finding_id
        )
        if unknown:
            raise AggregateEvidenceComparisonFinalizationError(
                f"final draft contains unknown source finding IDs: {sorted(unknown)!r}"
            )
        reused = claimed_ids.intersection(draft.source_finding_ids)
        if reused:
            raise AggregateEvidenceComparisonFinalizationError(
                "source finding IDs must be pairwise disjoint across final drafts: "
                f"{sorted(reused)!r}"
            )
        claimed_ids.update(draft.source_finding_ids)
        placement = min(
            global_position_by_finding_id[finding_id]
            for finding_id in draft.source_finding_ids
        )
        if placement in claimed_placements:
            raise AggregateEvidenceComparisonFinalizationError(
                f"duplicate aggregate-global draft placement: {placement}"
            )
        claimed_placements.add(placement)
        placed.append((placement, draft))

    expected_ids = set(global_position_by_finding_id)
    if claimed_ids != expected_ids:
        missing = sorted(expected_ids - claimed_ids)
        extra = sorted(claimed_ids - expected_ids)
        raise AggregateEvidenceComparisonFinalizationError(
            "final drafts must exactly conserve all job-final finding IDs; "
            f"missing={missing!r}, unknown={extra!r}"
        )
    placed.sort(key=lambda item: item[0])
    return tuple(draft for _placement, draft in placed)


def _max_original_sequence(finding_ids: Sequence[str]) -> int:
    maximum = 0
    for finding_id in finding_ids:
        if FINDING_ID_PATTERN.fullmatch(finding_id) is None:
            raise AggregateEvidenceComparisonFinalizationError(
                f"invalid job-final finding_id: {finding_id!r}"
            )
        maximum = max(maximum, int(finding_id[1:]))
    return maximum


def _serialize_final_findings(
    *,
    drafts: Sequence[ReconciledFindingDraft],
    original_finding_ids: Sequence[str],
) -> list[dict[str, Any]]:
    next_sequence = _max_original_sequence(original_finding_ids) + 1
    findings: list[dict[str, Any]] = []
    final_ids: set[str] = set()
    for draft in drafts:
        if isinstance(draft, PassthroughFindingDraft):
            finding_id = draft.retained_finding_id
        elif isinstance(draft, ConsolidatedFindingDraft):
            if next_sequence > 999:
                raise AggregateEvidenceComparisonFinalizationError(
                    "consolidated finding ID allocation exceeds L999"
                )
            finding_id = f"L{next_sequence:03d}"
            next_sequence += 1
        else:  # pragma: no cover - closed union, retained as a defensive seam.
            raise AggregateEvidenceComparisonFinalizationError(
                f"unsupported reconciled draft type: {type(draft)!r}"
            )
        if finding_id in final_ids:
            raise AggregateEvidenceComparisonFinalizationError(
                f"duplicate product-final finding_id: {finding_id!r}"
            )
        final_ids.add(finding_id)
        findings.append(
            {
                "finding_id": finding_id,
                "label": draft.label,
                "conclusion": draft.conclusion,
                "source_sentence_aliases": list(draft.source_sentence_aliases),
                "comparison_mode_id": draft.comparison_mode_id,
                "source_finding_ids": list(draft.source_finding_ids),
            }
        )
    return findings


def finalize_aggregate_evidence_comparison(
    *,
    job_final_rows: Sequence[Mapping[str, Any]],
    consolidation_executions: Sequence[ComparisonFindingConsolidationExecution],
    consolidation_config: ResolvedComparisonFindingConsolidationConfig,
) -> dict[str, Any]:
    """Build one validated in-memory product-final findings payload."""

    rows = _validate_job_final_rows(job_final_rows)
    execution_by_mode = _index_executions(
        consolidation_executions=consolidation_executions,
        consolidation_config=consolidation_config,
    )
    enabled_modes = set(consolidation_config.enabled_comparison_modes)
    all_drafts: list[ReconciledFindingDraft] = []
    fallback_modes: set[str] = set()

    for mode in FINAL_FINDINGS_COMPARISON_MODE_ORDER:
        selected_rows = select_job_final_rows_for_mode(
            job_final_rows=rows,
            comparison_mode_id=mode,
        )
        expected_projections = _expected_projections(
            mode=mode,
            selected_rows=selected_rows,
        )
        if mode not in enabled_modes:
            all_drafts.extend(
                _identity_drafts(mode=mode, projections=expected_projections)
            )
            continue

        execution = execution_by_mode[mode]
        _validate_execution_provenance(
            mode=mode,
            execution=execution,
            expected_projections=expected_projections,
        )
        route = _classify_execution(execution)
        if route == "validated_success":
            assert execution.validated_response is not None
            try:
                reconciliation = reconcile_mode_findings(
                    consolidation_input=execution.consolidation_input,
                    validated_response=execution.validated_response,
                )
            except (TypeError, ValueError) as exc:
                raise AggregateEvidenceComparisonFinalizationError(
                    f"mode-local reconciliation failed for mode {mode!r}: {exc}"
                ) from exc
            all_drafts.extend(reconciliation.drafts)
        else:
            all_drafts.extend(
                _identity_drafts(mode=mode, projections=expected_projections)
            )
            if route == "fallback":
                fallback_modes.add(mode)

    global_positions = _global_positions(rows)
    ordered_drafts = _merge_and_validate_drafts(
        drafts=all_drafts,
        global_position_by_finding_id=global_positions,
    )
    original_finding_ids = tuple(global_positions)
    findings = _serialize_final_findings(
        drafts=ordered_drafts,
        original_finding_ids=original_finding_ids,
    )
    ordered_fallback_modes = tuple(
        mode
        for mode in FINAL_FINDINGS_COMPARISON_MODE_ORDER
        if mode in fallback_modes
    )
    finalization_status = (
        "completed_with_fallback" if ordered_fallback_modes else "completed"
    )
    try:
        return build_final_findings(
            finalization_status=finalization_status,
            fallback_comparison_modes=ordered_fallback_modes,
            findings=findings,
        )
    except (TypeError, ValueError) as exc:
        raise AggregateEvidenceComparisonFinalizationError(
            f"product-final artifact validation failed: {exc}"
        ) from exc


__all__ = [
    "AggregateEvidenceComparisonFinalizationError",
    "finalize_aggregate_evidence_comparison",
]
