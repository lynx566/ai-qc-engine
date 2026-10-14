"""Deterministic job planner for clinical-safety Comparison Finding Assessment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_aggregate_comparison_evidence,
)

from ..comparison_mode import ComparisonModeId
from .config import ResolvedClinicalSafetyComparisonFindingAssessmentConfig
from .jobs import ComparisonFindingAssessmentGroup, ComparisonFindingAssessmentJob
from .scope_selection import select_scope_aliases_by_heading_profile


def _scope_aliases_for_participant(
    participant: Mapping[str, Any],
    *,
    role_id: str,
) -> tuple[str, ...]:
    scopes = participant.get("scopes")
    if not isinstance(scopes, list):
        raise TypeError(f"participant {role_id!r} scopes must be a list")
    aliases: list[str] = []
    for index, scope in enumerate(scopes):
        if not isinstance(scope, Mapping):
            raise TypeError(
                f"participant {role_id!r} scopes[{index}] must be a mapping"
            )
        scope_alias = scope.get("scope_alias")
        if not isinstance(scope_alias, str) or not scope_alias.strip():
            raise ValueError(
                f"participant {role_id!r} scopes[{index}].scope_alias "
                "must be a non-empty string"
            )
        aliases.append(scope_alias.strip())
    return tuple(aliases)


def _participant_lookup(
    evidence: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    participants = evidence.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ValueError("aggregate_comparison_evidence participants must be non-empty")
    lookup: dict[str, Mapping[str, Any]] = {}
    for index, participant in enumerate(participants):
        if not isinstance(participant, Mapping):
            raise TypeError(f"participants[{index}] must be a mapping")
        role_id = participant.get("role_id")
        if not isinstance(role_id, str) or not role_id.strip():
            raise ValueError(
                f"participants[{index}].role_id must be a non-empty string"
            )
        normalized_role = role_id.strip()
        if normalized_role in lookup:
            raise ValueError(f"duplicate participant role_id={normalized_role!r}")
        lookup[normalized_role] = participant
    return lookup


def _require_participant(
    *,
    participants_by_role: Mapping[str, Mapping[str, Any]],
    role_id: str,
) -> Mapping[str, Any]:
    participant = participants_by_role.get(role_id)
    if participant is None:
        raise ValueError(
            f"participant role_id={role_id!r} is not present in aggregate evidence"
        )
    return participant


def _plan_scope_local_jobs(
    *,
    scope_aliases: Sequence[str],
) -> tuple[ComparisonFindingAssessmentJob, ...]:
    return tuple(
        ComparisonFindingAssessmentJob(
            comparison_mode_id="scope_local",
            groups=(
                ComparisonFindingAssessmentGroup(
                    group_role="scope",
                    scope_aliases=(alias,),
                ),
            ),
        )
        for alias in scope_aliases
    )


def _plan_focus_comparison_jobs(
    *,
    scope_aliases: Sequence[str],
) -> tuple[ComparisonFindingAssessmentJob, ...]:
    if len(scope_aliases) < 2:
        return ()
    jobs: list[ComparisonFindingAssessmentJob] = []
    for focus_alias in scope_aliases:
        comparison_aliases = tuple(
            alias for alias in scope_aliases if alias != focus_alias
        )
        jobs.append(
            ComparisonFindingAssessmentJob(
                comparison_mode_id="focus_comparison",
                groups=(
                    ComparisonFindingAssessmentGroup(
                        group_role="focus_scope",
                        scope_aliases=(focus_alias,),
                    ),
                    ComparisonFindingAssessmentGroup(
                        group_role="comparison_scopes",
                        scope_aliases=comparison_aliases,
                    ),
                ),
            )
        )
    return tuple(jobs)


def _plan_ib_to_dsur_jobs(
    *,
    focus_scope_aliases: Sequence[str],
    comparison_scope_aliases: Sequence[str],
) -> tuple[ComparisonFindingAssessmentJob, ...]:
    if not focus_scope_aliases or not comparison_scope_aliases:
        return ()
    comparison_group = tuple(comparison_scope_aliases)
    return tuple(
        ComparisonFindingAssessmentJob(
            comparison_mode_id="ib_to_dsur",
            groups=(
                ComparisonFindingAssessmentGroup(
                    group_role="ib_scope",
                    scope_aliases=(focus_alias,),
                ),
                ComparisonFindingAssessmentGroup(
                    group_role="dsur_scopes",
                    scope_aliases=comparison_group,
                ),
            ),
        )
        for focus_alias in focus_scope_aliases
    )


def _plan_dsur_to_ib_jobs(
    *,
    dsur_scope_aliases: Sequence[str],
    ib_scope_aliases: Sequence[str],
) -> tuple[ComparisonFindingAssessmentJob, ...]:
    if not dsur_scope_aliases or not ib_scope_aliases:
        return ()
    return (
        ComparisonFindingAssessmentJob(
            comparison_mode_id="dsur_to_ib",
            groups=(
                ComparisonFindingAssessmentGroup(
                    group_role="dsur_scopes",
                    scope_aliases=tuple(dsur_scope_aliases),
                ),
                ComparisonFindingAssessmentGroup(
                    group_role="ib_scopes",
                    scope_aliases=tuple(ib_scope_aliases),
                ),
            ),
        ),
    )


def _plan_comparison_mode_jobs(
    *,
    comparison_mode_id: ComparisonModeId,
    config: ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
    participants_by_role: Mapping[str, Mapping[str, Any]],
) -> tuple[ComparisonFindingAssessmentJob, ...]:
    if comparison_mode_id in ("scope_local", "focus_comparison"):
        single_role_id = config.participant_role_ids[0]
        participant = _require_participant(
            participants_by_role=participants_by_role,
            role_id=single_role_id,
        )
        scope_aliases = _scope_aliases_for_participant(
            participant,
            role_id=single_role_id,
        )
        if comparison_mode_id == "scope_local":
            return _plan_scope_local_jobs(scope_aliases=scope_aliases)
        return _plan_focus_comparison_jobs(scope_aliases=scope_aliases)

    if comparison_mode_id == "ib_to_dsur":
        if config.ib_to_dsur is None:
            raise ValueError(
                "ib_to_dsur comparison mode requires ib_to_dsur configuration"
            )
        focus_participant = _require_participant(
            participants_by_role=participants_by_role,
            role_id=config.ib_to_dsur.focus_role_id,
        )
        comparison_participant = _require_participant(
            participants_by_role=participants_by_role,
            role_id=config.ib_to_dsur.comparison_role_id,
        )
        return _plan_ib_to_dsur_jobs(
            focus_scope_aliases=_scope_aliases_for_participant(
                focus_participant,
                role_id=config.ib_to_dsur.focus_role_id,
            ),
            comparison_scope_aliases=_scope_aliases_for_participant(
                comparison_participant,
                role_id=config.ib_to_dsur.comparison_role_id,
            ),
        )

    if comparison_mode_id == "dsur_to_ib":
        if config.dsur_to_ib is None:
            raise ValueError(
                "dsur_to_ib comparison mode requires dsur_to_ib configuration"
            )
        dsur_participant = _require_participant(
            participants_by_role=participants_by_role,
            role_id=config.dsur_to_ib.dsur_role_id,
        )
        ib_participant = _require_participant(
            participants_by_role=participants_by_role,
            role_id=config.dsur_to_ib.ib_role_id,
        )
        dsur_scopes = dsur_participant.get("scopes")
        ib_scopes = ib_participant.get("scopes")
        if not isinstance(dsur_scopes, list):
            raise TypeError(
                f"participant {config.dsur_to_ib.dsur_role_id!r} scopes must be a list"
            )
        if not isinstance(ib_scopes, list):
            raise TypeError(
                f"participant {config.dsur_to_ib.ib_role_id!r} scopes must be a list"
            )
        return _plan_dsur_to_ib_jobs(
            dsur_scope_aliases=select_scope_aliases_by_heading_profile(
                scopes=dsur_scopes,
                profile=config.dsur_to_ib.dsur_scope_selection,
            ),
            ib_scope_aliases=select_scope_aliases_by_heading_profile(
                scopes=ib_scopes,
                profile=config.dsur_to_ib.ib_scope_selection,
            ),
        )

    raise ValueError(f"unsupported comparison mode id: {comparison_mode_id!r}")


def plan_comparison_finding_assessment_jobs(
    *,
    aggregate_comparison_evidence: Mapping[str, Any],
    config: ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
) -> tuple[ComparisonFindingAssessmentJob, ...]:
    """Plan Finding Assessment jobs from formal evidence and resolved configuration."""

    if not isinstance(
        config,
        ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
    ):
        raise TypeError(
            "config must be a ResolvedClinicalSafetyComparisonFindingAssessmentConfig"
        )

    validate_aggregate_comparison_evidence(aggregate_comparison_evidence)
    participants_by_role = _participant_lookup(aggregate_comparison_evidence)

    for role_id in config.participant_role_ids:
        _require_participant(
            participants_by_role=participants_by_role,
            role_id=role_id,
        )

    planned: list[ComparisonFindingAssessmentJob] = []
    for comparison_mode_id in config.enabled_comparison_modes:
        planned.extend(
            _plan_comparison_mode_jobs(
                comparison_mode_id=comparison_mode_id,
                config=config,
                participants_by_role=participants_by_role,
            )
        )
    return tuple(planned)


__all__ = ["plan_comparison_finding_assessment_jobs"]
