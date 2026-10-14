"""Neutral Filter-output projection job indexing and resolution."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from operations.filter_output_projection.contracts import (
    ResolvedFilterOutputProjectionJob,
)


def build_filter_output_projection_job_index(
    jobs: Iterable[ResolvedFilterOutputProjectionJob],
) -> MappingProxyType[str, ResolvedFilterOutputProjectionJob]:
    """Derive an immutable filter_job_id → resolved projection job index."""

    index: dict[str, ResolvedFilterOutputProjectionJob] = {}
    for job in jobs:
        if job.filter_job_id in index:
            existing = index[job.filter_job_id]
            raise ValueError(
                "duplicate installed Filter-output projection job for "
                f"filter_job_id={job.filter_job_id!r}: "
                f"strategy_id={existing.strategy_id!r} and "
                f"strategy_id={job.strategy_id!r}"
            )
        index[job.filter_job_id] = job
    return MappingProxyType(index)


def resolve_filter_output_projection_job(
    *,
    filter_job_id: str,
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
) -> ResolvedFilterOutputProjectionJob:
    """Resolve one installed Filter-output projection job by filter_job_id."""

    if not isinstance(filter_job_id, str) or not filter_job_id.strip():
        raise ValueError("filter_job_id must be a non-empty string")

    resolved = filter_output_projection_jobs.get(filter_job_id)
    if resolved is not None:
        return resolved

    known_ids = sorted(filter_output_projection_jobs)
    if not known_ids:
        raise ValueError("no installed Filter-output projection jobs")
    raise ValueError(f"unknown Filter-output projection job: {filter_job_id!r}")


__all__ = [
    "build_filter_output_projection_job_index",
    "resolve_filter_output_projection_job",
]
