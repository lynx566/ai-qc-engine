"""Pair findings job envelopes with frozen Assessment jobs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..comparison_finding_assessment.jobs import ComparisonFindingAssessmentJob


def serialize_comparison_groups_for_provenance(
    job: ComparisonFindingAssessmentJob,
) -> list[dict[str, Any]]:
    """Serialize one frozen Assessment job into findings-style comparison groups."""

    return [
        {
            "group_role": group.group_role,
            "scope_aliases": list(group.scope_aliases),
        }
        for group in job.groups
    ]


def resolve_frozen_assessment_job(
    *,
    frozen_jobs: Sequence[ComparisonFindingAssessmentJob],
    frozen_job_index: int,
) -> ComparisonFindingAssessmentJob:
    """Resolve one canonical frozen Assessment job by 1-based index."""

    if frozen_job_index < 1 or frozen_job_index > len(frozen_jobs):
        raise ValueError(
            f"frozen_job_index must be between 1 and {len(frozen_jobs)}, "
            f"got {frozen_job_index}"
        )
    return frozen_jobs[frozen_job_index - 1]


def verify_findings_job_matches_frozen_job(
    findings_job: Mapping[str, Any],
    *,
    frozen_job: ComparisonFindingAssessmentJob,
    frozen_job_index: int,
) -> None:
    """Fail when a findings envelope does not match the canonical frozen Assessment job."""

    envelope_index = findings_job.get("frozen_job_index")
    if envelope_index != frozen_job_index:
        raise ValueError(
            "findings job frozen_job_index does not match requested frozen job index"
        )
    comparison_mode_id = findings_job.get("comparison_mode_id")
    if comparison_mode_id != frozen_job.comparison_mode_id:
        raise ValueError(
            "findings job comparison_mode_id does not match frozen assessment job"
        )
    comparison_groups = findings_job.get("comparison_groups")
    expected_groups = serialize_comparison_groups_for_provenance(frozen_job)
    if comparison_groups != expected_groups:
        raise ValueError(
            "findings job comparison_groups do not match frozen assessment job"
        )


__all__ = [
    "resolve_frozen_assessment_job",
    "serialize_comparison_groups_for_provenance",
    "verify_findings_job_matches_frozen_job",
]
