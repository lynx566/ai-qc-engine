"""Effective candidate scope stage: apply heading overrides to automatic Filter output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.candidate_scope_override import (
    CANDIDATE_SCOPE_OVERRIDE_FILENAME,
    assert_candidate_scope_override_safe,
    build_candidate_scope_override,
)
from artifacts.coverage_bundle import (
    COVERAGE_BUNDLE_FILENAME,
    assert_coverage_bundle_safe,
)
from artifacts.effective_candidate_scope import (
    EFFECTIVE_COVERAGE_BUNDLE_FILENAME,
    RESOLVED_ZONE_MATCH_BUNDLE_FILENAME,
)
from artifacts.zone_match_bundle import (
    ZONE_MATCH_BUNDLE_FILENAME,
    assert_zone_match_bundle_safe,
)
from steps.effective_candidate_scope import build_effective_candidate_scope
from runtime.io import load_json, save_json
from runtime.run_layout import (
    FILTER_RUN_DIR_LAYOUT,
    build_filter_session_run_naming,
    build_stage_run_layout,
    ensure_stage_doc_run_dir,
    output_leaf_name,
    utc_now_iso,
)
from runtime.zone_registry import filter_job_dir_context


@dataclass(frozen=True)
class CandidateScopeStageInvocation:
    stamp: datetime
    session_dir: Path
    runs_root: Path
    git_root: Path
    custom_output_dir: Path | None = None


@dataclass(frozen=True)
class CandidateScopeStageResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    base_filter_run_id: str
    override_path: Path
    resolved_zone_match_bundle_path: Path
    effective_coverage_bundle_path: Path
    automatic_zone_match_bundle_path: Path
    run_summary_path: Path
    resolved_zone_match_bundle: dict[str, Any]
    effective_coverage_bundle: dict[str, Any]


def _assert_public_artifact_safe(
    *,
    artifact_name: str,
    payload: dict[str, Any],
    checker: Any,
) -> None:
    try:
        checker(payload)
    except ValueError as exc:
        raise ValueError(f"[candidate_scope_stage safety:{artifact_name}] {exc}") from exc


def _source_doc_id(bundle: dict[str, Any], bundle_path: Path) -> str:
    return str(bundle.get("doc_id") or bundle_path.parent.name)


def _resolve_stage_paths(
    *,
    analysis_bundle_path: Path,
    analysis_bundle: dict[str, Any],
    zone_key: str,
    invocation: CandidateScopeStageInvocation,
) -> tuple[Path, str, str]:
    layout_doc_id = output_leaf_name(analysis_bundle_path, analysis_bundle)
    run_context = filter_job_dir_context(zone_key=zone_key, profile=None)
    layout = build_stage_run_layout(
        stage="candidate_scope",
        context=run_context,
        doc_id=layout_doc_id,
        stamp=invocation.stamp,
        session_dir_name=invocation.session_dir.name,
        task_key=run_context,
        run_dir_layout=FILTER_RUN_DIR_LAYOUT,
    )
    naming = build_filter_session_run_naming(
        stamp=invocation.stamp,
        zone_key=run_context,
        doc_id=layout_doc_id,
        git_root=invocation.git_root,
        session_dir_name=invocation.session_dir.name,
    )
    out_dir = ensure_stage_doc_run_dir(
        invocation.runs_root,
        layout,
        session_dir=invocation.session_dir,
        output_dir=invocation.custom_output_dir,
        multi_input=False,
    )
    return out_dir, naming.run_id, run_context


def run_candidate_scope_stage(
    *,
    automatic_zone_match_bundle_path: Path | str,
    analysis_bundle_path: Path | str,
    candidate_scope_override: dict[str, Any],
    invocation: CandidateScopeStageInvocation,
    git_provenance: dict[str, str | bool | None] | None = None,
    paths_base: Path | None = None,
) -> CandidateScopeStageResult:
    """Apply heading overrides and persist effective candidate scope artifacts."""
    resolved_zone_path = Path(automatic_zone_match_bundle_path).resolve()
    resolved_analysis_path = Path(analysis_bundle_path).resolve()

    automatic_zone_match_bundle = load_json(resolved_zone_path)
    analysis_bundle = load_json(resolved_analysis_path)
    block_manifest_path = resolved_analysis_path.parent / BLOCK_MANIFEST_FILENAME
    if not block_manifest_path.is_file():
        raise FileNotFoundError(
            f"block_manifest.json is required next to {resolved_analysis_path}"
        )
    block_manifest = load_json(block_manifest_path)

    zone_key = str(automatic_zone_match_bundle.get("zone_config_name") or "").strip()
    if not zone_key:
        raise ValueError("automatic zone_match_bundle.zone_config_name is required")

    out_dir, run_id, run_context = _resolve_stage_paths(
        analysis_bundle_path=resolved_analysis_path,
        analysis_bundle=analysis_bundle,
        zone_key=zone_key,
        invocation=invocation,
    )

    override_payload = build_candidate_scope_override(candidate_scope_override)
    assert_candidate_scope_override_safe(override_payload)

    result = build_effective_candidate_scope(
        automatic_zone_match_bundle=automatic_zone_match_bundle,
        candidate_scope_override=override_payload,
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
        effective_run_id=run_id,
    )

    out_dir.mkdir(parents=True, exist_ok=True)

    override_path = out_dir / CANDIDATE_SCOPE_OVERRIDE_FILENAME
    save_json(override_path, override_payload)

    resolved_zone_path = out_dir / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    save_json(resolved_zone_path, result.effective_zone_match_bundle)
    _assert_public_artifact_safe(
        artifact_name="resolved_zone_match_bundle",
        payload=result.effective_zone_match_bundle,
        checker=assert_zone_match_bundle_safe,
    )

    effective_coverage_path = out_dir / EFFECTIVE_COVERAGE_BUNDLE_FILENAME
    save_json(effective_coverage_path, result.effective_coverage_bundle)
    _assert_public_artifact_safe(
        artifact_name="effective_coverage_bundle",
        payload=result.effective_coverage_bundle,
        checker=assert_coverage_bundle_safe,
    )

    base_filter_run_id = str(override_payload.get("base_filter_run_id") or "")

    run_summary = {
        "run_id": run_id,
        "stage": "candidate_scope",
        "status": "completed",
        "created_at": utc_now_iso(),
        "doc_id": _source_doc_id(analysis_bundle, resolved_analysis_path),
        "zone_key": zone_key,
        "run_context": run_context,
        "base_filter_run_id": base_filter_run_id,
        "filter_job_id": override_payload.get("filter_job_id"),
        "applied_operations": list(result.applied_operations),
        "matched_zone_count": result.effective_zone_match_bundle.get("matched_zone_count"),
        "inputs": {
            "automatic_zone_match_bundle": str(resolved_zone_path),
            "analysis_bundle": str(resolved_analysis_path),
            "block_manifest": str(block_manifest_path),
        },
        "outputs": {
            "candidate_scope_override": CANDIDATE_SCOPE_OVERRIDE_FILENAME,
            "resolved_zone_match_bundle": RESOLVED_ZONE_MATCH_BUNDLE_FILENAME,
            "effective_coverage_bundle": EFFECTIVE_COVERAGE_BUNDLE_FILENAME,
            "automatic_zone_match_bundle_ref": ZONE_MATCH_BUNDLE_FILENAME,
            "coverage_bundle_ref": COVERAGE_BUNDLE_FILENAME,
        },
        "automatic_artifacts_immutable": True,
    }
    if git_provenance is not None:
        run_summary["git"] = dict(git_provenance)
    if paths_base is not None:
        run_summary["paths_base"] = str(paths_base)

    run_summary_path = out_dir / "run_summary.json"
    save_json(run_summary_path, run_summary)

    return CandidateScopeStageResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=_source_doc_id(analysis_bundle, resolved_analysis_path),
        zone_key=zone_key,
        base_filter_run_id=base_filter_run_id,
        override_path=override_path,
        resolved_zone_match_bundle_path=resolved_zone_path,
        effective_coverage_bundle_path=effective_coverage_path,
        automatic_zone_match_bundle_path=resolved_zone_path,
        run_summary_path=run_summary_path,
        resolved_zone_match_bundle=result.effective_zone_match_bundle,
        effective_coverage_bundle=result.effective_coverage_bundle,
    )
