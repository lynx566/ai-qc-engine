"""Filter strategy protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from core.filtering.block_universe import BlockUniverse


@dataclass(frozen=True)
class FilterContext:
    """Per-profile extraction context passed into a filter strategy."""

    zone_index_start: int = 1


@dataclass
class FilterStrategyResult:
    """Output of one strategy run for a single zone profile."""

    matched_zones: list[dict[str, Any]]
    selected_block_ids: frozenset[str]
    next_zone_index: int
    coverage_records: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class FilterStrategy(Protocol):
    """Pluggable filter extraction strategy."""

    strategy_id: str

    def extract(
        self,
        *,
        block_universe: BlockUniverse,
        zone_config: Any,
        context: FilterContext,
    ) -> FilterStrategyResult:
        """Extract matched zones from *block_universe* for *zone_config*."""
        ...
