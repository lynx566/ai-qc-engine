"""Aggregate-neutral selection of job-final rows by comparison mode."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def select_job_final_rows_for_mode(
    *,
    job_final_rows: Sequence[Mapping[str, Any]],
    comparison_mode_id: str,
) -> tuple[Mapping[str, Any], ...]:
    """Select one mode's rows without changing aggregate row order."""

    if not isinstance(job_final_rows, Sequence) or isinstance(
        job_final_rows, (str, bytes)
    ):
        raise TypeError("job_final_rows must be a sequence")
    if not isinstance(comparison_mode_id, str) or not comparison_mode_id.strip():
        raise ValueError("comparison_mode_id must be a non-empty string")
    selected: list[Mapping[str, Any]] = []
    for index, row in enumerate(job_final_rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"job_final_rows[{index}] must be an object")
        if row.get("comparison_mode_id") == comparison_mode_id:
            selected.append(row)
    return tuple(selected)


__all__ = ["select_job_final_rows_for_mode"]
