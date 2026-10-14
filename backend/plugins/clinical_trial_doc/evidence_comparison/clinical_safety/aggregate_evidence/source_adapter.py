"""Adapt clinical-safety aggregate ESP output into canonical Comparison input."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    validate_aggregate_evidence_source_bundle,
)

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonParticipantEvidence,
    AggregateEvidenceComparisonScope,
    AggregateEvidenceComparisonSentence,
    AggregateEvidenceComparisonSourceProvenance,
    AggregateEvidenceComparisonUnit,
)


def adapt_clinical_safety_aggregate_source_bundle(
    source_bundle: Mapping[str, Any],
) -> AggregateEvidenceComparisonParticipantEvidence:
    """Validate one clinical source and project comparison-eligible evidence."""

    validate_aggregate_evidence_source_bundle(source_bundle)
    heading_scopes = source_bundle["heading_scopes"]
    if not heading_scopes:
        raise ValueError(
            "clinical aggregate source contains no comparison-eligible scopes"
        )

    canonical_scopes: list[AggregateEvidenceComparisonScope] = []
    for source_scope in heading_scopes:
        canonical_units: list[AggregateEvidenceComparisonUnit] = []
        for source_unit in source_scope["units"]:
            canonical_sentences: list[AggregateEvidenceComparisonSentence] = []
            for source_sentence in source_unit["sentences"]:
                text = source_sentence["text"]
                if not text.strip():
                    raise ValueError(
                        "clinical aggregate source contains non-comparison-eligible "
                        "sentence text"
                    )
                canonical_sentences.append(
                    AggregateEvidenceComparisonSentence(
                        source_sentence_id=source_sentence["sentence_id"],
                        text=text,
                    )
                )
            canonical_units.append(
                AggregateEvidenceComparisonUnit(
                    source_unit_id=source_unit["unit_id"],
                    sentences=tuple(canonical_sentences),
                )
            )
        canonical_scopes.append(
            AggregateEvidenceComparisonScope(
                source_scope_id=source_scope["scope_id"],
                semantic_path=tuple(source_scope["heading_path"]),
                units=tuple(canonical_units),
            )
        )

    return AggregateEvidenceComparisonParticipantEvidence(
        source_provenance=AggregateEvidenceComparisonSourceProvenance(
            source_artifact_id=source_bundle["aggregate_evidence_source_bundle_id"],
            doc_id=source_bundle["doc_id"],
            file_hash=source_bundle["file_hash"],
        ),
        scopes=tuple(canonical_scopes),
    )


__all__ = ["adapt_clinical_safety_aggregate_source_bundle"]
