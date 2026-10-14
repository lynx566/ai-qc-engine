"""Deterministic Verification user input materialization from Assessment results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..comparison_finding_assessment import (
    ComparisonFindingAssessmentJob,
    materialize_comparison_finding_assessment_llm_input,
)
from .findings_rendering import render_verification_findings_section
from .job_pairing import (
    resolve_frozen_assessment_job,
    verify_findings_job_matches_frozen_job,
)

VERIFICATION_SOURCE_SCOPE_HEADING = "## Source Scope"
VERIFICATION_FINDINGS_HEADING = "## Findings"


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationInput:
    """One Verification user input derived from a successful Assessment job."""

    frozen_job_index: int
    comparison_mode_id: str
    comparison_groups: tuple[dict[str, Any], ...]
    source_scope_text: str
    findings: tuple[dict[str, Any], ...]
    user_input_text: str


def _comparison_groups_from_envelope(
    findings_job: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    comparison_groups = findings_job.get("comparison_groups")
    if not isinstance(comparison_groups, list):
        raise TypeError("findings job comparison_groups must be a list")
    return tuple(dict(group) for group in comparison_groups)


def _findings_from_envelope(
    findings_job: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    findings = findings_job.get("findings")
    if not isinstance(findings, list):
        raise TypeError("findings job findings must be a list")
    return tuple(dict(finding) for finding in findings)


def assemble_verification_user_input_text(
    *,
    source_scope_text: str,
    findings: Sequence[Mapping[str, Any]],
) -> str:
    """Assemble the full Verification user input with deterministic section spacing."""

    findings_section = render_verification_findings_section(findings)
    return (
        f"{VERIFICATION_SOURCE_SCOPE_HEADING}\n"
        f"{source_scope_text}\n\n"
        f"{VERIFICATION_FINDINGS_HEADING}\n"
        f"{findings_section}"
    )


def materialize_comparison_finding_verification_input(
    *,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
    findings_job_envelope: Mapping[str, Any],
    frozen_job_index: int,
) -> ComparisonFindingVerificationInput:
    """Materialize one Verification user input from a paired Assessment job envelope."""

    verify_findings_job_matches_frozen_job(
        findings_job_envelope,
        frozen_job=job,
        frozen_job_index=frozen_job_index,
    )
    source_scope_text = materialize_comparison_finding_assessment_llm_input(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    findings = _findings_from_envelope(findings_job_envelope)
    comparison_groups = _comparison_groups_from_envelope(findings_job_envelope)
    user_input_text = assemble_verification_user_input_text(
        source_scope_text=source_scope_text,
        findings=findings,
    )
    return ComparisonFindingVerificationInput(
        frozen_job_index=frozen_job_index,
        comparison_mode_id=job.comparison_mode_id,
        comparison_groups=comparison_groups,
        source_scope_text=source_scope_text,
        findings=findings,
        user_input_text=user_input_text,
    )


def materialize_comparison_finding_verification_inputs(
    *,
    planned_jobs: Sequence[ComparisonFindingAssessmentJob],
    aggregate_comparison_evidence: Mapping[str, Any],
    assessment_findings_artifact: Mapping[str, Any],
    successful_frozen_job_indexes: frozenset[int],
) -> tuple[ComparisonFindingVerificationInput, ...]:
    """Materialize Verification inputs from in-memory Assessment execution results."""

    findings_jobs = assessment_findings_artifact["jobs"]
    if not isinstance(findings_jobs, list):
        raise TypeError("assessment findings artifact jobs must be a list")

    materialized: list[ComparisonFindingVerificationInput] = []
    for findings_job in findings_jobs:
        if not isinstance(findings_job, Mapping):
            raise TypeError("findings job envelope must be a mapping")
        frozen_job_index = findings_job["frozen_job_index"]
        if not isinstance(frozen_job_index, int) or frozen_job_index < 1:
            raise ValueError("findings job frozen_job_index must be a positive integer")
        if frozen_job_index not in successful_frozen_job_indexes:
            raise ValueError(
                "findings job references a frozen_job_index that is not a "
                "successful assessment job in this execution"
            )
        frozen_job = resolve_frozen_assessment_job(
            frozen_jobs=planned_jobs,
            frozen_job_index=frozen_job_index,
        )
        materialized.append(
            materialize_comparison_finding_verification_input(
                job=frozen_job,
                aggregate_comparison_evidence=aggregate_comparison_evidence,
                findings_job_envelope=findings_job,
                frozen_job_index=frozen_job_index,
            )
        )
    return tuple(materialized)


__all__ = [
    "VERIFICATION_FINDINGS_HEADING",
    "VERIFICATION_SOURCE_SCOPE_HEADING",
    "ComparisonFindingVerificationInput",
    "assemble_verification_user_input_text",
    "materialize_comparison_finding_verification_input",
    "materialize_comparison_finding_verification_inputs",
]
