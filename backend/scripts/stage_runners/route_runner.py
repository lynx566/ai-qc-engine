from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)
from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.doc_meta import DOC_META_BUNDLE_FILENAME
from artifacts.filter_output_projection_bundle import (
    FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
)
from artifacts.prepare_analysis import ANALYSIS_BUNDLE_FILENAME
from runtime.projected_source_route_stage import (
    ProjectedSourceRouteStageInvocation,
    run_projected_source_route_from_projection_bundles,
)
from runtime.run_ids import utc_run_stamp
from runtime.run_layout import ROUTE_RUN_DIR_LAYOUT, allocate_session_dir
from runtime.run_provenance import snapshot_git_provenance_before_run
from scripts.stage_runners.common import ensure_project_on_path, resolve_artifact_file


def _ensure_project_on_path() -> None:
    ensure_project_on_path()


def resolve_runner_semantic_module_id(
    *,
    semantic_module_id: str | None,
    composition: DocumentConsistencyQcApplicationComposition,
) -> str:
    """Resolve one installed Route semantic module like the canonical Flow."""

    sequence = composition.route_semantic_module_sequence
    if semantic_module_id is None:
        if len(sequence) == 1:
            return sequence[0]
        raise SystemExit(
            "--semantic-module-id is required when multiple Route semantic modules "
            f"are installed: {list(sequence)!r}"
        )

    normalized = semantic_module_id.strip()
    if not normalized:
        raise SystemExit("--semantic-module-id must be a non-empty string")
    if not composition.is_route_semantic_module_enabled(normalized):
        known = sorted(composition.enabled_route_semantic_module_ids())
        raise SystemExit(
            f"unknown or disabled Route semantic module {normalized!r}; "
            f"installed={known!r}"
        )
    return normalized


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "route: canonical projected-source routing from persisted "
            "filter_output_projection_bundle.json artifact(s)."
        )
    )
    parser.add_argument(
        "--projection-bundle",
        action="append",
        required=True,
        help=(
            "Path to one filter_output_projection_bundle.json. "
            "Repeat for multi-source fan-in."
        ),
    )
    parser.add_argument(
        "--block-manifest",
        required=True,
        help="Path to block_manifest.json from prepare_analysis.",
    )
    parser.add_argument(
        "--doc-meta-bundle",
        required=True,
        help="Path to doc_meta_bundle.json from doc_meta.",
    )
    parser.add_argument(
        "--analysis-bundle",
        required=True,
        help="Path to analysis_bundle.json from prepare_analysis.",
    )
    parser.add_argument(
        "--semantic-module-id",
        default=None,
        help=(
            "Installed Route semantic module id. Defaults to the sole installed "
            "module when unambiguous."
        ),
    )
    parser.add_argument(
        "--route-key",
        default=None,
        help=(
            "Standalone layout segment for runs/route/<run_id>/doc_<doc_id>/<route-key>/. "
            "Required unless --output-dir is provided."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory override for route artifacts.",
    )
    args = parser.parse_args(argv)
    if args.output_dir is None and not args.route_key:
        parser.error("--route-key is required unless --output-dir is provided")
    return args


def main(argv: list[str] | None = None) -> None:
    _ensure_project_on_path()
    args = parse_args(argv)
    composition = build_installed_document_consistency_qc_application_composition()
    semantic_module_id = resolve_runner_semantic_module_id(
        semantic_module_id=args.semantic_module_id,
        composition=composition,
    )

    projection_bundle_paths = [
        resolve_artifact_file(
            path,
            filename=FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
            flag_name="--projection-bundle",
        )
        for path in args.projection_bundle
    ]
    block_manifest_path = resolve_artifact_file(
        args.block_manifest,
        filename=BLOCK_MANIFEST_FILENAME,
        flag_name="--block-manifest",
    )
    doc_meta_bundle_path = resolve_artifact_file(
        args.doc_meta_bundle,
        filename=DOC_META_BUNDLE_FILENAME,
        flag_name="--doc-meta-bundle",
    )
    analysis_bundle_path = resolve_artifact_file(
        args.analysis_bundle,
        filename=ANALYSIS_BUNDLE_FILENAME,
        flag_name="--analysis-bundle",
    )

    stamp = utc_run_stamp()
    git_prov = snapshot_git_provenance_before_run(root=PROJECT_ROOT)
    session_dir = allocate_session_dir(
        PROJECT_ROOT / "runs",
        stage="route",
        context=semantic_module_id,
        stamp=stamp,
        run_dir_layout=ROUTE_RUN_DIR_LAYOUT,
    )
    invocation = ProjectedSourceRouteStageInvocation(
        stamp=stamp,
        session_dir=session_dir,
        runs_root=PROJECT_ROOT / "runs",
        git_root=PROJECT_ROOT,
        custom_output_dir=Path(args.output_dir) if args.output_dir else None,
    )

    print(f"semantic_module_id={semantic_module_id}")
    print(f"projection_bundle_count={len(projection_bundle_paths)}")
    print(f"block_manifest: {block_manifest_path.as_posix()}")
    print(f"doc_meta_bundle: {doc_meta_bundle_path.as_posix()}")
    print(f"analysis_bundle: {analysis_bundle_path.as_posix()}")

    outcome = run_projected_source_route_from_projection_bundles(
        projection_bundle_paths=projection_bundle_paths,
        semantic_module_id=semantic_module_id,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        route_executor=composition.projected_source_route_executor,
        git_provenance=git_prov,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        route_key=(args.route_key or "").strip() or None,
        invocation=invocation,
    )
    if outcome.route_result is None:
        raise SystemExit(
            "no projected sources selected for "
            f"semantic_module_id={semantic_module_id!r}"
        )

    result = outcome.route_result
    print(f"selected_projected_source_count={outcome.selected_projected_source_count}")
    print(f"run_id: {result.run_id}")
    print(f"output_dir: {result.output_dir.as_posix()}")
    print(f"routing_manifest: {result.routing_manifest_path.as_posix()}")
    print(
        "routed_units_aggregate: "
        f"{result.routed_bundle_paths['aggregate'].as_posix()}"
    )
    print(f"run_summary: {result.run_summary_path.as_posix()}")


if __name__ == "__main__":
    main()
