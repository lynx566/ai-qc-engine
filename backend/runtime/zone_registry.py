"""Mechanical helpers for filter-stage run layout."""

from __future__ import annotations

from typing import Any

from runtime.run_layout import sanitize_run_segment


def filter_job_dir_context(*, zone_key: str, profile: Any) -> str:
    """Per-profile directory segment under ``runs/filter/<timestamp>/<context>/``."""
    if ":" in zone_key:
        return sanitize_run_segment(profile.zone_config_name).lower()
    return sanitize_run_segment(zone_key).lower()
