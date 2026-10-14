"""Installed heading-selection profiles for Comparison Finding Assessment."""

from __future__ import annotations

from .config import HeadingSelectionProfile

DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE = HeadingSelectionProfile(
    include_terms=(
        "安全性参考信息",
        "重要风险",
    ),
    match_mode="contains",
)

DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE = HeadingSelectionProfile(
    include_terms=(
        "研究者指南",
        "安全性参考信息",
    ),
    match_mode="contains",
)

__all__ = [
    "DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE",
    "DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE",
]
