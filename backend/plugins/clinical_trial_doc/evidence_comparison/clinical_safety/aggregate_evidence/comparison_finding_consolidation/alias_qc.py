"""Non-failing sentence-alias quality checks for consolidation groups."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .input_materialization import (
    ComparisonFindingConsolidationFindingProjection,
)
from .response_validation import (
    ComparisonFindingConsolidationValidatedResponse,
)


def _stable_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _duplicates(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationGroupAliasQcResult:
    group_index: int
    conclusion_aliases: tuple[str, ...]
    expected_sentence_aliases: tuple[str, ...]
    reported_sentence_aliases: tuple[str, ...]
    missing_sentence_aliases: tuple[str, ...]
    unexpected_sentence_aliases: tuple[str, ...]
    duplicate_reported_sentence_aliases: tuple[str, ...]
    combined_aliases_match: bool


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationAliasQcResult:
    groups: tuple[ComparisonFindingConsolidationGroupAliasQcResult, ...]

    @property
    def mismatch_count(self) -> int:
        return sum(not group.combined_aliases_match for group in self.groups)

    @property
    def all_groups_match(self) -> bool:
        return self.mismatch_count == 0


def compute_comparison_finding_consolidation_alias_qc(
    *,
    finding_projections: Sequence[
        ComparisonFindingConsolidationFindingProjection
    ],
    validated_response: ComparisonFindingConsolidationValidatedResponse,
) -> ComparisonFindingConsolidationAliasQcResult:
    """Compare reported T aliases with backend-derived member unions."""

    projection_by_alias = {
        projection.conclusion_alias: projection
        for projection in finding_projections
    }
    group_results: list[ComparisonFindingConsolidationGroupAliasQcResult] = []
    for group_index, group in enumerate(
        validated_response.consolidated_groups,
        start=1,
    ):
        expected = _stable_unique(
            tuple(
                sentence_alias
                for conclusion_alias in group.conclusion_aliases
                for sentence_alias in projection_by_alias[
                    conclusion_alias
                ].source_sentence_aliases
            )
        )
        reported = group.combined_sentence_aliases
        expected_set = frozenset(expected)
        reported_set = frozenset(reported)
        missing = tuple(alias for alias in expected if alias not in reported_set)
        unexpected = _stable_unique(
            tuple(alias for alias in reported if alias not in expected_set)
        )
        duplicates = _duplicates(reported)
        group_results.append(
            ComparisonFindingConsolidationGroupAliasQcResult(
                group_index=group_index,
                conclusion_aliases=group.conclusion_aliases,
                expected_sentence_aliases=expected,
                reported_sentence_aliases=reported,
                missing_sentence_aliases=missing,
                unexpected_sentence_aliases=unexpected,
                duplicate_reported_sentence_aliases=duplicates,
                combined_aliases_match=(reported == expected),
            )
        )
    return ComparisonFindingConsolidationAliasQcResult(groups=tuple(group_results))


def serialize_alias_qc(
    result: ComparisonFindingConsolidationAliasQcResult,
) -> dict[str, Any]:
    return {
        "all_groups_match": result.all_groups_match,
        "mismatch_count": result.mismatch_count,
        "groups": [
            {
                "group_index": group.group_index,
                "conclusion_aliases": list(group.conclusion_aliases),
                "expected": list(group.expected_sentence_aliases),
                "reported": list(group.reported_sentence_aliases),
                "missing": list(group.missing_sentence_aliases),
                "unexpected": list(group.unexpected_sentence_aliases),
                "duplicates": list(group.duplicate_reported_sentence_aliases),
                "combined_aliases_match": group.combined_aliases_match,
            }
            for group in result.groups
        ],
    }


__all__ = [
    "ComparisonFindingConsolidationAliasQcResult",
    "ComparisonFindingConsolidationGroupAliasQcResult",
    "compute_comparison_finding_consolidation_alias_qc",
    "serialize_alias_qc",
]
