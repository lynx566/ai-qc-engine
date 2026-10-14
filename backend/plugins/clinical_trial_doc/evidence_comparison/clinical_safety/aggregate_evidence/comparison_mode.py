"""Comparison mode identity for clinical-safety aggregate Evidence Comparison."""

from __future__ import annotations

from typing import Literal

ComparisonModeId = Literal[
    "scope_local",
    "focus_comparison",
    "ib_to_dsur",
    "dsur_to_ib",
]

__all__ = ["ComparisonModeId"]
