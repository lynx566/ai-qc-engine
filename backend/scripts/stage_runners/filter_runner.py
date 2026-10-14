from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application import (
    build_installed_document_consistency_qc_application_composition,
)
from operations.filter.variant_registry import resolve_filter_job_variant
from runtime.filter_stage import FilterStageInvocation, run_filter_stage
from runtime.run_ids import utc_run_stamp
from runtime.run_index import (
    build_filter_index_document,
    resolve_index_root,
    write_run_index,
)
from runtime.run_layout import (
    FILTER_RUN_DIR_LAYOUT,
    allocate_session_dir,
    build_stage_run_layout,
    posix_relative,
)
from runtime.run_provenance import snapshot_git_provenance_before_run
from scripts.stage_runners.common import (
    ANALYSIS_BUNDLE_FILENAME,
    ensure_project_on_path,
    resolve_artifact_dir,
    resolve_artifact_file,
)


def _ensure_project_on_path() -> None:
    ensure_project_on_path()


@dataclass(frozen=True)
class ResolvedFilterRunnerJob:
    filter_job_id: str
    profile: Any


def resolve_runner_filter_jobs(
    *,
    filter_job_ids: Sequence[str],
    language: str,
    filter_job_variants: Mapping[tuple[str, str], Any],
) -> tuple[ResolvedFilterRunnerJob, ...]:
    """Resolve installed Filter jobs the same way as the canonical Flow."""
    resolved: list[ResolvedFilterRunnerJob] = []
    for filter_job_id in filter_job_ids:
        profile = resolve_filter_job_variant(
            filter_job_id=filter_job_id,
            language=language,
            filter_job_variants=filter_job_variants,
        )
        resolved.append(
            ResolvedFilterRunnerJob(filter_job_id=filter_job_id, profile=profile)
        )
    return tuple(resolved)


def parse_args(
    *,
    filter_job_variants: Mapping[tuple[str, str], Any],
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="filter: target-zone extraction from analysis_bundle.json"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--analysis-bundle",
        type=str,
        help="Path to one analysis_bundle.json (output of the prepare_analysis step).",
    )
    input_group.add_argument(
        "--analysis-bundle-dir",
        type=str,
        help=(
            "Directory containing run subdirectories with analysis_bundle.json "
            "(output of the prepare_analysis step)."
        ),
    )
    parser.add_argument(
        "--filter-job-id",
        action="append",
        dest="filter_job_ids",
        metavar="ID",
        required=True,
        help=(
            "Installed filter job id (repeatable). Each id is an independent "
            "filter job under the same session timestamp. "
            "E.g. --filter-job-id ib_overview --filter-job-id ib_clinical_safety"
        ),
    )
    parser.add_argument(
        "--language",
        required=True,
        help="Installed localized variant language (e.g. zh).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Write local-only zone_match_bundle.debug.json with original_text when "
            "privacy_audit.json is available alongside the input analysis bundle"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "Optional output directory: exact folder for one profile and one "
            "bundle; with several bundles or profiles, each run uses "
            "<dir>/<leaf>/ or <dir>/<zone_key>/<leaf>/ "
            "(default: runs/filter/<timestamp>/<zone_key>/<doc_id>/)"
        ),
    )
    args = parser.parse_args()
    try:
        args.resolved_filter_jobs = resolve_runner_filter_jobs(
            filter_job_ids=args.filter_job_ids,
            language=args.language,
            filter_job_variants=filter_job_variants,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main() -> None:
    _ensure_project_on_path()
    composition = build_installed_document_consistency_qc_application_composition()
    args = parse_args(filter_job_variants=composition.filter_job_variants)
    git_prov = snapshot_git_provenance_before_run(root=PROJECT_ROOT)

    if args.analysis_bundle:
        bundle_paths = [
            resolve_artifact_file(
                args.analysis_bundle,
                filename=ANALYSIS_BUNDLE_FILENAME,
                flag_name="--analysis-bundle",
            )
        ]
    else:
        bundle_paths = resolve_artifact_dir(
            args.analysis_bundle_dir,
            filename=ANALYSIS_BUNDLE_FILENAME,
            flag_name="--analysis-bundle-dir",
        )

    resolved_jobs = args.resolved_filter_jobs
    profile_jobs = [(job.filter_job_id, job.profile) for job in resolved_jobs]
    multi_profile = len(profile_jobs) > 1
    first_layout_key = resolved_jobs[0].profile.zone_config_name

    print(f"filter_job_ids={[job.filter_job_id for job in resolved_jobs]}")
    print(f"language={args.language}")
    print(f"filter_jobs={len(profile_jobs)}")
    print(
        "loaded_filter_profiles="
        f"{[job.profile.zone_config_name for job in resolved_jobs]}"
    )

    stamp = utc_run_stamp()
    multi_bundle = len(bundle_paths) > 1
    session_dir = allocate_session_dir(
        PROJECT_ROOT / "runs",
        stage="filter",
        context=first_layout_key,
        stamp=stamp,
        run_dir_layout=FILTER_RUN_DIR_LAYOUT,
    )
    index_documents = []
    index_root = resolve_index_root(
        session_dir=session_dir,
        custom_output_dir=args.output_dir,
    )

    invocation = FilterStageInvocation(
        stamp=stamp,
        session_dir=session_dir,
        runs_root=PROJECT_ROOT / "runs",
        git_root=PROJECT_ROOT,
        multi_bundle=multi_bundle,
        multi_profile=multi_profile,
        custom_output_dir=Path(args.output_dir) if args.output_dir else None,
    )

    for bundle_path in bundle_paths:
        for _filter_job_id, profile in profile_jobs:
            result = run_filter_stage(
                bundle_path=bundle_path,
                profile=profile,
                zone_key=profile.zone_config_name,
                invocation=invocation,
                include_debug=args.debug,
                git_provenance=git_prov,
                paths_base=PROJECT_ROOT,
            )

            rel_bundle = posix_relative(bundle_path, PROJECT_ROOT)
            print(f"zone match bundle: {result.zone_bundle_path}")
            print(f"coverage bundle: {result.coverage_bundle_path}")
            if result.zone_bundle_debug_path is not None:
                print(f"zone debug:  {result.zone_bundle_debug_path}")
            print(f"Run summary:   {result.run_summary_path}")
            print(f"Input bundle:  {rel_bundle}")

            index_documents.append(
                build_filter_index_document(
                    bundle=result.bundle,
                    out_dir=result.output_dir,
                    index_root=index_root,
                    include_debug=result.zone_bundle_debug_path is not None,
                    zone_key=result.zone_key,
                )
            )

    if index_documents:
        index_path = write_run_index(
            index_root,
            step="filter",
            documents=index_documents,
            run_id=build_stage_run_layout(
                stage="filter",
                context=first_layout_key,
                doc_id=index_documents[0].doc_id,
                stamp=stamp,
                session_dir_name=session_dir.name,
                task_key=first_layout_key,
                run_dir_layout=FILTER_RUN_DIR_LAYOUT,
            ).run_id,
        )
        print(f"Session index: {index_path}")


if __name__ == "__main__":
    main()
