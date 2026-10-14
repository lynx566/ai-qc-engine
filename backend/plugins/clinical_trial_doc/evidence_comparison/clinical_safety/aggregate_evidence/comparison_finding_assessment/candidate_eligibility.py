"""Per-candidate eligibility filtering for Comparison Finding Assessment."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ..comparison_mode import ComparisonModeId
from .job_sentence_aliases import (
    collect_job_allowed_sentence_aliases,
    collect_job_group_sentence_aliases,
)
from .jobs import ComparisonFindingAssessmentJob
from .response_validation import (
    ComparisonFindingAssessmentCandidate,
    ComparisonFindingAssessmentValidatedResponse,
)

CandidateDropReason = Literal[
    "alias_outside_job_input",
    "missing_required_comparison_side",
]

_MODE_REQUIRED_SIDE_GROUP_ROLES: Mapping[
    ComparisonModeId,
    tuple[str, str] | None,
] = {
    "scope_local": None,
    "focus_comparison": ("focus_scope", "comparison_scopes"),
    "ib_to_dsur": ("ib_scope", "dsur_scopes"),
    "dsur_to_ib": ("dsur_scopes", "ib_scopes"),
}


@dataclass(frozen=True, slots=True)
class CandidateDropRecord:
    """One eligibility-filtered candidate with a canonical drop reason."""

    candidate_index: int
    reason: CandidateDropReason
    trigger_sentence_aliases: tuple[str, ...]
    missing_group_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateEligibilityResult:
    """Deterministic accepted/dropped split for one validated response."""

    accepted_response: ComparisonFindingAssessmentValidatedResponse
    dropped_candidates: tuple[CandidateDropRecord, ...]
    received_candidate_count: int
    accepted_candidate_count: int
    dropped_candidate_count: int
    drop_reason_counts: Mapping[CandidateDropReason, int]


def evaluate_trigger_alias_eligibility(
    trigger_sentence_aliases: Sequence[str],
    *,
    allowed_input_aliases: frozenset[str],
    group_sentence_aliases: Mapping[str, frozenset[str]],
    required_side_group_roles: tuple[str, str] | None,
) -> tuple[bool, CandidateDropReason | None, tuple[str, ...]]:
    """Return whether trigger aliases satisfy job input ownership and side coverage."""

    for alias in trigger_sentence_aliases:
        if alias not in allowed_input_aliases:
            return False, "alias_outside_job_input", ()

    if required_side_group_roles is None:
        return True, None, ()

    missing_roles: list[str] = []
    for group_role in required_side_group_roles:
        side_aliases = group_sentence_aliases.get(group_role, frozenset())
        if not any(alias in side_aliases for alias in trigger_sentence_aliases):
            missing_roles.append(group_role)
    if missing_roles:
        return False, "missing_required_comparison_side", tuple(missing_roles)
    return True, None, ()


def required_side_group_roles_for_mode(
    comparison_mode_id: ComparisonModeId,
) -> tuple[str, str] | None:
    """Return required comparison-side group roles for one comparison mode, if any."""

    return _MODE_REQUIRED_SIDE_GROUP_ROLES[comparison_mode_id]


def filter_eligible_candidates(
    validated_response: ComparisonFindingAssessmentValidatedResponse,
    *,
    job: ComparisonFindingAssessmentJob,
    aggregate_comparison_evidence: Mapping[str, Any],
) -> CandidateEligibilityResult:
    """Filter schema-valid candidates by job-local alias ownership and side coverage."""

    allowed_input_aliases = collect_job_allowed_sentence_aliases(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    group_sentence_aliases = collect_job_group_sentence_aliases(
        job=job,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    required_side_group_roles = _MODE_REQUIRED_SIDE_GROUP_ROLES[job.comparison_mode_id]

    accepted: list[ComparisonFindingAssessmentCandidate] = []
    dropped: list[CandidateDropRecord] = []
    reason_counts: Counter[CandidateDropReason] = Counter()

    for index, candidate in enumerate(validated_response.candidates):
        is_accepted, reason, missing_group_roles = evaluate_trigger_alias_eligibility(
            candidate.trigger_sentence_aliases,
            allowed_input_aliases=allowed_input_aliases,
            group_sentence_aliases=group_sentence_aliases,
            required_side_group_roles=required_side_group_roles,
        )
        if is_accepted:
            accepted.append(candidate)
            continue
        if reason is None:
            raise RuntimeError(
                "eligibility evaluation returned rejected without reason"
            )
        dropped.append(
            CandidateDropRecord(
                candidate_index=index,
                reason=reason,
                trigger_sentence_aliases=candidate.trigger_sentence_aliases,
                missing_group_roles=missing_group_roles,
            )
        )
        reason_counts[reason] += 1

    received_count = len(validated_response.candidates)
    accepted_count = len(accepted)
    dropped_count = len(dropped)
    return CandidateEligibilityResult(
        accepted_response=ComparisonFindingAssessmentValidatedResponse(
            candidates=tuple(accepted),
        ),
        dropped_candidates=tuple(dropped),
        received_candidate_count=received_count,
        accepted_candidate_count=accepted_count,
        dropped_candidate_count=dropped_count,
        drop_reason_counts=dict(reason_counts),
    )


def serialize_candidate_eligibility_audit(
    eligibility_result: CandidateEligibilityResult,
) -> dict[str, Any]:
    """Serialize eligibility counts and per-item drop records for debug persistence."""

    return {
        "received_candidate_count": eligibility_result.received_candidate_count,
        "accepted_candidate_count": eligibility_result.accepted_candidate_count,
        "dropped_candidate_count": eligibility_result.dropped_candidate_count,
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
        "dropped_candidates": [
            {
                "index": record.candidate_index,
                "reason": record.reason,
                "trigger_sentence_aliases": list(record.trigger_sentence_aliases),
                **(
                    {"missing_group_roles": list(record.missing_group_roles)}
                    if record.missing_group_roles
                    else {}
                ),
            }
            for record in eligibility_result.dropped_candidates
        ],
    }


__all__ = [
    "CandidateDropReason",
    "CandidateDropRecord",
    "CandidateEligibilityResult",
    "evaluate_trigger_alias_eligibility",
    "filter_eligible_candidates",
    "required_side_group_roles_for_mode",
    "serialize_candidate_eligibility_audit",
]
