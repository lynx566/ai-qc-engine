"""Canonical route step: pure in-memory orchestration (no I/O)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.routing.route_bundles import build_route_stage_artifacts
from artifacts.routing.schema import (
    is_projected_source_route_input_id,
    validate_route_projected_upstream_identity,
    validate_route_projection_static_upstream_document_identity,
)
from operations.filter_output_projection.contracts import ProjectedSource
from operations.projected_source_route.contracts import ProjectedSourceRouteExecutor


@dataclass(frozen=True)
class RouteStepResult:
    doc_id: str
    zone_key: str
    route_artifacts: dict[str, Any]


def _route_artifact_envelope(
    *,
    doc_id: str,
    file_hash: str,
    route_input_id: str,
    projection_input_refs: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "route_input_id": route_input_id,
        "doc_id": doc_id,
        "file_hash": file_hash,
    }
    if projection_input_refs is not None:
        envelope["projection_input_refs"] = [dict(ref) for ref in projection_input_refs]
    return envelope


def run_from_projected_sources(
    *,
    projected_sources: Sequence[ProjectedSource],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
    expected_semantic_module_id: str,
    route_executor: ProjectedSourceRouteExecutor,
    route_input_id: str = "projected_route_input",
    projection_input_refs: Sequence[Mapping[str, str]] | None = None,
    projection_doc_id: str | None = None,
    projection_file_hash: str | None = None,
) -> RouteStepResult:
    """Canonical Route entry for already-selected projected semantic sources."""

    if is_projected_source_route_input_id(route_input_id):
        if not projected_sources:
            raise ValueError(
                "projection_input_refs are required when routing projected sources"
            )
        if not projection_input_refs:
            raise ValueError(
                "projection_input_refs are required when routing projected sources"
            )
        if not isinstance(projection_doc_id, str) or not projection_doc_id.strip():
            raise ValueError(
                "projection_doc_id is required when routing projected sources"
            )
        if not isinstance(projection_file_hash, str) or not projection_file_hash.strip():
            raise ValueError(
                "projection_file_hash is required when routing projected sources"
            )
        doc_id, file_hash = validate_route_projection_static_upstream_document_identity(
            projection_doc_id=projection_doc_id.strip(),
            projection_file_hash=projection_file_hash.strip(),
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
            analysis_bundle=analysis_bundle,
        )
    else:
        doc_id, file_hash = validate_route_projected_upstream_identity(
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
            analysis_bundle=analysis_bundle,
        )
    routed = route_executor(
        projected_sources=projected_sources,
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
        expected_semantic_module_id=expected_semantic_module_id,
        doc_id=doc_id,
        file_hash=file_hash,
    )
    route_artifacts = build_route_stage_artifacts(
        routed=routed,
        route_input_envelope=_route_artifact_envelope(
            doc_id=doc_id,
            file_hash=file_hash,
            route_input_id=route_input_id,
            projection_input_refs=projection_input_refs,
        ),
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
    )
    return RouteStepResult(
        doc_id=doc_id,
        zone_key="",
        route_artifacts=route_artifacts,
    )


__all__ = ["RouteStepResult", "run_from_projected_sources"]
