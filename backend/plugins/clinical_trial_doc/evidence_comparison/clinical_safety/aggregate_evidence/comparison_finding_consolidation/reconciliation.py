"""Pure mode-local reconciliation for validated consolidation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from ..comparison_mode import ComparisonModeId
from .input_materialization import (
    ComparisonFindingConsolidationFindingProjection,
    ComparisonFindingConsolidationInput,
)
from .response_validation import (
    ComparisonFindingConsolidatedGroup,
    ComparisonFindingConsolidationValidatedResponse,
)

ReconciledFindingLabel = Literal["fail", "need_review"]
_ALLOWED_LABELS = frozenset({"fail", "need_review"})


class ComparisonFindingConsolidationReconciliationError(ValueError):
    """Raised when typed reconciliation inputs violate required invariants."""


@dataclass(frozen=True, slots=True)
class ConsolidatedFindingDraft:
    conclusion: str
    label: ReconciledFindingLabel
    source_sentence_aliases: tuple[str, ...]
    comparison_mode_id: ComparisonModeId
    source_finding_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PassthroughFindingDraft:
    retained_finding_id: str
    conclusion: str
    label: ReconciledFindingLabel
    source_sentence_aliases: tuple[str, ...]
    comparison_mode_id: ComparisonModeId
    source_finding_ids: tuple[str, ...]


ReconciledFindingDraft = ConsolidatedFindingDraft | PassthroughFindingDraft


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationReconciliationResult:
    drafts: tuple[ReconciledFindingDraft, ...]


def _stable_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _validate_projections(
    consolidation_input: ComparisonFindingConsolidationInput,
) -> tuple[
    tuple[ComparisonFindingConsolidationFindingProjection, ...],
    dict[str, ComparisonFindingConsolidationFindingProjection],
]:
    projections = consolidation_input.finding_projections
    projection_by_alias: dict[
        str, ComparisonFindingConsolidationFindingProjection
    ] = {}
    seen_finding_ids: set[str] = set()
    for projection in projections:
        if projection.conclusion_alias in projection_by_alias:
            raise ComparisonFindingConsolidationReconciliationError(
                "duplicate projection conclusion alias: "
                f"{projection.conclusion_alias!r}"
            )
        projection_by_alias[projection.conclusion_alias] = projection
        if projection.finding_id in seen_finding_ids:
            raise ComparisonFindingConsolidationReconciliationError(
                f"duplicate projection finding_id: {projection.finding_id!r}"
            )
        seen_finding_ids.add(projection.finding_id)
        if projection.comparison_mode_id != consolidation_input.comparison_mode_id:
            raise ComparisonFindingConsolidationReconciliationError(
                "projection comparison_mode_id must match consolidation input mode: "
                f"{projection.comparison_mode_id!r}"
            )
        if projection.label not in _ALLOWED_LABELS:
            raise ComparisonFindingConsolidationReconciliationError(
                f"unsupported projection label: {projection.label!r}"
            )
    return projections, projection_by_alias


def _resolve_group_memberships(
    *,
    projections: tuple[ComparisonFindingConsolidationFindingProjection, ...],
    projection_by_alias: dict[
        str, ComparisonFindingConsolidationFindingProjection
    ],
    validated_response: ComparisonFindingConsolidationValidatedResponse,
) -> dict[
    str,
    tuple[
        ComparisonFindingConsolidatedGroup,
        tuple[ComparisonFindingConsolidationFindingProjection, ...],
    ],
]:
    claimed_aliases: set[str] = set()
    membership_by_alias: dict[
        str,
        tuple[
            ComparisonFindingConsolidatedGroup,
            tuple[ComparisonFindingConsolidationFindingProjection, ...],
        ],
    ] = {}
    for group in validated_response.consolidated_groups:
        for alias in group.conclusion_aliases:
            if alias not in projection_by_alias:
                raise ComparisonFindingConsolidationReconciliationError(
                    f"unknown conclusion alias in consolidation group: {alias!r}"
                )
            if alias in claimed_aliases:
                raise ComparisonFindingConsolidationReconciliationError(
                    f"duplicate group membership for conclusion alias: {alias!r}"
                )
            claimed_aliases.add(alias)

        group_aliases = frozenset(group.conclusion_aliases)
        normalized_members = tuple(
            projection
            for projection in projections
            if projection.conclusion_alias in group_aliases
        )
        for member in normalized_members:
            membership_by_alias[member.conclusion_alias] = (
                group,
                normalized_members,
            )
    return membership_by_alias


def _consolidated_draft(
    *,
    mode: ComparisonModeId,
    group: ComparisonFindingConsolidatedGroup,
    members: tuple[ComparisonFindingConsolidationFindingProjection, ...],
) -> ConsolidatedFindingDraft:
    label: ReconciledFindingLabel = (
        "fail" if any(member.label == "fail" for member in members) else "need_review"
    )
    source_sentence_aliases = _stable_unique(
        tuple(
            sentence_alias
            for member in members
            for sentence_alias in member.source_sentence_aliases
        )
    )
    return ConsolidatedFindingDraft(
        conclusion=group.unified_conclusion,
        label=label,
        source_sentence_aliases=source_sentence_aliases,
        comparison_mode_id=mode,
        source_finding_ids=tuple(member.finding_id for member in members),
    )


def _passthrough_draft(
    *,
    mode: ComparisonModeId,
    projection: ComparisonFindingConsolidationFindingProjection,
) -> PassthroughFindingDraft:
    return PassthroughFindingDraft(
        retained_finding_id=projection.finding_id,
        conclusion=projection.conclusion,
        label=cast(ReconciledFindingLabel, projection.label),
        source_sentence_aliases=projection.source_sentence_aliases,
        comparison_mode_id=mode,
        source_finding_ids=(projection.finding_id,),
    )


def _validate_exact_once_conservation(
    *,
    projections: tuple[ComparisonFindingConsolidationFindingProjection, ...],
    drafts: tuple[ReconciledFindingDraft, ...],
) -> None:
    input_finding_ids = {projection.finding_id for projection in projections}
    output_finding_ids = tuple(
        finding_id
        for draft in drafts
        for finding_id in draft.source_finding_ids
    )
    if len(output_finding_ids) != len(set(output_finding_ids)):
        raise ComparisonFindingConsolidationReconciliationError(
            "draft source_finding_ids must be pairwise disjoint"
        )
    if set(output_finding_ids) != input_finding_ids:
        raise ComparisonFindingConsolidationReconciliationError(
            "draft source_finding_ids must exactly conserve input finding IDs"
        )


def reconcile_mode_findings(
    *,
    consolidation_input: ComparisonFindingConsolidationInput,
    validated_response: ComparisonFindingConsolidationValidatedResponse,
) -> ComparisonFindingConsolidationReconciliationResult:
    """Reconcile one mode's validated groups into ordered finding drafts."""

    if not isinstance(consolidation_input, ComparisonFindingConsolidationInput):
        raise TypeError(
            "consolidation_input must be a ComparisonFindingConsolidationInput"
        )
    if not isinstance(
        validated_response,
        ComparisonFindingConsolidationValidatedResponse,
    ):
        raise TypeError(
            "validated_response must be a "
            "ComparisonFindingConsolidationValidatedResponse"
        )

    projections, projection_by_alias = _validate_projections(
        consolidation_input
    )
    membership_by_alias = _resolve_group_memberships(
        projections=projections,
        projection_by_alias=projection_by_alias,
        validated_response=validated_response,
    )
    mode = cast(ComparisonModeId, consolidation_input.comparison_mode_id)

    drafts: list[ReconciledFindingDraft] = []
    for projection in projections:
        membership = membership_by_alias.get(projection.conclusion_alias)
        if membership is None:
            drafts.append(
                _passthrough_draft(mode=mode, projection=projection)
            )
            continue
        group, members = membership
        if projection.conclusion_alias != members[0].conclusion_alias:
            continue
        drafts.append(
            _consolidated_draft(mode=mode, group=group, members=members)
        )

    result = ComparisonFindingConsolidationReconciliationResult(
        drafts=tuple(drafts)
    )
    _validate_exact_once_conservation(
        projections=projections,
        drafts=result.drafts,
    )
    return result


__all__ = [
    "ComparisonFindingConsolidationReconciliationError",
    "ComparisonFindingConsolidationReconciliationResult",
    "ConsolidatedFindingDraft",
    "PassthroughFindingDraft",
    "ReconciledFindingDraft",
    "ReconciledFindingLabel",
    "reconcile_mode_findings",
]
