"""Filter stage runtime: zone_match + coverage artifacts (no LLM)."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.coverage_bundle import (
    COVERAGE_BUNDLE_FILENAME,
    assert_coverage_bundle_safe,
    build_coverage_bundle,
)
from artifacts.zone_match_bundle import (
    ZONE_MATCH_BUNDLE_DEBUG_FILENAME,
    ZONE_MATCH_BUNDLE_FILENAME,
    assert_zone_match_bundle_safe,
    build_zone_match_bundle,
)
from core.filtering.jobs import ResolvedFilterJob
from core.filtering.registry import resolve_filter_strategy_for_config
from steps.filter import (
    derive_block_selection_coverage,
    extract_zones_from_bundle,
    to_debug_filter_payload,
    to_public_filter_payload,
)
from runtime.io import load_json, save_json
from runtime.run_layout import (
    FILTER_RUN_DIR_LAYOUT,
    build_filter_session_run_naming,
    build_stage_run_layout,
    ensure_stage_doc_run_dir,
    output_leaf_name,
)
from runtime.run_summaries import (
    build_filter_run_summary,
    normalize_input_parser_type,
)
from runtime.zone_registry import filter_job_dir_context


@dataclass(frozen=True)
class FilterStageInvocation:
    """Session-level context for one filter runner invocation."""

    stamp: datetime
    session_dir: Path
    runs_root: Path
    git_root: Path
    multi_bundle: bool
    multi_profile: bool
    custom_output_dir: Path | None = None


@dataclass(frozen=True)
class FilterStageResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    run_context: str
    zone_bundle_path: Path
    coverage_bundle_path: Path
    zone_bundle_debug_path: Path | None
    run_summary_path: Path
    bundle: dict[str, Any]
    bundle_path: Path


def _summary_zone_key(zone_key: str, profile: Any) -> str:
    """Run-summary zone_key: installed profile ``zone_config_name``."""
    if ":" in zone_key:
        return profile.zone_config_name
    return zone_key


def _source_doc_id(bundle: dict[str, Any], bundle_path: Path) -> str:
    """Document identity from the analysis bundle (not layout leaf naming)."""
    return str(bundle.get("doc_id") or bundle_path.parent.name)


def _resolve_filter_stage_paths(
    *,
    bundle_path: Path,
    bundle: dict[str, Any],
    profile: Any,
    zone_key: str,
    invocation: FilterStageInvocation,
) -> tuple[Path, str, str, str, str]:
    """Resolve output_dir, run_id, run_context, job_zone_key, and layout doc leaf."""
    layout_doc_id = output_leaf_name(bundle_path, bundle)
    run_context = filter_job_dir_context(zone_key=zone_key, profile=profile)
    job_zone_key = _summary_zone_key(zone_key, profile)

    layout = build_stage_run_layout(
        stage="filter",
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

    profile_output_dir: Path | None = None
    if invocation.custom_output_dir is not None:
        base = invocation.custom_output_dir
        if invocation.multi_bundle or invocation.multi_profile:
            base = base / layout.doc_dir_name
            if invocation.multi_profile:
                base = base / run_context
            profile_output_dir = base
        else:
            profile_output_dir = base

    out_dir = ensure_stage_doc_run_dir(
        invocation.runs_root,
        layout,
        session_dir=invocation.session_dir,
        output_dir=profile_output_dir,
        multi_input=False,
    )
    return out_dir, naming.run_id, run_context, job_zone_key, layout_doc_id


def _assert_public_artifact_safe(
    *,
    artifact_name: str,
    payload: dict[str, Any],
    checker: Any,
) -> None:
    """Wrap public-artifact safety errors with a stable filter_stage prefix."""
    try:
        checker(payload)
    except ValueError as exc:
        raise ValueError(f"[filter_stage safety:{artifact_name}] {exc}") from exc


def _load_block_manifest(bundle_path: Path) -> dict[str, Any]:
    """Load ``block_manifest.json`` next to the Prepare Analysis analysis bundle."""
    block_manifest_path = bundle_path.parent / BLOCK_MANIFEST_FILENAME
    if not block_manifest_path.is_file():
        raise FileNotFoundError(
            f"block_manifest.json is required next to {bundle_path}; "
            "run the prepare_analysis step first"
        )
    return load_json(block_manifest_path)


def _load_privacy_audit_for_debug(bundle_path: Path) -> dict[str, Any] | None:
    audit_path = bundle_path.parent / "privacy_audit.json"
    if not audit_path.is_file():
        return None
    return load_json(audit_path)


def run_filter_stage(
    *,
    bundle_path: Path | str,
    profile: Any,
    zone_key: str,
    invocation: FilterStageInvocation,
    include_debug: bool = False,
    git_provenance: dict[str, str | bool | None] | None = None,
    paths_base: Path | None = None,
) -> FilterStageResult:
    """
    Execute one filter job: resolve naming, load inputs, run step, persist artifacts.

    *zone_key* is the installed profile ``zone_config_name``.
    """
    resolved_bundle_path = Path(bundle_path).resolve()
    bundle = load_json(resolved_bundle_path)

    out_dir, run_id, run_context, job_zone_key, _layout_doc_id = _resolve_filter_stage_paths(
        bundle_path=resolved_bundle_path,
        bundle=bundle,
        profile=profile,
        zone_key=zone_key,
        invocation=invocation,
    )

    block_manifest = _load_block_manifest(resolved_bundle_path)
    privacy_audit = _load_privacy_audit_for_debug(resolved_bundle_path)

    meta = bundle.get("document_meta") or {}
    input_parser_type = normalize_input_parser_type(meta.get("parser_type"))
    input_parser_version = meta.get("parser_version") or meta.get("handler_version")

    strategy = resolve_filter_strategy_for_config(profile)
    filter_job = ResolvedFilterJob(config=profile, strategy=strategy)
    zones_raw = extract_zones_from_bundle(bundle, filter_job)
    public_filter_result = to_public_filter_payload(
        zones_raw,
        mask_result=privacy_audit,
        block_manifest=block_manifest,
    )
    zone_bundle = build_zone_match_bundle(public_filter_result)
    _assert_public_artifact_safe(
        artifact_name="zone_match_bundle",
        payload=zone_bundle,
        checker=assert_zone_match_bundle_safe,
    )

    out_dir.mkdir(parents=True, exist_ok=True)

    zone_bundle_path = out_dir / ZONE_MATCH_BUNDLE_FILENAME
    save_json(zone_bundle_path, zone_bundle)

    coverage_rows = derive_block_selection_coverage(
        block_manifest=block_manifest,
        public_filter_result=zone_bundle,
    )
    coverage_bundle = build_coverage_bundle(
        block_manifest=block_manifest,
        coverage=coverage_rows,
        zone_key=job_zone_key,
        filter_run_id=run_id,
    )
    _assert_public_artifact_safe(
        artifact_name="coverage_bundle",
        payload=coverage_bundle,
        checker=assert_coverage_bundle_safe,
    )
    coverage_bundle_path = out_dir / COVERAGE_BUNDLE_FILENAME
    save_json(coverage_bundle_path, coverage_bundle)

    zone_bundle_debug_path: Path | None = None
    if include_debug:
        if privacy_audit is not None:
            zone_bundle_debug_path = out_dir / ZONE_MATCH_BUNDLE_DEBUG_FILENAME
            zone_debug = to_debug_filter_payload(zones_raw, mask_result=privacy_audit)
            save_json(zone_bundle_debug_path, zone_debug)
        else:
            warnings.warn(
                f"--debug requested but no privacy_audit.json next to "
                f"input bundle ({resolved_bundle_path.parent}); skipping "
                f"{ZONE_MATCH_BUNDLE_DEBUG_FILENAME} for {run_context}",
                stacklevel=2,
            )

    summary = build_filter_run_summary(
        run_id=run_id,
        bundle=bundle,
        bundle_path=resolved_bundle_path,
        zone_config=profile,
        zone_bundle=zone_bundle,
        zone_bundle_path=zone_bundle_path,
        zone_bundle_debug_path=zone_bundle_debug_path,
        coverage_bundle_path=coverage_bundle_path,
        input_parser_type=input_parser_type,
        input_parser_version=input_parser_version,
        git_provenance=git_provenance,
        run_context=run_context,
        zone_key=job_zone_key,
        paths_base=paths_base,
    )
    run_summary_path = out_dir / "run_summary.json"
    save_json(run_summary_path, summary)

    return FilterStageResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=_source_doc_id(bundle, resolved_bundle_path),
        zone_key=job_zone_key,
        run_context=run_context,
        zone_bundle_path=zone_bundle_path,
        coverage_bundle_path=coverage_bundle_path,
        zone_bundle_debug_path=zone_bundle_debug_path,
        run_summary_path=run_summary_path,
        bundle=bundle,
        bundle_path=resolved_bundle_path,
    )
