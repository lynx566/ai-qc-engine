"""Semantic configuration for generic Comparison Finding Consolidation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from ..comparison_mode import ComparisonModeId

_ALL_COMPARISON_MODE_IDS = frozenset(get_args(ComparisonModeId))


def _validate_enabled_comparison_modes(modes: tuple[str, ...]) -> None:
    if not isinstance(modes, tuple):
        raise TypeError("enabled_comparison_modes must be a tuple")
    seen: set[str] = set()
    for index, mode_id in enumerate(modes):
        if not isinstance(mode_id, str) or not mode_id.strip():
            raise ValueError(
                f"enabled_comparison_modes[{index}] must be a non-empty string"
            )
        if mode_id not in _ALL_COMPARISON_MODE_IDS:
            raise ValueError(f"unknown comparison mode id: {mode_id!r}")
        if mode_id in seen:
            raise ValueError(f"duplicate comparison mode id: {mode_id!r}")
        seen.add(mode_id)


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationCapabilityDeclaration:
    """Application-declared consolidation activation for one capability."""

    enabled_comparison_modes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_enabled_comparison_modes(self.enabled_comparison_modes)


@dataclass(frozen=True, slots=True)
class ResolvedComparisonFindingConsolidationConfig:
    """Frozen consolidation activation for one aggregate execution."""

    enabled_comparison_modes: tuple[ComparisonModeId, ...]

    def __post_init__(self) -> None:
        _validate_enabled_comparison_modes(self.enabled_comparison_modes)


__all__ = [
    "ComparisonFindingConsolidationCapabilityDeclaration",
    "ResolvedComparisonFindingConsolidationConfig",
]
