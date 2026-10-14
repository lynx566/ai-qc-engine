"""Test helpers for persisting route artifacts without legacy Route runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from artifacts.routing.route_bundles import build_route_stage_artifacts
from artifacts.routing.schema import (
    ROUTED_UNITS_ROUTE_FILENAMES,
    ROUTING_MANIFEST_FILENAME,
    validate_route_upstream_identity,
)
from plugins.clinical_trial_doc.routing import (
    route_prepare_units_from_projected_sources,
)
from runtime.io import load_json, save_json
from tests.route_test_fixtures import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_manifest,
    _block,
    _block_manifest,
    _coverage_bundle,
    _coverage_row,
    _minimal_doc_meta,
    _projected_sources_from_coverage_bundle,
    _route_input_envelope_from_coverage_bundle,
    _table_block,
)


@dataclass(frozen=True)
class PersistedRouteArtifacts:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    route_counts: dict[str, int]
    routed_bundle_paths: dict[str, Path]
    routing_manifest_path: Path


def _relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def write_upstream_route_fixtures(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    heading_agg = ["12 临床安全性", "12.3 不良事件概述"]
    heading_table = ["12 临床安全性", "12.4 表格"]
    heading_case = ["12 临床安全性", "12.5 个例"]
    coverage = _coverage_bundle(
        _coverage_row("C0100", 100, heading_path=heading_agg),
        _coverage_row(
            "T0001",
            200,
            block_kind="table",
            heading_path=heading_table,
        ),
        _coverage_row("C0200", 300, heading_path=heading_case),
        _coverage_row("C0300", 400, block_kind="figure"),
    )
    manifest = _block_manifest(
        blocks=[
            _block("C0100", 100, heading_path=heading_agg, analysis_text="agg text"),
            _block("C0200", 300, heading_path=heading_case, analysis_text="case text"),
            _block("C0300", 400, analysis_text="unknown figure"),
        ],
        table_blocks=[
            _table_block("T0001", 200, heading_path=heading_table),
        ],
    )
    doc_meta_bundle = _minimal_doc_meta()
    analysis_bundle = _analysis_bundle_for_manifest(manifest)
    paths = {
        "coverage": tmp_path / "coverage_bundle.json",
        "block_manifest": tmp_path / "block_manifest.json",
        "doc_meta_bundle": tmp_path / "doc_meta_bundle.json",
        "analysis": tmp_path / "analysis_bundle.json",
    }
    save_json(paths["coverage"], coverage)
    save_json(paths["block_manifest"], manifest)
    save_json(paths["doc_meta_bundle"], doc_meta_bundle)
    save_json(paths["analysis"], analysis_bundle)
    return paths


def write_prepare_upstream_run_tree(
    project_root: Path,
    *,
    include_block_manifest: bool = True,
    include_doc_meta_summary: bool = True,
    coverage_doc_id: str | None = None,
    analysis_run_id: str = "analysis_test",
    filter_run_id: str = "filter_test",
    doc_meta_run_id: str = "doc_meta_test",
) -> dict[str, Path]:
    """Create a minimal filter/analysis/doc-meta run tree for prepare harness tests."""

    source_paths = write_upstream_route_fixtures(project_root / "fixture_inputs")
    coverage = load_json(source_paths["coverage"])
    block_manifest = load_json(source_paths["block_manifest"])
    doc_meta_bundle = load_json(source_paths["doc_meta_bundle"])
    analysis_bundle = load_json(source_paths["analysis"])
    if coverage_doc_id is not None:
        coverage["doc_id"] = coverage_doc_id

    doc_id = str(analysis_bundle["doc_id"])
    zone_key = str(coverage["zone_key"])
    runs_root = project_root / "runs"
    analysis_dir = runs_root / "prepare_analysis" / analysis_run_id / doc_id
    filter_dir = runs_root / "filter" / filter_run_id / zone_key / doc_id
    doc_meta_dir = runs_root / "doc_meta" / doc_meta_run_id / doc_id
    for directory in (analysis_dir, filter_dir, doc_meta_dir):
        directory.mkdir(parents=True, exist_ok=True)

    paths = {
        "coverage": filter_dir / "coverage_bundle.json",
        "block_manifest": analysis_dir / "block_manifest.json",
        "doc_meta_bundle": doc_meta_dir / "doc_meta_bundle.json",
        "analysis": analysis_dir / "analysis_bundle.json",
        "filter_run_dir": filter_dir,
        "analysis_run_dir": analysis_dir,
        "doc_meta_dir": doc_meta_dir,
    }
    save_json(paths["coverage"], coverage)
    save_json(paths["analysis"], analysis_bundle)
    save_json(paths["doc_meta_bundle"], doc_meta_bundle)
    if include_block_manifest:
        save_json(paths["block_manifest"], block_manifest)

    save_json(
        filter_dir / "run_summary.json",
        {
            "doc_id": doc_id,
            "inputs": {
                "input_analysis_bundle": _relative_posix(paths["analysis"], project_root),
            },
            "outputs": {"coverage_bundle": "coverage_bundle.json"},
        },
    )
    if include_doc_meta_summary:
        save_json(
            doc_meta_dir / "run_summary.json",
            {
                "doc_id": doc_id,
                "inputs": {
                    "analysis_bundle": _relative_posix(paths["analysis"], project_root),
                },
                "outputs": {"doc_meta_bundle": "doc_meta_bundle.json"},
            },
        )
    return paths


def persist_route_artifacts_from_coverage(
    *,
    coverage_bundle_path: Path | str,
    block_manifest_path: Path | str,
    doc_meta_bundle_path: Path | str,
    analysis_bundle_path: Path | str,
    output_dir: Path | str,
    run_id: str = "route_test",
) -> PersistedRouteArtifacts:
    """Persist route-stage artifacts from coverage rows (test / harness helper only)."""

    resolved_coverage = Path(coverage_bundle_path).resolve()
    resolved_block_manifest = Path(block_manifest_path).resolve()
    resolved_doc_meta_bundle_path = Path(doc_meta_bundle_path).resolve()
    resolved_analysis = Path(analysis_bundle_path).resolve()

    coverage_bundle = load_json(resolved_coverage)
    block_manifest = load_json(resolved_block_manifest)
    doc_meta_bundle = load_json(resolved_doc_meta_bundle_path)
    analysis_bundle = load_json(resolved_analysis)
    if not analysis_bundle.get("content_blocks") and not analysis_bundle.get("table_blocks"):
        analysis_bundle = _analysis_bundle_for_manifest(block_manifest)

    doc_id, zone_key = validate_route_upstream_identity(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
    )
    routed = route_prepare_units_from_projected_sources(
        projected_sources=_projected_sources_from_coverage_bundle(coverage_bundle),
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
        expected_semantic_module_id="clinical_safety",
        doc_id=str(coverage_bundle.get("doc_id") or block_manifest.get("doc_id") or ""),
        file_hash=str(
            coverage_bundle.get("file_hash")
            or block_manifest.get("file_hash")
            or LINEAGE_FILE_HASH
        ),
    )
    route_artifacts = build_route_stage_artifacts(
        routed=routed,
        route_input_envelope=_route_input_envelope_from_coverage_bundle(coverage_bundle),
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
    )

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    routed_bundle_paths: dict[str, Path] = {}
    for route, filename in ROUTED_UNITS_ROUTE_FILENAMES.items():
        path = out_dir / filename
        save_json(path, route_artifacts["routed_bundles"][route])
        routed_bundle_paths[route] = path

    routing_manifest_path = out_dir / ROUTING_MANIFEST_FILENAME
    save_json(routing_manifest_path, route_artifacts["routing_manifest"])

    return PersistedRouteArtifacts(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=doc_id,
        zone_key=zone_key,
        route_counts=route_artifacts["route_counts"],
        routed_bundle_paths=routed_bundle_paths,
        routing_manifest_path=routing_manifest_path,
    )


def persist_route_artifacts_from_fixture_paths(
    paths: dict[str, Path],
    *,
    output_dir: Path,
    run_id: str = "route_test",
) -> PersistedRouteArtifacts:
    return persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=output_dir,
        run_id=run_id,
    )
