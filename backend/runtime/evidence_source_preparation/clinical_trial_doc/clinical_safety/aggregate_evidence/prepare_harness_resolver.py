"""Manifest-driven input resolution for aggregate-evidence prepare phase harness runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operations.evidence_source_preparation.coverage_resolution import (
    load_projection_input_refs_from_routing_manifest,
    resolve_projected_coverage_bundles_by_filter_job_id,
)
from operations.evidence_source_preparation.stage import (
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    ProjectedCoverageByFilterJob,
)
from runtime.io import load_json
from runtime.prepare_upstream_paths import (
    COVERAGE_BUNDLE_FILENAME,
    discover_doc_meta_dir,
    resolve_prepare_upstream_inputs_from_dirs,
)


@dataclass(frozen=True, slots=True)
class PrepareHarnessResolvedInputs:
    """Resolved prepare harness inputs before ``run_prepare``."""

    coverage_bundle_path: Path | None
    block_manifest_path: Path
    doc_meta_bundle_path: Path
    analysis_bundle_path: Path
    private_audit_bundle_path: Path | None
    doc_id: str
    projection_input_refs: tuple[ProjectionInputRefRecord, ...]
    projected_coverage_by_filter_job: ProjectedCoverageByFilterJob | None
    filter_job_coverage_refs: tuple[FilterJobCoverageReference, ...] = ()


def _existing_dir(value: str | Path, *, flag: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir():
        raise ValueError(f"{flag} must point to an existing directory: {path}")
    return path


def _coverage_bundle_path_in_filter_dir(filter_dir: Path) -> Path:
    summary_path = filter_dir / "run_summary.json"
    if summary_path.is_file():
        summary = load_json(summary_path)
        outputs = summary.get("outputs") or {}
        coverage_name = outputs.get("coverage_bundle", COVERAGE_BUNDLE_FILENAME)
        if isinstance(coverage_name, str) and coverage_name.strip():
            candidate = (filter_dir / coverage_name).resolve()
            if candidate.is_file():
                return candidate
    direct = (filter_dir / COVERAGE_BUNDLE_FILENAME).resolve()
    if not direct.is_file():
        raise ValueError(
            f"filter run directory missing coverage bundle: {filter_dir / COVERAGE_BUNDLE_FILENAME}"
        )
    return direct


def _projection_input_refs_from_manifest(
    routing_manifest: Mapping[str, Any],
) -> tuple[ProjectionInputRefRecord, ...]:
    source_refs = routing_manifest.get("source_refs")
    if not isinstance(source_refs, dict):
        return ()
    raw_refs = source_refs.get("projection_input_refs")
    if not isinstance(raw_refs, list) or not raw_refs:
        return ()
    return load_projection_input_refs_from_routing_manifest(routing_manifest)


def _filter_job_id_for_filter_dir(
    filter_dir: Path,
    *,
    projection_input_refs: Sequence[ProjectionInputRefRecord],
) -> str:
    coverage_path = _coverage_bundle_path_in_filter_dir(filter_dir)
    coverage_bundle = load_json(coverage_path)
    if not isinstance(coverage_bundle, dict):
        raise ValueError(f"coverage_bundle must be a JSON object: {coverage_path}")
    zone_key = str(coverage_bundle.get("zone_key") or "").strip()
    if not zone_key:
        raise ValueError(
            f"filter run directory coverage_bundle missing zone_key: {coverage_path}"
        )
    matches = [ref for ref in projection_input_refs if ref.zone_key == zone_key]
    if len(matches) != 1:
        raise ValueError(
            "filter run directory "
            f"{filter_dir.as_posix()} zone_key {zone_key!r} must match exactly one "
            "routing_manifest.source_refs.projection_input_ref"
        )
    return matches[0].filter_job_id


def _resolve_shared_upstream_from_filter_dir(
    *,
    filter_dir: Path,
    doc_meta_dir: Path | None,
    project_root: Path,
) -> dict[str, Any]:
    metadata_dir = (
        _existing_dir(doc_meta_dir, flag="--doc-meta-dir")
        if doc_meta_dir is not None
        else discover_doc_meta_dir(filter_run_dir=filter_dir, project_root=project_root)
    )
    return resolve_prepare_upstream_inputs_from_dirs(
        filter_run_dir=filter_dir,
        doc_meta_dir=metadata_dir,
        project_root=project_root,
    )


def _resolve_fan_in_shared_upstream_from_contributor_dirs(
    *,
    dir_by_filter_job_id: Mapping[str, Path],
    doc_meta_dir: Path | None,
    project_root: Path,
) -> tuple[dict[str, Any], str | None]:
    """Resolve shared upstream artifacts and require contributor dirs to agree."""

    if not dir_by_filter_job_id:
        raise ValueError("dir_by_filter_job_id must be non-empty")

    discovery_message: str | None = None
    resolved: dict[str, Any] | None = None
    shared_keys = (
        "block_manifest_path",
        "doc_meta_bundle_path",
        "analysis_bundle_path",
        "doc_id",
    )

    for filter_job_id in sorted(dir_by_filter_job_id):
        filter_dir = dir_by_filter_job_id[filter_job_id]
        metadata_dir = (
            _existing_dir(doc_meta_dir, flag="--doc-meta-dir")
            if doc_meta_dir is not None
            else discover_doc_meta_dir(filter_run_dir=filter_dir, project_root=project_root)
        )
        if doc_meta_dir is None and discovery_message is None:
            discovery_message = f"auto-discovered doc_meta:    {metadata_dir}"
        candidate = _resolve_shared_upstream_from_filter_dir(
            filter_dir=filter_dir,
            doc_meta_dir=metadata_dir,
            project_root=project_root,
        )
        if resolved is None:
            resolved = candidate
            continue
        for key in shared_keys:
            if str(resolved[key]) != str(candidate[key]):
                raise ValueError(
                    "projected fan-in contributor filter run directories disagree on "
                    f"{key!r} for filter_job_id={filter_job_id!r}: "
                    f"{resolved[key]!r} != {candidate[key]!r}"
                )

    if resolved is None:
        raise ValueError("failed to resolve shared upstream from contributor filter dirs")
    return resolved, discovery_message


def resolve_prepare_harness_inputs(
    *,
    routing_manifest: Mapping[str, Any],
    filter_run_dirs: Sequence[str | Path] | None,
    coverage_bundle: str | None,
    block_manifest: str | None,
    doc_meta_bundle_path: str | None,
    analysis_bundle: str | None,
    doc_meta_dir: str | None,
    project_root: Path,
) -> tuple[PrepareHarnessResolvedInputs, str | None]:
    """
    Resolve prepare harness inputs from routing manifest and explicit CLI paths.

    Returns ``(resolved, discovery_message)`` where *discovery_message* is set when
    doc_meta was auto-discovered from a filter run directory.
    """
    projection_input_refs = _projection_input_refs_from_manifest(routing_manifest)
    is_fan_in = len(projection_input_refs) > 1

    explicit_values = (
        coverage_bundle,
        block_manifest,
        doc_meta_bundle_path,
        analysis_bundle,
    )
    explicit_count = sum(value is not None for value in explicit_values)
    has_filter_dirs = bool(filter_run_dirs)

    if is_fan_in and explicit_count:
        raise ValueError(
            "projected fan-in prepare requires --filter-run-dir for each manifest "
            "contributor; explicit upstream file flags are not supported for fan-in"
        )
    if is_fan_in and not has_filter_dirs:
        raise ValueError(
            "projected fan-in prepare requires one --filter-run-dir per manifest "
            "contributor referenced in routing_manifest.source_refs.projection_input_refs"
        )

    if not has_filter_dirs:
        if explicit_count != len(explicit_values):
            raise ValueError("explicit input mode requires all four upstream artifact paths")
        from artifacts.routing.schema import validate_route_upstream_identity
        from runtime.prepare_upstream_paths import resolve_private_audit_bundle_path

        coverage_path = Path(coverage_bundle or "").resolve()
        block_path = Path(block_manifest or "").resolve()
        doc_meta_path = Path(doc_meta_bundle_path or "").resolve()
        analysis_path = Path(analysis_bundle or "").resolve()
        for path, label in (
            (coverage_path, "--coverage-bundle"),
            (block_path, "--block-manifest"),
            (doc_meta_path, "--doc-meta-bundle"),
            (analysis_path, "--analysis-bundle"),
        ):
            if not path.is_file():
                raise ValueError(f"{label} must point to an existing file: {path}")
        doc_id, _ = validate_route_upstream_identity(
            coverage_bundle=load_json(coverage_path),
            block_manifest=load_json(block_path),
            doc_meta_bundle=load_json(doc_meta_path),
            analysis_bundle=load_json(analysis_path),
        )
        return (
            PrepareHarnessResolvedInputs(
                coverage_bundle_path=coverage_path,
                block_manifest_path=block_path,
                doc_meta_bundle_path=doc_meta_path,
                analysis_bundle_path=analysis_path,
                private_audit_bundle_path=resolve_private_audit_bundle_path(analysis_path),
                doc_id=doc_id,
                projection_input_refs=(),
                projected_coverage_by_filter_job=None,
            ),
            None,
        )

    normalized_filter_dirs = tuple(
        _existing_dir(path, flag="--filter-run-dir") for path in filter_run_dirs or ()
    )
    discovery_message: str | None = None

    if not is_fan_in:
        if len(normalized_filter_dirs) != 1:
            raise ValueError(
                "single-source prepare requires exactly one --filter-run-dir"
            )
        filter_dir = normalized_filter_dirs[0]
        metadata_dir = (
            _existing_dir(doc_meta_dir, flag="--doc-meta-dir")
            if doc_meta_dir is not None
            else discover_doc_meta_dir(filter_run_dir=filter_dir, project_root=project_root)
        )
        if doc_meta_dir is None:
            discovery_message = f"auto-discovered doc_meta:    {metadata_dir}"
        resolved = resolve_prepare_upstream_inputs_from_dirs(
            filter_run_dir=filter_dir,
            doc_meta_dir=metadata_dir,
            project_root=project_root,
        )
        return (
            PrepareHarnessResolvedInputs(
                coverage_bundle_path=Path(resolved["coverage_bundle_path"]),
                block_manifest_path=Path(resolved["block_manifest_path"]),
                doc_meta_bundle_path=Path(resolved["doc_meta_bundle_path"]),
                analysis_bundle_path=Path(resolved["analysis_bundle_path"]),
                private_audit_bundle_path=resolved.get("private_audit_bundle_path"),
                doc_id=str(resolved["doc_id"]),
                projection_input_refs=(),
                projected_coverage_by_filter_job=None,
            ),
            discovery_message,
        )

    expected_filter_job_ids = {
        ref.filter_job_id for ref in projection_input_refs
    }
    if len(normalized_filter_dirs) != len(expected_filter_job_ids):
        raise ValueError(
            "projected fan-in prepare requires exactly "
            f"{len(expected_filter_job_ids)} --filter-run-dir value(s) for manifest "
            f"contributors {sorted(expected_filter_job_ids)!r}; "
            f"got {len(normalized_filter_dirs)}"
        )

    dir_by_filter_job_id: dict[str, Path] = {}
    for filter_dir in normalized_filter_dirs:
        filter_job_id = _filter_job_id_for_filter_dir(
            filter_dir,
            projection_input_refs=projection_input_refs,
        )
        if filter_job_id in dir_by_filter_job_id:
            raise ValueError(
                "duplicate --filter-run-dir for filter_job_id "
                f"{filter_job_id!r}: "
                f"{dir_by_filter_job_id[filter_job_id].as_posix()} and "
                f"{filter_dir.as_posix()}"
            )
        dir_by_filter_job_id[filter_job_id] = filter_dir

    missing = sorted(expected_filter_job_ids - set(dir_by_filter_job_id))
    if missing:
        raise ValueError(
            "missing --filter-run-dir for manifest contributor filter_job_id(s): "
            + ", ".join(missing)
        )
    extra = sorted(set(dir_by_filter_job_id) - expected_filter_job_ids)
    if extra:
        raise ValueError(
            "unexpected --filter-run-dir filter_job_id(s) not listed in "
            f"routing_manifest.source_refs.projection_input_refs: "
            + ", ".join(extra)
        )

    filter_job_coverage_refs = tuple(
        FilterJobCoverageReference(
            filter_job_id=filter_job_id,
            coverage_bundle_path=_coverage_bundle_path_in_filter_dir(
                dir_by_filter_job_id[filter_job_id]
            ),
        )
        for filter_job_id in (ref.filter_job_id for ref in projection_input_refs)
    )
    coverage_resolution = resolve_projected_coverage_bundles_by_filter_job_id(
        projection_input_refs=projection_input_refs,
        filter_job_coverage_refs=filter_job_coverage_refs,
    )
    coverage_bundles_by_filter_job_id = {
        filter_job_id: load_json(path)
        for filter_job_id, path in coverage_resolution.paths_by_filter_job_id.items()
    }
    shared, discovery_message = _resolve_fan_in_shared_upstream_from_contributor_dirs(
        dir_by_filter_job_id=dir_by_filter_job_id,
        doc_meta_dir=(
            _existing_dir(doc_meta_dir, flag="--doc-meta-dir")
            if doc_meta_dir is not None
            else None
        ),
        project_root=project_root,
    )

    return (
        PrepareHarnessResolvedInputs(
            coverage_bundle_path=None,
            block_manifest_path=Path(shared["block_manifest_path"]),
            doc_meta_bundle_path=Path(shared["doc_meta_bundle_path"]),
            analysis_bundle_path=Path(shared["analysis_bundle_path"]),
            private_audit_bundle_path=shared.get("private_audit_bundle_path"),
            doc_id=str(shared["doc_id"]),
            projection_input_refs=projection_input_refs,
            projected_coverage_by_filter_job=ProjectedCoverageByFilterJob(
                bundles_by_filter_job_id=coverage_bundles_by_filter_job_id,
            ),
            filter_job_coverage_refs=filter_job_coverage_refs,
        ),
        discovery_message,
    )


__all__ = [
    "PrepareHarnessResolvedInputs",
    "resolve_prepare_harness_inputs",
]
