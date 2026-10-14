"""Filter-output projection stage runtime: semantic projection artifacts only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from artifacts.filter_output_projection_bundle import (
    FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
    build_filter_output_projection_bundle,
    validate_filter_output_projection_bundle,
)
from artifacts.zone_match_bundle import assert_zone_match_bundle_safe
from core.document.doc_identity import validate_file_hash_format
from llm.invocation import llm_invocations_from_exception, serialize_llm_invocations
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionFacade,
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ResolvedFilterOutputProjectionJob,
)
from steps.project_filter_output import run as run_project_filter_output_step
from runtime.io import load_json, save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import (
    FILTER_OUTPUT_PROJECTION_RUN_DIR_LAYOUT,
    build_filter_output_projection_session_run_naming,
    build_stage_run_layout,
    ensure_stage_doc_run_dir,
    output_leaf_name,
)
from runtime.run_summaries import build_filter_output_projection_run_summary


@dataclass(frozen=True)
class FilterOutputProjectionStageInvocation:
    """Session-level context for one Filter-output projection runner invocation."""

    stamp: datetime
    session_dir: Path
    runs_root: Path
    git_root: Path
    custom_output_dir: Path | None = None


@dataclass(frozen=True)
class FilterOutputProjectionStageResult:
    output_dir: Path
    run_id: str
    filter_job_id: str
    doc_id: str
    zone_key: str
    step_result: FilterOutputProjectionStepResult
    projection_bundle_path: Path
    run_summary_path: Path


def resolve_filter_output_projection_run_id(*, stamp=None) -> str:
    resolved_stamp = stamp or utc_run_stamp()
    return format_run_timestamp(resolved_stamp)


def resolve_filter_output_projection_stage_paths(
    *,
    zone_match_bundle_path: Path | str,
    filter_job_id: str,
    invocation: FilterOutputProjectionStageInvocation,
) -> tuple[Path, str]:
    """Resolve canonical artifact sink path and run_id for one projection stage run."""

    resolved_zone_match = Path(zone_match_bundle_path).resolve()
    zone_match_bundle = load_json(resolved_zone_match)
    if not isinstance(zone_match_bundle, dict):
        raise ValueError("zone_match_bundle must be a JSON object")

    layout_doc_id = output_leaf_name(resolved_zone_match, zone_match_bundle)
    run_context = filter_job_id.strip()
    if not run_context:
        raise ValueError("filter_job_id must be a non-empty string")

    layout = build_stage_run_layout(
        stage="filter_output_projection",
        context=run_context,
        doc_id=layout_doc_id,
        stamp=invocation.stamp,
        session_dir_name=invocation.session_dir.name,
        task_key=run_context,
        run_dir_layout=FILTER_OUTPUT_PROJECTION_RUN_DIR_LAYOUT,
    )
    naming = build_filter_output_projection_session_run_naming(
        stamp=invocation.stamp,
        filter_job_id=run_context,
        doc_id=layout_doc_id,
        git_root=invocation.git_root,
        session_dir_name=invocation.session_dir.name,
    )

    profile_output_dir: Path | None = None
    if invocation.custom_output_dir is not None:
        profile_output_dir = invocation.custom_output_dir

    out_dir = ensure_stage_doc_run_dir(
        invocation.runs_root,
        layout,
        session_dir=invocation.session_dir,
        output_dir=profile_output_dir,
        multi_input=False,
    )
    return out_dir, naming.run_id


def run_filter_output_projection_stage(
    *,
    filter_job_id: str,
    resolved_job: ResolvedFilterOutputProjectionJob,
    zone_match_bundle_path: Path | str,
    analysis_bundle_path: Path | str,
    facade: FilterOutputProjectionFacade,
    output_dir: Path | str,
    git_provenance: dict[str, str | bool | None] | None = None,
    run_id: str | None = None,
) -> FilterOutputProjectionStageResult:
    """Execute canonical projection for one Filter job and persist artifacts."""

    resolved_zone_match = Path(zone_match_bundle_path).resolve()
    zone_match_bundle = load_json(resolved_zone_match)
    if not isinstance(zone_match_bundle, dict):
        raise ValueError("zone_match_bundle must be a JSON object")
    assert_zone_match_bundle_safe(zone_match_bundle)

    resolved_analysis_bundle = Path(analysis_bundle_path).resolve()
    analysis_bundle = load_json(resolved_analysis_bundle)
    if not isinstance(analysis_bundle, dict):
        raise ValueError("analysis_bundle must be a JSON object")

    doc_id = str(zone_match_bundle.get("doc_id") or "").strip()
    if not doc_id:
        raise ValueError("zone_match_bundle.doc_id is required")

    file_hash = validate_file_hash_format(
        zone_match_bundle.get("file_hash"),
        field="file_hash",
    )
    zone_key = str(zone_match_bundle.get("zone_config_name") or "").strip()
    if not zone_key:
        raise ValueError("zone_match_bundle.zone_config_name is required")

    projection_input = FilterOutputProjectionInput(
        filter_job_id=filter_job_id,
        doc_id=doc_id,
        file_hash=file_hash,
        zone_key=zone_key,
        zone_match_bundle=zone_match_bundle,
    )

    resolved_run_id = run_id or resolve_filter_output_projection_run_id()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        step_result = run_project_filter_output_step(
            projection_input=projection_input,
            analysis_bundle=analysis_bundle,
            job=resolved_job,
            facade=facade,
        )
    except Exception as error:
        invocations = llm_invocations_from_exception(error)
        if invocations:
            failure_summary = build_filter_output_projection_run_summary(
                run_id=resolved_run_id,
                filter_job_id=filter_job_id,
                doc_id=doc_id,
                zone_key=zone_key,
                zone_match_bundle_path=resolved_zone_match,
                zone_match_bundle=zone_match_bundle,
                analysis_bundle_path=resolved_analysis_bundle,
                projection_bundle_path=None,
                projected_source_count=0,
                semantic_outcome_count=0,
                llm_invocations=serialize_llm_invocations(invocations),
                git_provenance=git_provenance,
                run_status="failed",
                error={
                    "type": type(error).__name__,
                    "message": str(error),
                },
            )
            save_json(out_dir / "run_summary.json", failure_summary)
        raise

    bundle = build_filter_output_projection_bundle(
        step_result=step_result,
        run_id=resolved_run_id,
    )
    projection_bundle_path = out_dir / FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME
    save_json(projection_bundle_path, bundle)
    reloaded = load_json(projection_bundle_path)
    validate_filter_output_projection_bundle(reloaded)

    run_summary_path = out_dir / "run_summary.json"
    summary = build_filter_output_projection_run_summary(
        run_id=resolved_run_id,
        filter_job_id=filter_job_id,
        doc_id=doc_id,
        zone_key=zone_key,
        zone_match_bundle_path=resolved_zone_match,
        zone_match_bundle=zone_match_bundle,
        analysis_bundle_path=resolved_analysis_bundle,
        projection_bundle_path=projection_bundle_path,
        projected_source_count=len(step_result.projected_sources),
        semantic_outcome_count=len(step_result.semantic_outcomes),
        llm_invocations=serialize_llm_invocations(step_result.llm_invocations),
        git_provenance=git_provenance,
    )
    save_json(run_summary_path, summary)

    return FilterOutputProjectionStageResult(
        output_dir=out_dir,
        run_id=resolved_run_id,
        filter_job_id=filter_job_id,
        doc_id=doc_id,
        zone_key=zone_key,
        step_result=step_result,
        projection_bundle_path=projection_bundle_path,
        run_summary_path=run_summary_path,
    )


__all__ = [
    "FilterOutputProjectionStageInvocation",
    "FilterOutputProjectionStageResult",
    "resolve_filter_output_projection_run_id",
    "resolve_filter_output_projection_stage_paths",
    "run_filter_output_projection_stage",
]
