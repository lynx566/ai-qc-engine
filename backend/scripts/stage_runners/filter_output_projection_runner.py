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
from artifacts.zone_match_bundle import ZONE_MATCH_BUNDLE_FILENAME
from artifacts.prepare_analysis import ANALYSIS_BUNDLE_FILENAME
from llm.provider_cli import (
    build_llm_provider_from_cli_args,
    register_llm_cli_arguments,
    validate_configured_llm_cli_args,
)
from operations.filter_output_projection.contracts import (
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from runtime.filter_output_projection_stage import (
    FilterOutputProjectionStageInvocation,
    resolve_filter_output_projection_stage_paths,
    run_filter_output_projection_stage,
)
from runtime.run_ids import utc_run_stamp
from runtime.run_layout import (
    FILTER_OUTPUT_PROJECTION_RUN_DIR_LAYOUT,
    allocate_session_dir,
)
from runtime.run_provenance import snapshot_git_provenance_before_run
from scripts.stage_runners.common import (
    ensure_project_on_path,
    resolve_artifact_file,
)
from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)

_STANDALONE_LLM_MODES = ("mock", "api")
_OVERVIEW_SEMANTIC_DECOMPOSITION_STRATEGY_ID = "overview_semantic_decomposition"


def _ensure_project_on_path() -> None:
    ensure_project_on_path()


def resolve_runner_projection_job(
    *,
    filter_job_id: str,
    composition: DocumentConsistencyQcApplicationComposition,
) -> ResolvedFilterOutputProjectionJob:
    """Resolve one installed Filter-output projection job like the canonical Flow."""

    return composition.resolve_filter_output_projection_job(filter_job_id)


def build_runner_projection_runtime_dependencies(
    *,
    args: argparse.Namespace,
    resolved_job: ResolvedFilterOutputProjectionJob,
) -> FilterOutputProjectionRuntimeDependencies:
    """Construct dev-selected projection runtime dependencies for one standalone run."""

    if resolved_job.strategy_id != _OVERVIEW_SEMANTIC_DECOMPOSITION_STRATEGY_ID:
        return FilterOutputProjectionRuntimeDependencies(llm_provider=None)

    if args.llm == "mock":
        return FilterOutputProjectionRuntimeDependencies(
            llm_provider=OverviewStandaloneMockProvider(),
        )
    if args.llm == "api":
        provider = build_llm_provider_from_cli_args(args)
        if provider is None:
            raise ValueError("provider is required for overview API projection")
        return FilterOutputProjectionRuntimeDependencies(llm_provider=provider)

    raise ValueError(f"unsupported --llm mode {args.llm!r}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "filter_output_projection: semantic projection from an existing "
            "zone_match_bundle.json (output of the filter step)."
        )
    )
    parser.add_argument(
        "--zone-match-bundle",
        required=True,
        help="Path to one zone_match_bundle.json produced by the filter step.",
    )
    parser.add_argument(
        "--analysis-bundle",
        required=True,
        help="Path to one analysis_bundle.json produced by the prepare_analysis step.",
    )
    parser.add_argument(
        "--filter-job-id",
        required=True,
        help="Installed filter job id whose projection binding should run.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Optional output directory (default: "
            "runs/filter_output_projection/<run_id>/doc_<doc_id>/<filter_job_id>/)"
        ),
    )
    register_llm_cli_arguments(
        parser,
        llm_required=True,
        allowed_modes=_STANDALONE_LLM_MODES,
    )
    args = parser.parse_args(argv)
    validate_configured_llm_cli_args(args)
    return args


def main(argv: list[str] | None = None) -> None:
    _ensure_project_on_path()
    args = parse_args(argv)
    composition = build_installed_document_consistency_qc_application_composition()
    resolved_job = resolve_runner_projection_job(
        filter_job_id=args.filter_job_id,
        composition=composition,
    )
    zone_match_bundle_path = resolve_artifact_file(
        args.zone_match_bundle,
        filename=ZONE_MATCH_BUNDLE_FILENAME,
        flag_name="--zone-match-bundle",
    )
    analysis_bundle_path = resolve_artifact_file(
        args.analysis_bundle,
        filename=ANALYSIS_BUNDLE_FILENAME,
        flag_name="--analysis-bundle",
    )
    runtime_dependencies = build_runner_projection_runtime_dependencies(
        args=args,
        resolved_job=resolved_job,
    )
    facade = composition.filter_output_projection_facade_builder(
        job=resolved_job,
        runtime_dependencies=runtime_dependencies,
    )

    stamp = utc_run_stamp()
    git_prov = snapshot_git_provenance_before_run(root=PROJECT_ROOT)
    session_dir = allocate_session_dir(
        PROJECT_ROOT / "runs",
        stage="filter_output_projection",
        context=resolved_job.filter_job_id,
        stamp=stamp,
        run_dir_layout=FILTER_OUTPUT_PROJECTION_RUN_DIR_LAYOUT,
    )
    invocation = FilterOutputProjectionStageInvocation(
        stamp=stamp,
        session_dir=session_dir,
        runs_root=PROJECT_ROOT / "runs",
        git_root=PROJECT_ROOT,
        custom_output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    output_dir, run_id = resolve_filter_output_projection_stage_paths(
        zone_match_bundle_path=zone_match_bundle_path,
        filter_job_id=resolved_job.filter_job_id,
        invocation=invocation,
    )

    print(f"filter_job_id={resolved_job.filter_job_id}")
    print(f"strategy_id={resolved_job.strategy_id}")
    print(f"zone_match_bundle: {zone_match_bundle_path.as_posix()}")
    print(f"analysis_bundle: {analysis_bundle_path.as_posix()}")

    result = run_filter_output_projection_stage(
        filter_job_id=resolved_job.filter_job_id,
        resolved_job=resolved_job,
        zone_match_bundle_path=zone_match_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        facade=facade,
        output_dir=output_dir,
        git_provenance=git_prov,
        run_id=run_id,
    )

    print(f"run_id: {result.run_id}")
    print(f"output_dir: {result.output_dir.as_posix()}")
    print(f"projection_bundle: {result.projection_bundle_path.as_posix()}")
    print(f"projected_source_count: {len(result.step_result.projected_sources)}")
    print(f"semantic_outcome_count: {len(result.step_result.semantic_outcomes)}")
    print(f"run_summary: {result.run_summary_path.as_posix()}")


if __name__ == "__main__":
    main()
