"""Filter strategy registry and resolution."""

from __future__ import annotations

from typing import Any

from core.filtering.heading_zone import HEADING_ZONE_STRATEGY, HeadingZoneStrategy
from core.filtering.strategies import FilterStrategy

DEFAULT_FILTER_STRATEGY_ID = "heading_zone"

_STRATEGIES: dict[str, FilterStrategy] = {
    DEFAULT_FILTER_STRATEGY_ID: HEADING_ZONE_STRATEGY,
}


def strategy_id_from_zone_config(zone_config: Any) -> str:
    """Resolve strategy id from a zone profile; default ``heading_zone``."""
    strategy_id = getattr(zone_config, "strategy_id", DEFAULT_FILTER_STRATEGY_ID)
    if isinstance(strategy_id, str):
        stripped = strategy_id.strip()
        if stripped:
            return stripped
    return DEFAULT_FILTER_STRATEGY_ID


def resolve_filter_strategy(strategy_id: str | None) -> FilterStrategy:
    """Return a registered filter strategy instance."""
    resolved = strategy_id or DEFAULT_FILTER_STRATEGY_ID
    if resolved not in _STRATEGIES:
        known = ", ".join(sorted(_STRATEGIES))
        raise KeyError(
            f"Unknown filter strategy {resolved!r}; registered: {known}"
        )
    return _STRATEGIES[resolved]


def resolve_filter_strategy_for_config(zone_config: Any) -> FilterStrategy:
    """Resolve strategy from *zone_config* (profile may omit ``strategy_id``)."""
    return resolve_filter_strategy(strategy_id_from_zone_config(zone_config))


__all__ = [
    "DEFAULT_FILTER_STRATEGY_ID",
    "HeadingZoneStrategy",
    "resolve_filter_strategy",
    "resolve_filter_strategy_for_config",
    "strategy_id_from_zone_config",
]
