"""Additional-finding eligibility filtering for Comparison Finding Verification."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..comparison_finding_assessment.candidate_eligibility import (
    CandidateDropReason,
    evaluate_trigger_alias_eligibility,
    required_side_group_roles_for_mode,
)
from ..comparison_finding_assessment.job_sentence_aliases import (
    collect_job_allowed_sentence_aliases,
    collect_job_group_sentence_aliases,
)
from ..comparison_finding_assessment.jobs import ComparisonFindingAssessmentJob
from .response_validation import ComparisonFindingVerificationAdditionalFinding

ADDITIONAL_FINDING_ELIGIBILITY_DEBUG_FILENAME = "additional_finding_eligibility.json"


@dataclass(frozen=True, slots=True)
class DroppedAdditionalFinding:
    additional_finding_index: int
    reason: CandidateDropReason
    source_sentence_aliases: tuple[str, ...]
    missing_group_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AdditionalFindingEligibilityResult:
    accepted_additional_findings: tuple[
        ComparisonFindingVerificationAdditionalFinding, ...
    ]
    dropped_additional_findings: tuple[DroppedAdditionalFinding, ...]
    received_additional_finding_count: int
    accepted_additional_finding_count: int
    dropped_additional_finding_count: int
    drop_reason_counts: Mapping[CandidateDropReason, int]


def filter_eligible_additional_findings(
    additional_findings: Sequence[ComparisonFindingVerificationAdditionalFinding],
    *,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
) -> AdditionalFindingEligibilityResult:
    """Filter schema-valid additional findings by job-local alias eligibility."""

    allowed_input_aliases = collect_job_allowed_sentence_aliases(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    group_sentence_aliases = collect_job_group_sentence_aliases(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    required_side_group_roles = required_side_group_roles_for_mode(
        job.comparison_mode_id,
    )

    accepted: list[ComparisonFindingVerificationAdditionalFinding] = []
    dropped: list[DroppedAdditionalFinding] = []
    reason_counts: Counter[CandidateDropReason] = Counter()

    for index, additional_finding in enumerate(additional_findings):
        is_accepted, reason, missing_group_roles = evaluate_trigger_alias_eligibility(
            additional_finding.source_sentence_aliases,
            allowed_input_aliases=allowed_input_aliases,
            group_sentence_aliases=group_sentence_aliases,
            required_side_group_roles=required_side_group_roles,
        )
        if is_accepted:
            accepted.append(additional_finding)
            continue
        if reason is None:
            raise RuntimeError(
                "eligibility evaluation returned rejected without reason"
            )
        dropped.append(
            DroppedAdditionalFinding(
                additional_finding_index=index,
                reason=reason,
                source_sentence_aliases=additional_finding.source_sentence_aliases,
                missing_group_roles=missing_group_roles,
            )
        )
        reason_counts[reason] += 1

    received_count = len(additional_findings)
    return AdditionalFindingEligibilityResult(
        accepted_additional_findings=tuple(accepted),
        dropped_additional_findings=tuple(dropped),
        received_additional_finding_count=received_count,
        accepted_additional_finding_count=len(accepted),
        dropped_additional_finding_count=len(dropped),
        drop_reason_counts=dict(reason_counts),
    )


def serialize_additional_finding_eligibility_audit(
    eligibility_result: AdditionalFindingEligibilityResult,
) -> dict[str, Any]:
    """Serialize additional-finding eligibility counts and drop records."""

    return {
        "received_additional_finding_count": (
            eligibility_result.received_additional_finding_count
        ),
        "accepted_additional_finding_count": (
            eligibility_result.accepted_additional_finding_count
        ),
        "dropped_additional_finding_count": (
            eligibility_result.dropped_additional_finding_count
        ),
        "drop_reason_counts": {
            "alias_outside_job_input": eligibility_result.drop_reason_counts.get(
                "alias_outside_job_input",
                0,
            ),
            "missing_required_comparison_side": eligibility_result.drop_reason_counts.get(
                "missing_required_comparison_side",
                0,
            ),
        },
        "accepted_additional_findings": [
            {
                "conclusion": finding.conclusion,
                "label": finding.label,
                "source_sentence_aliases": list(finding.source_sentence_aliases),
            }
            for finding in eligibility_result.accepted_additional_findings
        ],
        "dropped_additional_findings": [
            {
                "additional_finding_index": record.additional_finding_index,
                "reason": record.reason,
                "source_sentence_aliases": list(record.source_sentence_aliases),
                **(
                    {"missing_group_roles": list(record.missing_group_roles)}
                    if record.missing_group_roles
                    else {}
                ),
            }
            for record in eligibility_result.dropped_additional_findings
        ],
    }


__all__ = [
    "ADDITIONAL_FINDING_ELIGIBILITY_DEBUG_FILENAME",
    "AdditionalFindingEligibilityResult",
    "DroppedAdditionalFinding",
    "filter_eligible_additional_findings",
    "serialize_additional_finding_eligibility_audit",
]
