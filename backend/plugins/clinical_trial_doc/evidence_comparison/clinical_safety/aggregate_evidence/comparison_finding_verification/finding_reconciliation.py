"""Deterministic Finding reconciliation and final artifact assembly for Verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDING_ID_PATTERN,
    build_findings,
)

from ..comparison_finding_assessment.finding_assembly import format_finding_id
from ..comparison_finding_assessment.jobs import ComparisonFindingAssessmentJob
from .additional_finding_eligibility import AdditionalFindingEligibilityResult
from .job_pairing import serialize_comparison_groups_for_provenance
from .response_validation import (
    ComparisonFindingVerificationAdditionalFinding,
    ComparisonFindingVerificationConfirmedEntry,
    ComparisonFindingVerificationEntry,
    ComparisonFindingVerificationRejectedEntry,
    ComparisonFindingVerificationRevisedEntry,
    ComparisonFindingVerificationValidatedResponse,
)


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationJobReconciliationResult:
    frozen_job_index: int
    comparison_mode_id: str
    comparison_groups: tuple[dict[str, Any], ...]
    findings: tuple[dict[str, Any], ...]
    input_finding_count: int
    confirmed_finding_count: int
    revised_finding_count: int
    rejected_finding_count: int
    accepted_additional_finding_count: int


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationReconciliationResult:
    findings_artifact: dict[str, Any]
    job_results: tuple[ComparisonFindingVerificationJobReconciliationResult, ...]
    adopted_finding_count: int


def max_finding_sequence_number(findings_artifact: Mapping[str, Any]) -> int:
    """Return the highest numeric Finding ID sequence from one findings artifact."""

    max_sequence = 0
    for job in findings_artifact.get("jobs", ()):
        if not isinstance(job, Mapping):
            continue
        findings = job.get("findings")
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, Mapping):
                continue
            finding_id = finding.get("finding_id")
            if not isinstance(finding_id, str):
                continue
            if FINDING_ID_PATTERN.fullmatch(finding_id) is None:
                continue
            max_sequence = max(max_sequence, int(finding_id[1:]))
    return max_sequence


def _verification_entries_by_finding_id(
    validated_response: ComparisonFindingVerificationValidatedResponse,
) -> dict[str, ComparisonFindingVerificationEntry]:
    return {
        entry.finding_id: entry for entry in validated_response.finding_verifications
    }


def reconcile_existing_findings(
    original_findings: Sequence[Mapping[str, Any]],
    *,
    validated_response: ComparisonFindingVerificationValidatedResponse,
) -> tuple[tuple[dict[str, Any], ...], int, int, int]:
    """Reconcile original Assessment findings against validated Verification entries."""

    verified_by_id = _verification_entries_by_finding_id(validated_response)
    reconciled: list[dict[str, Any]] = []
    confirmed_count = 0
    revised_count = 0
    rejected_count = 0

    for original in original_findings:
        finding_id = str(original["finding_id"])
        entry = verified_by_id.get(finding_id)
        if entry is None:
            raise ValueError(
                f"missing verification entry for original finding_id: {finding_id!r}"
            )
        if isinstance(entry, ComparisonFindingVerificationConfirmedEntry):
            reconciled.append(
                {
                    "finding_id": finding_id,
                    "conclusion": original["conclusion"],
                    "label": original["label"],
                    "source_sentence_aliases": list(
                        original["source_sentence_aliases"],
                    ),
                }
            )
            confirmed_count += 1
            continue
        if isinstance(entry, ComparisonFindingVerificationRevisedEntry):
            reconciled.append(
                {
                    "finding_id": finding_id,
                    "conclusion": entry.conclusion,
                    "label": entry.label,
                    "source_sentence_aliases": list(entry.source_sentence_aliases),
                }
            )
            revised_count += 1
            continue
        if isinstance(entry, ComparisonFindingVerificationRejectedEntry):
            rejected_count += 1
            continue
        raise TypeError(f"unsupported verification entry type: {type(entry)!r}")

    return tuple(reconciled), confirmed_count, revised_count, rejected_count


def _additional_finding_to_row(
    additional_finding: ComparisonFindingVerificationAdditionalFinding,
    *,
    finding_id: str,
) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "conclusion": additional_finding.conclusion,
        "label": additional_finding.label,
        "source_sentence_aliases": list(additional_finding.source_sentence_aliases),
    }


def reconcile_verification_job(
    *,
    frozen_job_index: int,
    job: ComparisonFindingAssessmentJob,
    original_findings: Sequence[Mapping[str, Any]],
    validated_response: ComparisonFindingVerificationValidatedResponse,
    additional_eligibility: AdditionalFindingEligibilityResult,
) -> ComparisonFindingVerificationJobReconciliationResult:
    """Reconcile one Verification job without assigning global additional Finding IDs."""

    (
        reconciled_existing,
        confirmed_count,
        revised_count,
        rejected_count,
    ) = reconcile_existing_findings(
        original_findings,
        validated_response=validated_response,
    )
    return ComparisonFindingVerificationJobReconciliationResult(
        frozen_job_index=frozen_job_index,
        comparison_mode_id=job.comparison_mode_id,
        comparison_groups=tuple(serialize_comparison_groups_for_provenance(job)),
        findings=reconciled_existing,
        input_finding_count=len(original_findings),
        confirmed_finding_count=confirmed_count,
        revised_finding_count=revised_count,
        rejected_finding_count=rejected_count,
        accepted_additional_finding_count=(
            additional_eligibility.accepted_additional_finding_count
        ),
    )


def assemble_verified_findings_artifact(
    *,
    assessment_findings_artifact: Mapping[str, Any],
    job_reconciliations: Sequence[
        tuple[
            ComparisonFindingVerificationJobReconciliationResult,
            AdditionalFindingEligibilityResult,
        ]
    ],
) -> ComparisonFindingVerificationReconciliationResult:
    """Assign global additional Finding IDs and build the post-Verification artifact."""

    ordered = sorted(job_reconciliations, key=lambda row: row[0].frozen_job_index)
    next_sequence = max_finding_sequence_number(assessment_findings_artifact) + 1
    next_sequence = max(next_sequence, 1)

    assembled_jobs: list[ComparisonFindingVerificationJobReconciliationResult] = []
    artifact_job_rows: list[dict[str, Any]] = []
    adopted_finding_count = 0

    for job_reconciliation, additional_eligibility in ordered:
        job_findings = list(job_reconciliation.findings)
        for additional_finding in additional_eligibility.accepted_additional_findings:
            job_findings.append(
                _additional_finding_to_row(
                    additional_finding,
                    finding_id=format_finding_id(next_sequence),
                )
            )
            next_sequence += 1

        assembled_job = ComparisonFindingVerificationJobReconciliationResult(
            frozen_job_index=job_reconciliation.frozen_job_index,
            comparison_mode_id=job_reconciliation.comparison_mode_id,
            comparison_groups=job_reconciliation.comparison_groups,
            findings=tuple(job_findings),
            input_finding_count=job_reconciliation.input_finding_count,
            confirmed_finding_count=job_reconciliation.confirmed_finding_count,
            revised_finding_count=job_reconciliation.revised_finding_count,
            rejected_finding_count=job_reconciliation.rejected_finding_count,
            accepted_additional_finding_count=(
                job_reconciliation.accepted_additional_finding_count
            ),
        )
        assembled_jobs.append(assembled_job)
        adopted_finding_count += len(job_findings)
        artifact_job_rows.append(
            {
                "frozen_job_index": assembled_job.frozen_job_index,
                "comparison_mode_id": assembled_job.comparison_mode_id,
                "comparison_groups": [
                    dict(group) for group in assembled_job.comparison_groups
                ],
                "findings": list(assembled_job.findings),
            }
        )

    findings_artifact = build_findings(jobs=artifact_job_rows)
    return ComparisonFindingVerificationReconciliationResult(
        findings_artifact=findings_artifact,
        job_results=tuple(assembled_jobs),
        adopted_finding_count=adopted_finding_count,
    )


__all__ = [
    "ComparisonFindingVerificationJobReconciliationResult",
    "ComparisonFindingVerificationReconciliationResult",
    "assemble_verified_findings_artifact",
    "max_finding_sequence_number",
    "reconcile_existing_findings",
    "reconcile_verification_job",
]
