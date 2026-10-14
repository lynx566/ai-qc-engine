from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.filtering.strategies import FilterStrategy


@dataclass(frozen=True)
class ResolvedFilterJob:
    config: Any
    strategy: FilterStrategy
