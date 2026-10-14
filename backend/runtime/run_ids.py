"""Stable pipeline run_id and session directory segment helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

PipelineStage = Literal["extract", "mask", "filter", "tag"]

# Canonical writes: ``20260705_102233_184512Z``; legacy reads may omit ``Z`` or microseconds.
RUN_TIMESTAMP_PATTERN = re.compile(r"^\d{8}_\d{6}(?:_\d{6})?Z?$")


def utc_run_stamp() -> datetime:
    """Return the UTC-aware timestamp used for run folder names and run IDs."""
    return datetime.now(timezone.utc)


def format_run_timestamp(stamp: datetime) -> str:
    """Format a UTC-aware timestamp for session folders and run ID bases.

    Output format: ``YYYYMMDD_HHMMSS_microsecondsZ`` (e.g. ``20260705_102233_184512Z``).
    """
    if stamp.tzinfo is None:
        raise ValueError("run timestamp must be timezone-aware")
    stamp_utc = stamp.astimezone(timezone.utc)
    return stamp_utc.strftime("%Y%m%d_%H%M%S_%fZ")


def build_session_dir_segment(stamp: datetime) -> str:
    """
    Session folder base name (timestamp only).

    Git commit is recorded in ``run_summary.json`` as a ``base_commit_hint``,
    not embedded in directory names.

    Example: ``20260705_102233_184512Z``.
    """
    return format_run_timestamp(stamp)


def build_run_id(
    stage: PipelineStage | str,
    stamp: datetime,
) -> str:
    """
    Legacy run_id from timestamp only.

    Prefer :func:`build_run_id_from_session_dir` when the final unique session
    directory name is already known.
    """
    return f"{stage}_{format_run_timestamp(stamp)}"


def build_run_id_from_session_dir(
    stage: PipelineStage | str,
    session_dir_name: str,
) -> str:
    """Build run_id from the allocated session folder name (includes ``__n`` suffix)."""
    return f"{stage}_{session_dir_name}"
