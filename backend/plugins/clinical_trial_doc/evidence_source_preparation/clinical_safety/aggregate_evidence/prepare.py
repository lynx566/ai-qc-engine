"""Aggregate Evidence prepare processor entry."""

from __future__ import annotations

from typing import Any

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    ProjectedFanInPrepareContext,
    prepare_aggregate_evidence_semantic_result,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidencePrepareSemanticBinding,
)


def run_aggregate_evidence_prepare(
    *,
    aggregate_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    prepare_semantic: AggregateEvidencePrepareSemanticBinding,
    coverage_bundle: dict[str, Any] | None = None,
    projected_fan_in: ProjectedFanInPrepareContext | None = None,
) -> dict[str, Any]:
    """
    Plugin boundary for Aggregate Evidence prepare semantic processing.

    Consumes in-memory route/coverage/doc_meta payloads only; does not re-run routing,
    build formal artifacts, validate envelopes, or perform IO.
    """
    return prepare_aggregate_evidence_semantic_result(
        aggregate_bundle=aggregate_bundle,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        assessment_profile_ref=prepare_semantic.assessment_profile_ref,
        instructions=prepare_semantic.instructions,
        projected_fan_in=projected_fan_in,
    )
