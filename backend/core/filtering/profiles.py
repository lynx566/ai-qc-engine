from __future__ import annotations

from typing import Any


def normalize_filter_profiles(
    zone_config: Any | tuple[Any, ...] | list[Any],
) -> tuple[Any, ...]:
    if isinstance(zone_config, (list, tuple)):
        if not zone_config:
            raise ValueError("zone_config must contain at least one profile")
        return tuple(zone_config)
    return (zone_config,)
