"""Deterministic Aggregate Evidence Comparison input transformation."""

from __future__ import annotations

from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    format_scope_alias,
    format_sentence_alias,
    format_unit_alias,
)

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonInvocation,
)


def materialize_aggregate_comparison_evidence(
    *,
    invocation: AggregateEvidenceComparisonInvocation,
) -> dict[str, Any]:
    """Project ordered aggregate inputs into formal comparison evidence."""

    if not isinstance(invocation, AggregateEvidenceComparisonInvocation):
        raise TypeError(
            "invocation must be an AggregateEvidenceComparisonInvocation; "
            f"got {type(invocation)!r}"
        )

    scope_counter = 1
    unit_counter = 1
    sentence_counter = 1
    canonical_participants: list[dict[str, Any]] = []

    for participant in invocation.participants:
        canonical_scopes: list[dict[str, Any]] = []
        for source_scope in participant.scopes:
            canonical_units: list[dict[str, Any]] = []
            for source_unit in source_scope.units:
                canonical_sentences: list[dict[str, Any]] = []
                for source_sentence in source_unit.sentences:
                    canonical_sentences.append(
                        {
                            "sentence_id": source_sentence.source_sentence_id,
                            "sentence_alias": format_sentence_alias(
                                sentence_counter
                            ),
                            "text": source_sentence.text,
                        }
                    )
                    sentence_counter += 1

                canonical_units.append(
                    {
                        "unit_id": source_unit.source_unit_id,
                        "unit_alias": format_unit_alias(unit_counter),
                        "sentences": canonical_sentences,
                    }
                )
                unit_counter += 1

            canonical_scopes.append(
                {
                    "scope_id": source_scope.source_scope_id,
                    "scope_alias": format_scope_alias(scope_counter),
                    "heading_path": list(source_scope.semantic_path),
                    "units": canonical_units,
                }
            )
            scope_counter += 1

        canonical_participants.append(
            {
                "role_id": participant.role_id,
                "aggregate_evidence_source_bundle_id": (
                    participant.source_provenance.source_artifact_id
                ),
                "doc_id": participant.source_provenance.doc_id,
                "file_hash": participant.source_provenance.file_hash,
                "scopes": canonical_scopes,
            }
        )

    return build_aggregate_comparison_evidence(
        participants=canonical_participants,
    )


__all__ = ["materialize_aggregate_comparison_evidence"]
