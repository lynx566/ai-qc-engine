"""Canonical projected-source Route stage runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from artifacts.filter_output_projection_bundle import (
    validate_filter_output_projection_bundle,
)
from artifacts.routing.schema import (
    ROUTED_UNITS_ROUTE_FILENAMES,
    ROUTING_MANIFEST_FILENAME,
)
from core.document.block_position import blocks_by_id
from operations.filter_output_projection.contracts import ProjectedSource
from operations.filter_output_projection.document_order import (
    sort_projected_sources_by_document_position,
)
from operations.filter_output_projection.fan_in import (
    build_projection_fan_in_inputs_from_bundles,
    resolve_projection_fan_in_document_identity,
    select_projected_sources_for_semantic_module,
)
from operations.projected_source_route.contracts import ProjectedSourceRouteExecutor
from steps.route import run_from_projected_sources
from plugins.clinical_trial_doc.filter_output_projection.document_anchor import (
    projected_source_document_anchor,
)
from runtime.io import load_json, save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import resolve_route_artifact_dir
from runtime.run_summaries import build_projected_source_route_run_summary


@dataclass(frozen=True)
class ProjectedSourceRouteStageInvocation:
    """Session-level context for one standalone projected-source Route runner invocation."""

    stamp: datetime
    session_dir: Path
    runs_root: Path
    git_root: Path
    custom_output_dir: Path | None = None


@dataclass(frozen=True)
class ProjectedSourceRouteStageResult:
    output_dir: Path
    run_id: str
    doc_id: str
    semantic_module_id: str
    route_counts: dict[str, int]
    routed_bundle_paths: dict[str, Path]
    routing_manifest_path: Path
    run_summary_path: Path


@dataclass(frozen=True)
class PersistedProjectionRouteStageOutcome:
    """Result of persisted-projection Route orchestration before/alongside stage I/O."""

    route_result: ProjectedSourceRouteStageResult | None
    selected_projected_source_count: int
    projection_bundle_count: int
    projection_input_refs: tuple[dict[str, str], ...]


def load_persisted_projection_bundles(
    projection_bundle_paths: Sequence[Path | str],
) -> list[dict[str, Any]]:
    """Load and validate persisted filter_output_projection_bundle payloads."""

    if not projection_bundle_paths:
        raise ValueError("projection_bundle_paths must be non-empty")

    bundles: list[dict[str, Any]] = []
    for index, raw_path in enumerate(projection_bundle_paths):
        path = Path(raw_path).resolve()
        bundle = load_json(path)
        if not isinstance(bundle, dict):
            raise ValueError(
                f"projection_bundle_paths[{index}] must be a JSON object: {path.as_posix()}"
            )
        validate_filter_output_projection_bundle(bundle)
        bundles.append(bundle)
    return bundles


def run_projected_source_route_from_projection_bundles(
    *,
    projection_bundle_paths: Sequence[Path | str],
    semantic_module_id: str,
    enabled_route_semantic_module_ids: Mapping[str, object] | frozenset[str] | None,
    block_manifest_path: Path | str,
    doc_meta_bundle_path: Path | str,
    analysis_bundle_path: Path | str,
    route_executor: ProjectedSourceRouteExecutor,
    git_provenance: dict[str, str | bool | None] | None = None,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
    route_key: str | None = None,
    invocation: ProjectedSourceRouteStageInvocation | None = None,
) -> PersistedProjectionRouteStageOutcome:
    """Orchestrate fan-in selection and canonical Route stage from persisted bundles."""

    bundles = load_persisted_projection_bundles(projection_bundle_paths)
    fan_in_inputs = build_projection_fan_in_inputs_from_bundles(bundles)
    projection_doc_id, projection_file_hash = resolve_projection_fan_in_document_identity(
        fan_in_inputs
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=fan_in_inputs,
        semantic_module_id=semantic_module_id,
        enabled_route_semantic_module_ids=enabled_route_semantic_module_ids,
    )
    projection_input_refs = tuple(ref.to_dict() for ref in selection.projection_input_refs)
    selected_count = len(selection.selected_projected_sources)
    if not selection.selected_projected_sources:
        return PersistedProjectionRouteStageOutcome(
            route_result=None,
            selected_projected_source_count=selected_count,
            projection_bundle_count=len(projection_bundle_paths),
            projection_input_refs=projection_input_refs,
        )

    resolved_output_dir = output_dir
    resolved_run_id = run_id
    if resolved_output_dir is None:
        if invocation is None:
            raise ValueError(
                "invocation is required when output_dir is not provided explicitly"
            )
        resolved_output_dir, resolved_run_id = resolve_projected_source_route_stage_paths(
            doc_id=fan_in_inputs[0].step_result.doc_id,
            route_key=route_key or "",
            invocation=invocation,
        )

    route_result = run_projected_source_route_stage(
        projected_sources=selection.selected_projected_sources,
        semantic_module_id=semantic_module_id,
        projection_input_refs=projection_input_refs,
        projection_doc_id=projection_doc_id,
        projection_file_hash=projection_file_hash,
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        output_dir=resolved_output_dir,
        git_provenance=git_provenance,
        run_id=resolved_run_id,
        route_executor=route_executor,
    )
    return PersistedProjectionRouteStageOutcome(
        route_result=route_result,
        selected_projected_source_count=selected_count,
        projection_bundle_count=len(projection_bundle_paths),
        projection_input_refs=projection_input_refs,
    )


def resolve_projected_source_route_run_id(*, stamp=None) -> str:
    resolved_stamp = stamp or utc_run_stamp()
    return format_run_timestamp(resolved_stamp)


def validate_route_stage_semantic_module_identity(
    *,
    requested_semantic_module_id: str,
    route_stage_result: ProjectedSourceRouteStageResult,
) -> None:
    """Fail fast when Route stage result identity diverges from the request."""

    if not isinstance(requested_semantic_module_id, str) or not requested_semantic_module_id.strip():
        raise ValueError("requested_semantic_module_id must be a non-empty string")
    requested = requested_semantic_module_id.strip()
    actual = route_stage_result.semantic_module_id
    if actual != requested:
        raise ValueError(
            "route stage semantic_module_id mismatch: "
            f"requested={requested!r} result={actual!r}"
        )


def resolve_projected_source_route_stage_paths(
    *,
    doc_id: str,
    route_key: str,
    invocation: ProjectedSourceRouteStageInvocation,
) -> tuple[Path, str]:
    """Resolve canonical artifact sink path and run_id for one Route stage run."""

    run_id = invocation.session_dir.name
    if invocation.custom_output_dir is not None:
        return Path(invocation.custom_output_dir).resolve(), run_id

    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError("doc_id must be a non-empty string")
    if not isinstance(route_key, str) or not route_key.strip():
        raise ValueError("route_key must be a non-empty string")
    route_key = route_key.strip()

    out_dir, _session_dir = resolve_route_artifact_dir(
        project_root=invocation.git_root,
        zone_key=route_key,
        doc_id=doc_id.strip(),
        run_id=run_id,
        stamp=invocation.stamp,
    )
    return out_dir, run_id


def run_projected_source_route_stage(
    *,
    projected_sources: Sequence[ProjectedSource],
    semantic_module_id: str,
    block_manifest_path: Path | str,
    doc_meta_bundle_path: Path | str,
    analysis_bundle_path: Path | str,
    output_dir: Path | str,
    git_provenance: dict[str, str | bool | None] | None = None,
    run_id: str | None = None,
    route_input_id: str | None = None,
    projection_input_refs: Sequence[Mapping[str, str]] | None = None,
    projection_doc_id: str | None = None,
    projection_file_hash: str | None = None,
    route_executor: ProjectedSourceRouteExecutor,
) -> ProjectedSourceRouteStageResult:
    """Build canonical route-stage artifacts from selected projected sources."""

    block_manifest = load_json(Path(block_manifest_path).resolve())
    doc_meta_bundle = load_json(Path(doc_meta_bundle_path).resolve())
    analysis_bundle = load_json(Path(analysis_bundle_path).resolve())

    if not isinstance(block_manifest, dict):
        raise ValueError("block_manifest must be a JSON object")
    if not isinstance(doc_meta_bundle, dict):
        raise ValueError("doc_meta_bundle must be a JSON object")
    if not isinstance(analysis_bundle, dict):
        raise ValueError("analysis_bundle must be a JSON object")

    if not isinstance(semantic_module_id, str) or not semantic_module_id.strip():
        raise ValueError("semantic_module_id must be a non-empty string")
    semantic_module_id = semantic_module_id.strip()

    manifest_blocks_by_id = blocks_by_id(block_manifest)

    def _resolve_document_anchor(source: ProjectedSource) -> tuple:
        return projected_source_document_anchor(
            source,
            blocks_by_id=manifest_blocks_by_id,
        )

    document_ordered_sources = sort_projected_sources_by_document_position(
        projected_sources,
        resolve_document_anchor=_resolve_document_anchor,
    )

    resolved_route_input_id = route_input_id or f"projected_route_{semantic_module_id}"
    step_result = run_from_projected_sources(
        projected_sources=document_ordered_sources,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
        expected_semantic_module_id=semantic_module_id,
        route_executor=route_executor,
        route_input_id=resolved_route_input_id,
        projection_input_refs=projection_input_refs,
        projection_doc_id=projection_doc_id,
        projection_file_hash=projection_file_hash,
    )
    route_artifacts = step_result.route_artifacts
    doc_id = step_result.doc_id

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    routed_bundle_paths: dict[str, Path] = {}
    for route, filename in ROUTED_UNITS_ROUTE_FILENAMES.items():
        path = out_dir / filename
        save_json(path, route_artifacts["routed_bundles"][route])
        routed_bundle_paths[route] = path

    routing_manifest_path = out_dir / ROUTING_MANIFEST_FILENAME
    save_json(routing_manifest_path, route_artifacts["routing_manifest"])

    resolved_run_id = run_id or resolve_projected_source_route_run_id()
    run_summary_path = out_dir / "run_summary.json"
    summary = build_projected_source_route_run_summary(
        run_id=resolved_run_id,
        doc_id=doc_id,
        semantic_module_id=semantic_module_id,
        block_manifest_path=Path(block_manifest_path).resolve(),
        doc_meta_bundle_path=Path(doc_meta_bundle_path).resolve(),
        analysis_bundle_path=Path(analysis_bundle_path).resolve(),
        routed_bundle_paths=routed_bundle_paths,
        routing_manifest_path=routing_manifest_path,
        route_counts=route_artifacts["route_counts"],
        selected_projected_source_count=len(projected_sources),
        projection_input_refs=projection_input_refs,
        git_provenance=git_provenance,
    )
    save_json(run_summary_path, summary)

    route_stage_result = ProjectedSourceRouteStageResult(
        output_dir=out_dir,
        run_id=resolved_run_id,
        doc_id=doc_id,
        semantic_module_id=semantic_module_id,
        route_counts=route_artifacts["route_counts"],
        routed_bundle_paths=routed_bundle_paths,
        routing_manifest_path=routing_manifest_path,
        run_summary_path=run_summary_path,
    )
    validate_route_stage_semantic_module_identity(
        requested_semantic_module_id=semantic_module_id,
        route_stage_result=route_stage_result,
    )
    return route_stage_result


__all__ = [
    "PersistedProjectionRouteStageOutcome",
    "ProjectedSourceRouteStageInvocation",
    "ProjectedSourceRouteStageResult",
    "load_persisted_projection_bundles",
    "resolve_projected_source_route_run_id",
    "resolve_projected_source_route_stage_paths",
    "run_projected_source_route_from_projection_bundles",
    "run_projected_source_route_stage",
    "validate_route_stage_semantic_module_identity",
]
