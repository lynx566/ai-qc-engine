"""Filter strategy framework (protocol, default heading_zone, block universe)."""

from core.filtering.block_universe import BlockUniverse
from core.filtering.heading_zone import HEADING_ZONE_STRATEGY, HeadingZoneStrategy
from core.filtering.registry import (
    DEFAULT_FILTER_STRATEGY_ID,
    resolve_filter_strategy,
    resolve_filter_strategy_for_config,
    strategy_id_from_zone_config,
)
from core.filtering.strategies import (
    FilterContext,
    FilterStrategy,
    FilterStrategyResult,
)

__all__ = [
    "BlockUniverse",
    "DEFAULT_FILTER_STRATEGY_ID",
    "FilterContext",
    "FilterStrategy",
    "FilterStrategyResult",
    "HEADING_ZONE_STRATEGY",
    "HeadingZoneStrategy",
    "resolve_filter_strategy",
    "resolve_filter_strategy_for_config",
    "strategy_id_from_zone_config",
]
