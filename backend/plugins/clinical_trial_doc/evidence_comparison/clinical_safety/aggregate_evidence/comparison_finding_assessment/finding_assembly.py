"""Deterministic Finding assembly from validated Assessment candidates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .jobs import ComparisonFindingAssessmentGroup, ComparisonFindingAssessmentJob
from .response_validation import (
    ComparisonFindingAssessmentCandidate,
    ComparisonFindingAssessmentValidatedResponse,
)


@dataclass(frozen=True, slots=True)
class AssembledFinding:
    """One formal Finding from a validated Assessment candidate."""

    finding_id: str
    conclusion: str
    label: str
    source_sentence_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JobFindingsBundle:
    """One job's assembled findings with comparison-mode provenance."""

    frozen_job_index: int
    job: ComparisonFindingAssessmentJob
    findings: tuple[AssembledFinding, ...]


def format_finding_id(sequence_number: int) -> str:
    """Format one deterministic finding id (L001, L002, ...)."""

    if sequence_number < 1:
        raise ValueError("sequence_number must be at least 1")
    return f"L{sequence_number:03d}"


def _serialize_comparison_groups(
    groups: Sequence[ComparisonFindingAssessmentGroup],
) -> list[dict[str, Any]]:
    return [
        {
            "group_role": group.group_role,
            "scope_aliases": list(group.scope_aliases),
        }
        for group in groups
    ]


def _candidate_to_finding(
    candidate: ComparisonFindingAssessmentCandidate,
    *,
    finding_id: str,
) -> AssembledFinding:
    return AssembledFinding(
        finding_id=finding_id,
        conclusion=candidate.candidate_focus,
        label=candidate.label,
        source_sentence_aliases=candidate.trigger_sentence_aliases,
    )


def assemble_findings_for_job(
    validated_response: ComparisonFindingAssessmentValidatedResponse,
    *,
    job: ComparisonFindingAssessmentJob,
    starting_finding_sequence: int = 1,
) -> tuple[AssembledFinding, ...]:
    """Assemble findings for one job using consecutive finding ids."""

    if starting_finding_sequence < 1:
        raise ValueError("starting_finding_sequence must be at least 1")
    assembled: list[AssembledFinding] = []
    sequence = starting_finding_sequence
    for candidate in validated_response.candidates:
        assembled.append(
            _candidate_to_finding(
                candidate,
                finding_id=format_finding_id(sequence),
            )
        )
        sequence += 1
    return tuple(assembled)


def assemble_findings_for_jobs(
    job_results: Sequence[tuple[int, ComparisonFindingAssessmentJob, ComparisonFindingAssessmentValidatedResponse]],
) -> tuple[JobFindingsBundle, ...]:
    """Assemble findings for multiple jobs in frozen-job order with artifact-wide ids."""

    ordered = sorted(job_results, key=lambda row: row[0])
    bundles: list[JobFindingsBundle] = []
    sequence = 1
    for frozen_job_index, job, validated in ordered:
        findings: list[AssembledFinding] = []
        for candidate in validated.candidates:
            findings.append(
                _candidate_to_finding(
                    candidate,
                    finding_id=format_finding_id(sequence),
                )
            )
            sequence += 1
        bundles.append(
            JobFindingsBundle(
                frozen_job_index=frozen_job_index,
                job=job,
                findings=tuple(findings),
            )
        )
    return tuple(bundles)


def job_findings_bundle_to_artifact_row(
    bundle: JobFindingsBundle,
) -> dict[str, Any]:
    """Serialize one job bundle into a findings artifact job entry."""

    return {
        "frozen_job_index": bundle.frozen_job_index,
        "comparison_mode_id": bundle.job.comparison_mode_id,
        "comparison_groups": _serialize_comparison_groups(bundle.job.groups),
        "findings": [
            {
                "finding_id": finding.finding_id,
                "conclusion": finding.conclusion,
                "label": finding.label,
                "source_sentence_aliases": list(finding.source_sentence_aliases),
            }
            for finding in bundle.findings
        ],
    }


def build_findings_artifact_from_bundles(
    bundles: Sequence[JobFindingsBundle],
) -> dict[str, Any]:
    """Build a validated findings artifact envelope from assembled job bundles."""

    from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
        build_findings,
    )

    if not bundles:
        raise ValueError("bundles must be non-empty")
    return build_findings(
        jobs=[job_findings_bundle_to_artifact_row(bundle) for bundle in bundles],
    )


__all__ = [
    "AssembledFinding",
    "JobFindingsBundle",
    "assemble_findings_for_job",
    "assemble_findings_for_jobs",
    "build_findings_artifact_from_bundles",
    "format_finding_id",
    "job_findings_bundle_to_artifact_row",
]
