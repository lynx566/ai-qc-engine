"""Materialize clinical-safety Finding Assessment jobs into LLM evidence bodies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_aggregate_comparison_evidence,
)

from .jobs import (
    ComparisonFindingAssessmentGroupRole,
    ComparisonFindingAssessmentJob,
)

_GROUP_ROLE_HEADINGS: Mapping[ComparisonFindingAssessmentGroupRole, str] = {
    "scope": "Scope",
    "focus_scope": "Focus Scope",
    "comparison_scopes": "Comparison Scopes",
    "ib_scope": "IB Scope",
    "dsur_scopes": "DSUR Scopes",
    "ib_scopes": "IB Scopes",
}
_SCOPE_LOCAL_COMPARISON_MODE_ID = "scope_local"


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


def _render_group_heading(
    *,
    group_role: ComparisonFindingAssessmentGroupRole,
    comparison_mode_id: str,
) -> str | None:
    if (
        comparison_mode_id == _SCOPE_LOCAL_COMPARISON_MODE_ID
        and group_role == "scope"
    ):
        return None
    return f"## {_GROUP_ROLE_HEADINGS[group_role]}"


def _render_scope(scope: Mapping[str, Any]) -> str:
    heading_text = " / ".join(scope["heading_path"])
    rendered_units: list[str] = []
    for unit in scope["units"]:
        rendered_sentences = [
            f"- {sentence['text']} [{sentence['sentence_alias']}]"
            for sentence in unit["sentences"]
        ]
        rendered_units.append(
            "\n".join((f"Unit {unit['unit_alias']}", *rendered_sentences))
        )
    return "\n".join((f"Scope: {heading_text}", *rendered_units))


def _render_job(
    *,
    job: ComparisonFindingAssessmentJob,
    scope_by_alias: Mapping[str, Mapping[str, Any]],
) -> str:
    if not isinstance(job, ComparisonFindingAssessmentJob):
        raise TypeError("job must be a ComparisonFindingAssessmentJob")

    rendered_groups: list[str] = []
    for group in job.groups:
        seen_aliases: set[str] = set()
        rendered_scopes: list[str] = []
        for scope_alias in group.scope_aliases:
            if scope_alias in seen_aliases:
                raise ValueError(
                    f"duplicate scope_alias {scope_alias!r} in group "
                    f"{group.group_role!r}"
                )
            seen_aliases.add(scope_alias)
            scope = scope_by_alias.get(scope_alias)
            if scope is None:
                raise ValueError(f"unknown scope_alias {scope_alias!r}")
            rendered_scopes.append(_render_scope(scope))
        rendered_scopes_block = "\n\n".join(rendered_scopes)
        group_heading = _render_group_heading(
            group_role=group.group_role,
            comparison_mode_id=job.comparison_mode_id,
        )
        if group_heading is None:
            rendered_groups.append(rendered_scopes_block)
        else:
            rendered_groups.append(f"{group_heading}\n{rendered_scopes_block}")
    return "\n\n".join(rendered_groups)


def materialize_comparison_finding_assessment_llm_input(
    *,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
) -> str:
    """Validate evidence and render one planned Finding Assessment job."""

    validate_aggregate_comparison_evidence(aggregate_comparison_evidence)
    return _render_job(
        job=job,
        scope_by_alias=_build_scope_index(aggregate_comparison_evidence),
    )


def materialize_comparison_finding_assessment_llm_inputs(
    *,
    jobs: Sequence[ComparisonFindingAssessmentJob],
    aggregate_comparison_evidence: Mapping[str, Any],
) -> tuple[str, ...]:
    """Validate/index evidence once and render an ordered job collection."""

    validate_aggregate_comparison_evidence(aggregate_comparison_evidence)
    scope_by_alias = _build_scope_index(aggregate_comparison_evidence)
    return tuple(_render_job(job=job, scope_by_alias=scope_by_alias) for job in jobs)


__all__ = [
    "materialize_comparison_finding_assessment_llm_input",
    "materialize_comparison_finding_assessment_llm_inputs",
]
