"""Neutral route-stage vocabulary shared by plugin processors and artifact builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Route = Literal["aggregate", "table", "case", "unknown"]

ROUTES: tuple[Route, ...] = ("aggregate", "table", "case", "unknown")


@dataclass(frozen=True)
class RoutedUnitSet:
    """Routed units grouped by route before route-stage artifact persistence."""

    units_by_route: dict[Route, list[dict[str, Any]]]
    route_counts: dict[str, int]
    all_units: tuple[dict[str, Any], ...]
