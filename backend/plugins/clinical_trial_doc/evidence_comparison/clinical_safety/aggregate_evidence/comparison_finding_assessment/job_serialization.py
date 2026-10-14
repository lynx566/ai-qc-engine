"""Deterministic serialization for Comparison Finding Assessment plan artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .jobs import ComparisonFindingAssessmentJob

COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME = "comparison_finding_assessment_jobs.json"


def _serialize_job(job: ComparisonFindingAssessmentJob) -> dict[str, Any]:
    return {
        "comparison_mode_id": job.comparison_mode_id,
        "groups": [
            {
                "group_role": group.group_role,
                "scope_aliases": list(group.scope_aliases),
            }
            for group in job.groups
        ],
    }


def serialize_comparison_finding_assessment_jobs(
    *,
    capability_id: str,
    jobs: Sequence[ComparisonFindingAssessmentJob],
) -> dict[str, Any]:
    """Serialize planned Assessment jobs into the persisted jobs artifact envelope."""

    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("capability_id must be a non-empty string")
    return {
        "capability_id": capability_id.strip(),
        "jobs": [_serialize_job(job) for job in jobs],
    }


__all__ = [
    "COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME",
    "serialize_comparison_finding_assessment_jobs",
]
