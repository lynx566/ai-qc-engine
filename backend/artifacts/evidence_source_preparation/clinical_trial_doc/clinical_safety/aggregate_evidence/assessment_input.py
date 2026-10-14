"""Build assessment_input.json for Aggregate Evidence prepare."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    build_assessment_runtime_context_envelope,
    build_assessment_runtime_context_id,
    count_compact_assessment_stats,
    validate_scoped_assessment_cross_artifacts,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_ids import (
    build_llm_input_bundle_id,
    build_projected_fan_in_llm_input_bundle_id,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_preview import (
    build_llm_input_preview,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_safety import (
    assert_assessment_input_safe,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
    validate_assessment_input,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from artifacts.upstream_validation import (
    validate_coverage_block_manifest_doc_meta_upstream,
)

ASSESSMENT_INPUT_FILENAME = "assessment_input.json"
ASSESSMENT_INPUT_PREVIEW_FILENAME = "assessment_input_preview.json"


def _validate_upstream_inputs(
    *,
    coverage_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
) -> None:
    validate_coverage_block_manifest_doc_meta_upstream(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
    )


def _validate_block_manifest_doc_meta_upstream(
    *,
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
) -> None:
    from core.document.doc_identity import require_bundle_file_hash

    manifest_doc_id = str(block_manifest.get("doc_id") or "").strip()
    meta_doc_id = str(doc_meta_bundle.get("doc_id") or "").strip()
    if not manifest_doc_id or not meta_doc_id:
        raise ValueError("block_manifest.doc_id and doc_meta_bundle.doc_id are required")
    if manifest_doc_id != meta_doc_id:
        raise ValueError(
            f"doc_id mismatch: block_manifest={manifest_doc_id!r} "
            f"doc_meta_bundle={meta_doc_id!r}"
        )
    if not isinstance(doc_meta_bundle.get("summary"), dict):
        raise ValueError("doc_meta_bundle.summary is required")  # noqa: TRY004
    require_bundle_file_hash(block_manifest, label="block_manifest")


def build_aggregate_evidence_assessment_input_envelope(
    *,
    semantic_result: Mapping[str, Any],
    source_routed_unit_bundle_ref: Mapping[str, Any],
    source_routing_manifest_ref: Mapping[str, Any],
    coverage_bundle_ref: Mapping[str, Any] | None = None,
    block_manifest_ref: Mapping[str, Any] | None = None,
    doc_meta_ref: Mapping[str, Any] | None = None,
    projected_fan_in_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap prepared aggregate semantic result into formal assessment_input + runtime_context."""
    shared_metadata = dict(semantic_result.get("shared_metadata") or {})
    heading_scopes = semantic_result.get("heading_scopes") or []
    unit_provenance = semantic_result.get("unit_provenance") or {}

    if projected_fan_in_identity is not None:
        llm_input_bundle_id = build_projected_fan_in_llm_input_bundle_id(
            file_hash=str(projected_fan_in_identity.get("file_hash") or ""),
            semantic_module_id=str(
                projected_fan_in_identity.get("semantic_module_id") or ""
            ),
            projection_input_refs=list(
                projected_fan_in_identity.get("projection_input_refs") or []
            ),
            route="aggregate",
        )
    else:
        coverage_bundle_id = str(shared_metadata.get("coverage_bundle_id") or "")
        llm_input_bundle_id = build_llm_input_bundle_id(
            coverage_bundle_id=coverage_bundle_id,
            route="aggregate",
        )
    runtime_context_id = build_assessment_runtime_context_id(
        llm_input_bundle_id=llm_input_bundle_id,
    )

    assessment_input: dict[str, Any] = {
        key: value
        for key, value in shared_metadata.items()
        if key not in {"coverage_bundle_id", "route_stats"}
    }
    assessment_input.update(
        {
            "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
            "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
            "phase": EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
            "source_stage": "route",
            "llm_input_bundle_id": llm_input_bundle_id,
            "heading_scopes": list(heading_scopes),
            "runtime_context_ref": {
                "runtime_context_id": runtime_context_id,
            },
        }
    )

    runtime_context = build_assessment_runtime_context_envelope(
        llm_input_bundle_id=llm_input_bundle_id,
        runtime_context_id=runtime_context_id,
        doc_id=str(shared_metadata.get("doc_id") or ""),
        file_hash=str(shared_metadata.get("file_hash") or ""),
        route_stats=dict(shared_metadata.get("route_stats") or {}),
        unit_provenance=dict(unit_provenance),
        source_routed_unit_bundle_ref=source_routed_unit_bundle_ref,
        source_routing_manifest_ref=source_routing_manifest_ref,
        coverage_bundle_ref=coverage_bundle_ref,
        block_manifest_ref=block_manifest_ref,
        doc_meta_ref=doc_meta_ref,
    )

    validate_scoped_assessment_cross_artifacts(
        assessment_input,
        runtime_context,
        aggregate_units=semantic_result.get("canonical_aggregate_units"),
    )
    assert_assessment_input_safe(assessment_input)
    return {
        "assessment_input": assessment_input,
        "assessment_runtime_context": runtime_context,
    }


def build_assessment_input_preview(
    assessment_input: dict[str, Any],
    *,
    text_preview_chars: int = 200,
) -> dict[str, Any]:
    """Human-readable preview for aggregate assessment input only."""
    stats = count_compact_assessment_stats(assessment_input)
    aggregate_units = [
        unit
        for scope in assessment_input.get("heading_scopes") or []
        if isinstance(scope, dict)
        for unit in scope.get("units") or []
        if isinstance(unit, dict)
    ]
    llm_input_preview_source = {
        "doc_id": assessment_input.get("doc_id"),
        "zone_key": assessment_input.get("zone_key"),
        "route_counts": {"aggregate": stats["assessment_unit_count"]},
        "route_inputs": {
            "aggregate": {
                **assessment_input,
                "units": aggregate_units,
            }
        },
    }
    preview = build_llm_input_preview(
        llm_input_preview_source,
        text_preview_chars=text_preview_chars,
    )
    return {
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
        **preview,
    }


def validate_aggregate_evidence_prepare_assessment_artifacts(
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
) -> None:
    """Validate formal Aggregate Evidence prepare artifacts after envelope construction."""
    validate_assessment_input(assessment_input)
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
        validate_assessment_runtime_context,
    )

    validate_assessment_runtime_context(assessment_runtime_context)
    validate_scoped_assessment_cross_artifacts(
        assessment_input,
        assessment_runtime_context,
    )
