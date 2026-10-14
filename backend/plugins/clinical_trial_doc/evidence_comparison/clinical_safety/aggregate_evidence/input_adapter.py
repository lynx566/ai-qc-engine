"""Public role-binding adapter for canonical Aggregate Comparison input."""

from __future__ import annotations

from collections.abc import Sequence

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonInvocation,
    AggregateEvidenceComparisonParticipant,
    AggregateEvidenceComparisonParticipantEvidence,
)


def build_aggregate_evidence_comparison_invocation(
    *,
    participants: Sequence[tuple[str, AggregateEvidenceComparisonParticipantEvidence]],
) -> AggregateEvidenceComparisonInvocation:
    """Preserve participant order and bind Comparison-local roles."""

    return AggregateEvidenceComparisonInvocation(
        participants=tuple(
            AggregateEvidenceComparisonParticipant(
                role_id=role_id,
                source_provenance=evidence.source_provenance,
                scopes=evidence.scopes,
            )
            for role_id, evidence in participants
        )
    )


__all__ = ["build_aggregate_evidence_comparison_invocation"]
