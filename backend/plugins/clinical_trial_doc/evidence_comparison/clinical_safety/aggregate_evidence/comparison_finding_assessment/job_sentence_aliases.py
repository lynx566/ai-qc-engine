"""Structured sentence-alias ownership for Comparison Finding Assessment jobs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_aggregate_comparison_evidence,
)

from .jobs import ComparisonFindingAssessmentGroupRole, ComparisonFindingAssessmentJob


def _build_scope_index(
    aggregate_comparison_evidence: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    scope_by_alias: dict[str, Mapping[str, Any]] = {}
    participants = aggregate_comparison_evidence["participants"]
    for participant in participants:
        for scope in participant["scopes"]:
            scope_alias = scope["scope_alias"]
            if scope_alias in scope_by_alias:
                raise ValueError(f"duplicate scope_alias {scope_alias!r}")
            scope_by_alias[scope_alias] = scope
    return scope_by_alias


def _sentence_aliases_for_scope_aliases(
    scope_aliases: Sequence[str],
    *,
    scope_by_alias: Mapping[str, Mapping[str, Any]],
) -> frozenset[str]:
    allowed_aliases: set[str] = set()
    for scope_alias in scope_aliases:
        scope = scope_by_alias.get(scope_alias)
        if scope is None:
            raise ValueError(f"unknown scope_alias {scope_alias!r}")
        for unit in scope["units"]:
            for sentence in unit["sentences"]:
                allowed_aliases.add(str(sentence["sentence_alias"]))
    return frozenset(allowed_aliases)


def collect_job_group_sentence_aliases(
    *,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
) -> Mapping[ComparisonFindingAssessmentGroupRole, frozenset[str]]:
    """Return sentence aliases grouped by each job group's semantic role."""

    validate_aggregate_comparison_evidence(aggregate_comparison_evidence)
    scope_by_alias = _build_scope_index(aggregate_comparison_evidence)
    grouped: dict[ComparisonFindingAssessmentGroupRole, set[str]] = {}
    for group in job.groups:
        group_aliases = _sentence_aliases_for_scope_aliases(
            group.scope_aliases,
            scope_by_alias=scope_by_alias,
        )
        bucket = grouped.setdefault(group.group_role, set())
        bucket.update(group_aliases)
    return {role: frozenset(aliases) for role, aliases in grouped.items()}


def collect_job_allowed_sentence_aliases(
    *,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
) -> frozenset[str]:
    """Return T aliases structurally owned by one planned Finding Assessment job."""

    group_aliases = collect_job_group_sentence_aliases(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    allowed_aliases: set[str] = set()
    for aliases in group_aliases.values():
        allowed_aliases.update(aliases)
    return frozenset(allowed_aliases)


__all__ = [
    "collect_job_allowed_sentence_aliases",
    "collect_job_group_sentence_aliases",
]
