"""Neutral in-memory coverage resolution from Route projection provenance."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from operations.evidence_source_preparation.stage import (
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
)


@dataclass(frozen=True, slots=True)
class ProjectedCoverageResolution:
    """Resolved contributor coverage bundle paths keyed by filter_job_id."""

    paths_by_filter_job_id: dict[str, Path]
    ordered_filter_job_ids: tuple[str, ...]


def _coverage_path_index(
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference],
) -> dict[str, Path]:
    coverage_by_filter_job_id: dict[str, Path] = {}
    for ref in filter_job_coverage_refs:
        filter_job_id = ref.filter_job_id.strip()
        if not filter_job_id:
            raise ValueError("filter_job_coverage_refs[].filter_job_id must be non-empty")
        coverage_path = Path(ref.coverage_bundle_path).resolve()
        existing = coverage_by_filter_job_id.get(filter_job_id)
        if existing is not None and existing != coverage_path:
            raise ValueError(
                "ambiguous coverage_bundle_path for filter_job_id "
                f"{filter_job_id!r}: {existing} != {coverage_path}"
            )
        coverage_by_filter_job_id[filter_job_id] = coverage_path
    return coverage_by_filter_job_id


def _ordered_unique_filter_job_ids(
    projection_input_refs: Sequence[ProjectionInputRefRecord],
) -> tuple[str, ...]:
    if not projection_input_refs:
        raise ValueError(
            "projection_input_refs must be non-empty to resolve coverage_bundle_path"
        )

    seen_filter_job_ids: set[str] = set()
    ordered_filter_job_ids: list[str] = []
    for ref in projection_input_refs:
        filter_job_id = ref.filter_job_id.strip()
        if not filter_job_id:
            raise ValueError("projection_input_refs[].filter_job_id must be non-empty")
        if filter_job_id in seen_filter_job_ids:
            continue
        seen_filter_job_ids.add(filter_job_id)
        ordered_filter_job_ids.append(filter_job_id)
    return tuple(ordered_filter_job_ids)


def resolve_projected_coverage_bundles_by_filter_job_id(
    *,
    projection_input_refs: Sequence[ProjectionInputRefRecord],
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference],
) -> ProjectedCoverageResolution:
    """Resolve all contributing coverage bundle paths from Route projection provenance."""

    coverage_by_filter_job_id = _coverage_path_index(filter_job_coverage_refs)
    ordered_filter_job_ids = _ordered_unique_filter_job_ids(projection_input_refs)

    paths_by_filter_job_id: dict[str, Path] = {}
    missing_filter_job_ids: list[str] = []

    for filter_job_id in ordered_filter_job_ids:
        coverage_path = coverage_by_filter_job_id.get(filter_job_id)
        if coverage_path is None:
            missing_filter_job_ids.append(filter_job_id)
            continue
        paths_by_filter_job_id[filter_job_id] = coverage_path

    if missing_filter_job_ids:
        raise ValueError(
            "missing coverage_bundle_path for filter_job_id(s): "
            + ", ".join(sorted(missing_filter_job_ids))
        )
    if not paths_by_filter_job_id:
        raise ValueError(
            "no coverage_bundle_path resolved from projection_input_refs filter_job_id values"
        )

    return ProjectedCoverageResolution(
        paths_by_filter_job_id=paths_by_filter_job_id,
        ordered_filter_job_ids=ordered_filter_job_ids,
    )


def resolve_unique_coverage_bundle_path(
    *,
    projection_input_refs: Sequence[ProjectionInputRefRecord],
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference],
) -> Path:
    """Resolve exactly one coverage bundle path from Route projection provenance."""

    resolution = resolve_projected_coverage_bundles_by_filter_job_id(
        projection_input_refs=projection_input_refs,
        filter_job_coverage_refs=filter_job_coverage_refs,
    )
    distinct_paths = tuple(
        dict.fromkeys(
            resolution.paths_by_filter_job_id[job_id]
            for job_id in resolution.ordered_filter_job_ids
        ).keys()
    )
    if len(distinct_paths) > 1:
        raise ValueError(
            "multiple distinct coverage_bundle_path values resolved from "
            "projection_input_refs; expected exactly one unique coverage source"
        )
    return distinct_paths[0]


def is_projected_multi_source_fan_in(
    *,
    aggregate_bundle: Mapping[str, object],
    projection_input_refs: Sequence[ProjectionInputRefRecord],
    distinct_coverage_count: int,
) -> bool:
    """Return True when aggregate prepare must use projected multi-source semantics."""

    if distinct_coverage_count > 1:
        return True
    if not str(aggregate_bundle.get("zone_key") or "").strip():
        return True
    unique_filter_jobs = {
        ref.filter_job_id.strip()
        for ref in projection_input_refs
        if ref.filter_job_id.strip()
    }
    return len(unique_filter_jobs) > 1


def load_projection_input_refs_from_routing_manifest(
    routing_manifest: Mapping[str, object],
) -> tuple[ProjectionInputRefRecord, ...]:
    """Load formal projection input refs from one Route routing manifest."""

    source_refs = routing_manifest.get("source_refs")
    if not isinstance(source_refs, dict):
        raise ValueError("routing_manifest.source_refs must be an object")
    raw_refs = source_refs.get("projection_input_refs")
    if not isinstance(raw_refs, list) or not raw_refs:
        raise ValueError(
            "routing_manifest.source_refs.projection_input_refs must be a non-empty list"
        )

    projection_input_refs: list[ProjectionInputRefRecord] = []
    for index, raw_ref in enumerate(raw_refs):
        if not isinstance(raw_ref, dict):
            raise ValueError(
                "routing_manifest.source_refs.projection_input_refs["
                f"{index}] must be an object"
            )
        filter_job_id = str(raw_ref.get("filter_job_id") or "").strip()
        zone_key = str(raw_ref.get("zone_key") or "").strip()
        bundle_id = str(
            raw_ref.get("filter_output_projection_bundle_id") or ""
        ).strip()
        if not filter_job_id or not zone_key or not bundle_id:
            raise ValueError(
                "routing_manifest.source_refs.projection_input_refs["
                f"{index}] requires filter_job_id, zone_key, and "
                "filter_output_projection_bundle_id"
            )
        projection_input_refs.append(
            ProjectionInputRefRecord(
                filter_job_id=filter_job_id,
                zone_key=zone_key,
                filter_output_projection_bundle_id=bundle_id,
            )
        )
    return tuple(projection_input_refs)


__all__ = [
    "ProjectedCoverageResolution",
    "is_projected_multi_source_fan_in",
    "load_projection_input_refs_from_routing_manifest",
    "resolve_projected_coverage_bundles_by_filter_job_id",
    "resolve_unique_coverage_bundle_path",
]
