"""In-memory job contract for clinical-safety Comparison Finding Assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..comparison_mode import ComparisonModeId

ComparisonFindingAssessmentGroupRole = Literal[
    "scope",
    "focus_scope",
    "comparison_scopes",
    "ib_scope",
    "dsur_scopes",
    "ib_scopes",
]


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentGroup:
    """One semantic scope group within a Finding Assessment job."""

    group_role: ComparisonFindingAssessmentGroupRole
    scope_aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.group_role not in (
            "scope",
            "focus_scope",
            "comparison_scopes",
            "ib_scope",
            "dsur_scopes",
            "ib_scopes",
        ):
            raise ValueError(f"unknown group_role: {self.group_role!r}")
        if not self.scope_aliases:
            raise ValueError("scope_aliases must be a non-empty tuple")
        for index, alias in enumerate(self.scope_aliases):
            if not isinstance(alias, str) or not alias.strip():
                raise ValueError(f"scope_aliases[{index}] must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentJob:
    """One planned Comparison Finding Assessment job."""

    comparison_mode_id: ComparisonModeId
    groups: tuple[ComparisonFindingAssessmentGroup, ...]

    def __post_init__(self) -> None:
        if not self.groups:
            raise ValueError("groups must be a non-empty tuple")
        for index, group in enumerate(self.groups):
            if not isinstance(group, ComparisonFindingAssessmentGroup):
                raise TypeError(
                    f"groups[{index}] must be a ComparisonFindingAssessmentGroup"
                )


__all__ = [
    "ComparisonFindingAssessmentGroup",
    "ComparisonFindingAssessmentGroupRole",
    "ComparisonFindingAssessmentJob",
]
