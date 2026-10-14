"""Filesystem-free in-memory phase facade for clinical-safety aggregate evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_prepare_integrity import (
    validate_aggregate_prepare_handoff,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
    ASSESSMENT_INPUT_FILENAME,
    _validate_block_manifest_doc_meta_upstream,
    _validate_upstream_inputs,
    build_aggregate_evidence_assessment_input_envelope,
    build_assessment_input_preview,
    validate_aggregate_evidence_prepare_assessment_artifacts,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
    count_compact_assessment_stats,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    validate_aggregate_evidence_prepare_route_artifacts,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_review import (
    build_scope_assessment_review_envelope,
    validate_scope_assessment_review_envelope,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_FILENAME,
    validate_scope_assessments_envelope,
)
from llm.providers.base import LLMProvider
from operations.evidence_source_preparation.coverage_resolution import (
    is_projected_multi_source_fan_in,
)

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assess import (
    run_aggregate_evidence_assess as plugin_run_aggregate_evidence_assess,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceAssessmentExecution,
    AggregateEvidenceEligibilityExecution,
    AggregateEvidencePrepareExecution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceRouteArtifactsInput,
    EvidenceSourcePreparationUpstreamInput,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    ProjectedFanInPrepareContext,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.prepare import (
    run_aggregate_evidence_prepare as plugin_run_aggregate_evidence_prepare,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import (
    API_RUN_STATUS_COMPLETED_WITH_FALLBACK,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidencePrepareSemanticBinding,
    HeadingScopeEligibilityEntriesBuilder,
)


def _projected_fan_in_context(
    upstream: EvidenceSourcePreparationUpstreamInput,
    *,
    aggregate_bundle: Mapping[str, Any],
) -> ProjectedFanInPrepareContext | None:
    projected = upstream.projected_coverage_by_filter_job
    if projected is None:
        return None
    distinct_count = len(
        {
            str(bundle.get("coverage_bundle_id") or "")
            for bundle in projected.bundles_by_filter_job_id.values()
        }
    )
    if not is_projected_multi_source_fan_in(
        aggregate_bundle=aggregate_bundle,
        projection_input_refs=upstream.projection_input_refs,
        distinct_coverage_count=distinct_count,
    ):
        return None
    semantic_module_id = str(upstream.semantic_module_id or "").strip()
    if not semantic_module_id:
        raise ValueError(
            "semantic_module_id is required for projected multi-source fan-in prepare"
        )
    return ProjectedFanInPrepareContext(
        semantic_module_id=semantic_module_id,
        projection_input_refs=upstream.projection_input_refs,
    )


def _validate_projected_fan_in_prepare(
    *,
    upstream: EvidenceSourcePreparationUpstreamInput,
    aggregate_bundle: Mapping[str, Any],
) -> None:
    projected = upstream.projected_coverage_by_filter_job
    if projected is None:
        raise ValueError("projected_coverage_by_filter_job is required")
    if not upstream.projection_input_refs:
        raise ValueError("projection_input_refs is required for projected fan-in prepare")

    _validate_block_manifest_doc_meta_upstream(
        block_manifest=upstream.block_manifest,
        doc_meta_bundle=upstream.doc_meta_bundle,
    )

    routed_doc_id = str(aggregate_bundle.get("doc_id") or "")
    manifest_doc_id = str(upstream.block_manifest.get("doc_id") or "")
    if routed_doc_id and routed_doc_id != manifest_doc_id:
        raise ValueError(
            f"doc_id mismatch: routed aggregate={routed_doc_id!r} "
            f"block_manifest={manifest_doc_id!r}"
        )

    bundles_by_filter_job_id = projected.bundles_by_filter_job_id
    contributor_filter_job_ids = set(bundles_by_filter_job_id)

    for ref in upstream.projection_input_refs:
        coverage_bundle = bundles_by_filter_job_id.get(ref.filter_job_id)
        if coverage_bundle is None:
            raise ValueError(
                "missing coverage bundle for projection_input_ref.filter_job_id "
                f"{ref.filter_job_id!r}"
            )
        coverage_zone = str(coverage_bundle.get("zone_key") or "")
        if ref.zone_key != coverage_zone:
            raise ValueError(
                "projection_input_ref.zone_key mismatch for "
                f"filter_job_id={ref.filter_job_id!r}: ref={ref.zone_key!r} "
                f"coverage={coverage_zone!r}"
            )
        coverage_doc_id = str(coverage_bundle.get("doc_id") or "")
        if routed_doc_id and coverage_doc_id and routed_doc_id != coverage_doc_id:
            raise ValueError(
                f"doc_id mismatch for filter_job_id={ref.filter_job_id!r}: "
                f"routed aggregate={routed_doc_id!r} coverage={coverage_doc_id!r}"
            )

    for unit in aggregate_bundle.get("units") or []:
        if not isinstance(unit, dict):
            continue
        unit_id = str(unit.get("unit_id") or "")
        filter_job_id = str(unit.get("filter_job_id") or "").strip()
        if not filter_job_id:
            raise ValueError(f"aggregate unit {unit_id!r} missing filter_job_id")
        if filter_job_id not in contributor_filter_job_ids:
            raise ValueError(
                f"aggregate unit {unit_id!r} filter_job_id {filter_job_id!r} "
                "is not in projection contributor set"
            )
        if not str(unit.get("source_zone_key") or "").strip():
            raise ValueError(f"aggregate unit {unit_id!r} missing source_zone_key")


def run_aggregate_evidence_prepare(
    *,
    upstream: EvidenceSourcePreparationUpstreamInput,
    route_artifacts: AggregateEvidenceRouteArtifactsInput,
    evidence_form_id: str,
    prepare_semantic: AggregateEvidencePrepareSemanticBinding,
) -> AggregateEvidencePrepareExecution:
    if not evidence_form_id.strip():
        raise ValueError("evidence_form_id must be a non-empty path segment")

    coverage_bundle = upstream.coverage_bundle
    block_manifest = upstream.block_manifest
    doc_meta_bundle = upstream.doc_meta_bundle

    aggregate_bundle = route_artifacts.aggregate_bundle
    routing_manifest = route_artifacts.routing_manifest

    projected_fan_in = _projected_fan_in_context(
        upstream,
        aggregate_bundle=aggregate_bundle,
    )

    if projected_fan_in is not None:
        _validate_projected_fan_in_prepare(
            upstream=upstream,
            aggregate_bundle=aggregate_bundle,
        )
    else:
        if coverage_bundle is None:
            raise ValueError("coverage_bundle is required for single-source prepare")
        _validate_upstream_inputs(
            coverage_bundle=coverage_bundle,
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
        )

    validate_aggregate_evidence_prepare_route_artifacts(
        aggregate_bundle=aggregate_bundle,
        routing_manifest=routing_manifest,
        projected_fan_in=projected_fan_in is not None,
    )

    if projected_fan_in is None:
        assert coverage_bundle is not None
        routed_doc_id = str(aggregate_bundle.get("doc_id") or "")
        coverage_doc_id = str(coverage_bundle.get("doc_id") or "")
        if routed_doc_id and routed_doc_id != coverage_doc_id:
            raise ValueError(
                f"doc_id mismatch: routed aggregate={routed_doc_id!r} "
                f"coverage_bundle={coverage_doc_id!r}"
            )
        routed_zone = str(aggregate_bundle.get("zone_key") or "")
        coverage_zone = str(coverage_bundle.get("zone_key") or "")
        if routed_zone and routed_zone != coverage_zone:
            raise ValueError(
                f"zone_key mismatch: routed aggregate={routed_zone!r} "
                f"coverage_bundle={coverage_zone!r}"
            )

    semantic_result = plugin_run_aggregate_evidence_prepare(
        aggregate_bundle=aggregate_bundle,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        prepare_semantic=prepare_semantic,
        projected_fan_in=projected_fan_in,
    )

    routed_bundle_id = str(aggregate_bundle.get("routed_unit_bundle_id") or "")
    routing_manifest_id = str(routing_manifest.get("routing_manifest_id") or "")
    source_routed_unit_bundle_ref = {
        "routed_unit_bundle_id": routed_bundle_id,
        "path": route_artifacts.source_routed_unit_bundle_filename,
    }
    source_routing_manifest_ref = {
        "routing_manifest_id": routing_manifest_id,
        "path": route_artifacts.routing_manifest_filename,
    }

    envelope = build_aggregate_evidence_assessment_input_envelope(
        semantic_result=semantic_result,
        source_routed_unit_bundle_ref=source_routed_unit_bundle_ref,
        source_routing_manifest_ref=source_routing_manifest_ref,
        coverage_bundle_ref=(
            None
            if projected_fan_in is not None
            else {
                "coverage_bundle_id": coverage_bundle.get("coverage_bundle_id"),  # type: ignore[union-attr]
            }
        ),
        block_manifest_ref={
            "block_manifest_id": block_manifest.get("block_manifest_id"),
        },
        doc_meta_ref={"doc_meta_bundle_id": doc_meta_bundle.get("doc_meta_bundle_id")},
        projected_fan_in_identity=(
            {
                "file_hash": str(upstream.block_manifest.get("file_hash") or ""),
                "semantic_module_id": projected_fan_in.semantic_module_id,
                "projection_input_refs": [
                    {
                        "filter_output_projection_bundle_id": (
                            ref.filter_output_projection_bundle_id
                        ),
                        "filter_job_id": ref.filter_job_id,
                        "zone_key": ref.zone_key,
                    }
                    for ref in projected_fan_in.projection_input_refs
                ],
            }
            if projected_fan_in is not None
            else None
        ),
    )
    assessment_input = envelope["assessment_input"]
    assessment_runtime_context = envelope["assessment_runtime_context"]
    validate_aggregate_evidence_prepare_assessment_artifacts(
        assessment_input,
        assessment_runtime_context,
    )

    assessment_input_preview = build_assessment_input_preview(assessment_input)
    compact_stats = count_compact_assessment_stats(assessment_input)
    aggregate_unit_count = compact_stats["assessment_unit_count"]

    canonical_aggregate_units = semantic_result["canonical_aggregate_units"]
    unit_integrity_report = validate_aggregate_prepare_handoff(
        assessment_input=assessment_input,
        runtime_context=assessment_runtime_context,
        aggregate_units=canonical_aggregate_units,
    )
    error_count = int(unit_integrity_report.get("summary", {}).get("error_count") or 0)
    if error_count > 0:
        raise ValueError(
            "aggregate prepare handoff validation failed with "
            f"{error_count} error(s)"
        )

    doc_id = str(assessment_input.get("doc_id") or "")
    zone_key = str(assessment_input.get("zone_key") or "")

    return AggregateEvidencePrepareExecution(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        assessment_input_preview=assessment_input_preview,
        unit_integrity_report=unit_integrity_report,
        semantic_result=semantic_result,
        aggregate_unit_count=aggregate_unit_count,
        doc_id=doc_id,
        zone_key=zone_key,
    )


def run_aggregate_evidence_assess_heading_scopes(
    *,
    assessment_input: dict[str, Any],
    assessment_runtime_context: dict[str, Any],
    assessment_profile_name: str,
    llm_mode: str = "mock",
    llm_profile: str | None = None,
    provider: LLMProvider | None = None,
    llm_execution_config: dict[str, Any] | None = None,
    assessment_input_ref: str | None = None,
    assessment_runtime_context_ref: str | None = None,
    allow_api_parse_fallback: bool = False,
) -> AggregateEvidenceAssessmentExecution:
    input_ref = assessment_input_ref or ASSESSMENT_INPUT_FILENAME
    runtime_context_ref = (
        assessment_runtime_context_ref or ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    )

    assess_result = plugin_run_aggregate_evidence_assess(
        assessment_input,
        assessment_profile_name=assessment_profile_name,
        llm_mode=llm_mode,
        llm_profile=llm_profile,
        provider=provider,
        llm_execution_config=llm_execution_config,
        assessment_input_path=input_ref,
        allow_api_parse_fallback=allow_api_parse_fallback,
        assessment_runtime_context=assessment_runtime_context,
        assessment_runtime_context_path=runtime_context_ref,
    )

    scope_assessments = assess_result["scope_assessments"]
    validate_scope_assessments_envelope(scope_assessments)

    scope_assessment_trace = assess_result.get("scope_assessment_trace")
    scope_assessment_review: dict[str, Any] | None = None
    if isinstance(scope_assessment_trace, dict):
        scope_assessment_review = build_scope_assessment_review_envelope(
            scope_assessments=scope_assessments,
            scope_assessment_trace=scope_assessment_trace,
            scope_assessments_path=SCOPE_ASSESSMENTS_FILENAME,
            assessment_input=assessment_input,
            assessment_runtime_context=assessment_runtime_context,
        )
        validate_scope_assessment_review_envelope(scope_assessment_review)

    api_result = scope_assessments.get("api_result") or {}
    run_status = (
        API_RUN_STATUS_COMPLETED_WITH_FALLBACK
        if api_result.get("fallback_used") is True
        else str(assess_result.get("run_status") or "success")
    )

    return AggregateEvidenceAssessmentExecution(
        scope_assessments=scope_assessments,
        scope_assessment_review=scope_assessment_review,
        scope_assessments_filename=SCOPE_ASSESSMENTS_FILENAME,
        llm_debug_artifacts=assess_result.get("llm_debug_artifacts"),
        run_status=run_status,
        profile_name=assessment_profile_name,
        scope_assessment_count=int(scope_assessments.get("scope_assessment_count") or 0),
        scope_assessment_trace=(
            scope_assessment_trace if isinstance(scope_assessment_trace, dict) else None
        ),
        llm_invocations=tuple(assess_result.get("llm_invocations", ())),
    )


def run_aggregate_evidence_evaluate_heading_scope_eligibility(
    *,
    scope_assessments: dict[str, Any],
    source_scope_assessments_ref: Mapping[str, Any],
    build_heading_scope_eligibility_entries: HeadingScopeEligibilityEntriesBuilder,
) -> AggregateEvidenceEligibilityExecution:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
        build_heading_scope_eligibility_envelope,
        validate_heading_scope_eligibility,
    )

    validate_scope_assessments_envelope(scope_assessments)

    scope_eligibility_entries = build_heading_scope_eligibility_entries(
        scope_assessments=scope_assessments.get("scope_assessments") or [],
    )
    heading_scope_eligibility = build_heading_scope_eligibility_envelope(
        scope_assessments_payload=scope_assessments,
        scope_eligibility_entries=scope_eligibility_entries,
        source_scope_assessments_ref=source_scope_assessments_ref,
    )
    validate_heading_scope_eligibility(
        heading_scope_eligibility,
        source_scope_assessments_payload=scope_assessments,
    )

    return AggregateEvidenceEligibilityExecution(
        heading_scope_eligibility=heading_scope_eligibility,
        auto_included_scope_count=int(
            heading_scope_eligibility.get("auto_included_scope_count") or 0
        ),
        excluded_scope_count=int(heading_scope_eligibility.get("excluded_scope_count") or 0),
        review_ambiguous_scope_count=int(
            heading_scope_eligibility.get("review_ambiguous_scope_count") or 0
        ),
    )
