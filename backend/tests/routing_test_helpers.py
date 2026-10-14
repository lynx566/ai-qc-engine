"""Current Route test helpers that build formal in-memory route artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from artifacts.routing.route_bundles import build_route_stage_artifacts
from artifacts.routing.schema import validate_route_upstream_identity
from operations.filter_output_projection.contracts import ProjectedSource
from plugins.clinical_trial_doc.routing import (
    route_prepare_units_from_projected_sources,
)
from tests.route_test_fixtures import (
    DEFAULT_SEMANTIC_MODULE_ID,
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_manifest,
    _projected_sources_from_coverage_bundle,
    _route_input_envelope_from_coverage_bundle,
)


def build_current_route_artifacts_from_inputs(
    *,
    coverage_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any] | None = None,
    projected_sources: Sequence[ProjectedSource] | None = None,
) -> dict[str, Any]:
    """Build current routed units, routed bundles, and routing manifest in memory."""

    if analysis_bundle is None:
        resolved_analysis = _analysis_bundle_for_manifest(block_manifest)
        analysis_ref = block_manifest.get("analysis_bundle_ref") or {}
        analysis_bundle_id = str(analysis_ref.get("analysis_bundle_id") or "").strip()
        if analysis_bundle_id:
            resolved_analysis["analysis_bundle_id"] = analysis_bundle_id
    else:
        resolved_analysis = analysis_bundle
    doc_id, _zone_key = validate_route_upstream_identity(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=resolved_analysis,
    )
    routed = route_prepare_units_from_projected_sources(
        projected_sources=(
            tuple(projected_sources)
            if projected_sources is not None
            else _projected_sources_from_coverage_bundle(coverage_bundle)
        ),
        block_manifest=block_manifest,
        analysis_bundle=resolved_analysis,
        expected_semantic_module_id=DEFAULT_SEMANTIC_MODULE_ID,
        doc_id=doc_id,
        file_hash=str(
            coverage_bundle.get("file_hash")
            or block_manifest.get("file_hash")
            or LINEAGE_FILE_HASH
        ),
    )
    route_artifacts = build_route_stage_artifacts(
        routed=routed,
        route_input_envelope=_route_input_envelope_from_coverage_bundle(
            coverage_bundle
        ),
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=resolved_analysis,
    )
    return {"routed": routed, **route_artifacts}
