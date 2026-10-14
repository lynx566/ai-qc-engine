from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from core.metadata.schemas import MetadataProfile
from runtime.prepare_analysis.context import PREPARE_ANALYSIS_STAGE_SCOPE
from runtime.run_layout import (
    ANALYSIS_RUN_DIR_LAYOUT,
    EXTRACT_RUN_DIR_LAYOUT,
    FILTER_RUN_DIR_LAYOUT,
    REQUEST_FILE_INTAKE_RUN_DIR_LAYOUT,
    ROUTE_RUN_DIR_LAYOUT,
    STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    run_dir_layout_metadata,
    sanitize_run_segment,
    utc_now_iso,
)
from runtime.run_provenance import (
    finalize_run_summary,
    load_upstream_run_summary,
)
from runtime.run_summary_safe import (
    PATHS_BASE,
    post_analysis_bundle_extra,
    post_mask_inputs,
    summary_artifact_path,
)

FILTER_STAGE_SCOPE = "zone_key"

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _resolved_filter_strategy_id_for_summary(
    *,
    zone_bundle: dict[str, Any] | None,
    zone_config: Any,
) -> str:
    """Prefer filter output metadata; re-resolve from profile when unavailable."""
    if zone_bundle is not None:
        single = zone_bundle.get("resolved_filter_strategy_id")
        if isinstance(single, str) and single.strip():
            return single.strip()
        # Legacy archived bundles may only have plural mirror.
        ids = zone_bundle.get("resolved_filter_strategy_ids")
        if isinstance(ids, list) and ids:
            for item in ids:
                if isinstance(item, str) and item.strip():
                    return item.strip()

    from core.filtering.profiles import normalize_filter_profiles
    from core.filtering.registry import resolve_filter_strategy_for_config

    profiles = normalize_filter_profiles(zone_config)
    return resolve_filter_strategy_for_config(profiles[0]).strategy_id


def normalize_input_parser_type(parser_type: Any) -> Any:
    if isinstance(parser_type, str) and parser_type.startswith("docx_handlers_v"):
        return "docx_handlers"
    return parser_type


def build_extract_run_summary_dict(
    *,
    run_id: str,
    bundle: Any,
    export_slices: bool,
    source_docx: Path,
    git_root: Path,
    context: str | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> dict[str, Any]:
    meta = bundle.document_meta
    outputs: dict[str, str] = {"bundle": "bundle.json"}
    if export_slices:
        outputs["slices_dir"] = "slices/"

    extra: dict[str, Any] = {}
    if meta.get("front_matter_policy_version") is not None:
        extra["front_matter_policy_version"] = meta.get("front_matter_policy_version")
    if meta.get("sentence_index_version") is not None:
        extra["sentence_index_version"] = meta.get("sentence_index_version")
    if meta.get("sentence_index_policy") is not None:
        extra["sentence_index_policy"] = meta.get("sentence_index_policy")
    if meta.get("language") is not None:
        extra["language"] = meta.get("language")
    ctx = context or sanitize_run_segment(bundle.source_type or "docx").lower()
    extra.update(
        run_dir_layout_metadata(
            context=ctx,
            run_dir_layout=EXTRACT_RUN_DIR_LAYOUT,
        )
    )
    file_hash = getattr(bundle, "file_hash", None)
    if isinstance(file_hash, str) and file_hash.strip():
        extra["file_hash"] = file_hash.strip()

    return finalize_run_summary(
        stage="extract",
        run_id=run_id,
        pipeline=["extract"],
        doc_id=bundle.doc_id,
        file_name=bundle.file_name,
        inputs={"source_docx": source_docx.resolve().as_posix()},
        outputs=outputs,
        git_root=git_root,
        git_provenance=git_provenance,
        upstream_summary=None,
        created_at=utc_now_iso(),
        source_type=bundle.source_type,
        parser_type=meta.get("parser_type"),
        parser_version=meta.get("parser_version") or meta.get("handler_version"),
        bundle_schema_version=meta.get("bundle_schema_version"),
        **extra,
    )


def build_prepare_analysis_output_privacy_contract(
    *,
    privacy_transform_applied: bool,
) -> dict[str, Any]:
    """
    Distinguish public artifact privacy levels for prepare_analysis outputs.

    Identity mode (``privacy_transform_applied=False``) produces local raw public
    artifacts — not deidentified and not safe for export. Privacy-transform mode
    emits slim public ``analysis_bundle`` (``public_masked_v0.4``); raw side lives
    in private audit outputs only.
    """
    if privacy_transform_applied:
        return {
            "analysis_bundle": {
                "artifact_privacy_level": "public_masked_v0.4",
                "safe_for_export": False,
                "contains_raw_sensitive_data": False,
            },
            "block_manifest": {
                "artifact_privacy_level": "public_masked_text_transitional",
                "safe_for_export": False,
                "contains_raw_sensitive_data": True,
            },
            "private_outputs": {
                "private_audit_bundle": "private_raw_audit",
                "privacy_audit": "private_raw_audit",
                "mapping": "private_raw_audit",
            },
        }
    return {
        "analysis_bundle": {
            "artifact_privacy_level": "local_raw_public",
            "safe_for_export": False,
            "contains_raw_sensitive_data": True,
        },
        "block_manifest": {
            "artifact_privacy_level": "local_raw_public",
            "safe_for_export": False,
            "contains_raw_sensitive_data": True,
        },
        "private_outputs": {},
    }


def build_filter_output_privacy_contract(
    *,
    include_debug_bundle: bool,
    include_coverage_bundle: bool,
) -> dict[str, Any]:
    """
    Privacy contract for filter outputs.

    ``zone_match_bundle`` is a sanitized public artifact. ``zone_match_bundle.debug``
    remains local-only debug output when requested.
    """
    contract: dict[str, Any] = {
        "zone_match_bundle": {
            "artifact_privacy_level": "public_masked_v0.2",
            "safe_for_export": False,
            "contains_raw_sensitive_data": False,
        },
        "private_outputs": {},
    }
    if include_coverage_bundle:
        contract["coverage_bundle"] = {
            "artifact_privacy_level": "public_structural_v0.1",
            "safe_for_export": False,
            "contains_raw_sensitive_data": False,
        }
    if include_debug_bundle:
        contract["private_outputs"]["zone_match_bundle_debug"] = "local_debug_raw"
    return contract


def build_prepare_analysis_run_summary(
    *,
    run_id: str,
    bundle_dict: dict[str, Any],
    language: str,
    input_bundle: Path | None,
    output_bundle_path: Path | None,
    analysis_bundle_path: Path,
    privacy_audit_path: Path | None = None,
    mapping_path: Path | None = None,
    private_audit_path: Path | None = None,
    privacy_transform_applied: bool = False,
    privacy_detectors_configured: list[str] | None = None,
    privacy_detectors_used: list[str] | None = None,
    privacy_transform_slot: str = "after_extract",
    date_shift_offset_days: int | None = None,
    analysis_block_count: int,
    privacy_provenance_stats: Mapping[str, str] | None = None,
    privacy_profile_ref: str | None = None,
    session_segment: str | None = None,
    plugin_provenance: Mapping[str, Any] | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    meta = bundle_dict.get("document_meta") or {}
    input_parser_type = normalize_input_parser_type(meta.get("parser_type"))
    base = paths_base or PATHS_BASE

    raw_inputs: dict[str, str] = {}
    if input_bundle is not None:
        raw_inputs["input_bundle"] = str(input_bundle)

    outputs: dict[str, str] = {
        "analysis_bundle": analysis_bundle_path.name,
        "block_manifest": BLOCK_MANIFEST_FILENAME,
    }
    if privacy_transform_applied:
        if privacy_audit_path is not None:
            outputs["privacy_audit"] = privacy_audit_path.name
        if mapping_path is not None:
            outputs["mapping"] = mapping_path.name
        if private_audit_path is not None:
            outputs["private_audit_bundle"] = private_audit_path.name
    if output_bundle_path is not None:
        outputs["bundle"] = output_bundle_path.name

    upstream_summary = (
        load_upstream_run_summary(input_bundle) if input_bundle is not None else None
    )

    resolved_segment = session_segment or privacy_profile_ref or "clinical_trial_doc"
    extra: dict[str, Any] = {
        "language": language,
        "stage_scope": PREPARE_ANALYSIS_STAGE_SCOPE,
    }
    extra.update(
        run_dir_layout_metadata(
            context=resolved_segment,
            run_dir_layout=ANALYSIS_RUN_DIR_LAYOUT,
        )
    )
    configured = list(privacy_detectors_configured or [])
    used = list(privacy_detectors_used or [])
    if privacy_transform_applied:
        extra["analysis_transform"] = "privacy_transform"
        extra["privacy_transform_applied"] = True
        extra["privacy_detectors_configured"] = configured
        extra["privacy_detectors_used"] = used
        audit_outputs = ["privacy_audit", "mapping"]
        if private_audit_path is not None:
            audit_outputs.append("private_audit_bundle")
        extra["audit_outputs"] = audit_outputs
        extra["output_privacy_contract"] = (
            build_prepare_analysis_output_privacy_contract(
                privacy_transform_applied=True,
            )
        )
        if privacy_profile_ref is not None:
            extra["privacy_profile_ref"] = privacy_profile_ref
        if date_shift_offset_days is not None:
            extra["privacy_transform"] = {
                "slot": privacy_transform_slot,
                "settings": {"date_shift_offset_days": date_shift_offset_days},
            }
    else:
        extra["analysis_transform"] = "identity"
        extra["privacy_transform_applied"] = False
        extra["privacy_detectors_configured"] = []
        extra["privacy_detectors_used"] = []
        extra["audit_outputs"] = []
        extra["output_privacy_contract"] = (
            build_prepare_analysis_output_privacy_contract(
                privacy_transform_applied=False,
            )
        )

    if plugin_provenance is not None:
        extra["plugin"] = deepcopy(dict(plugin_provenance))
    extra.update(post_analysis_bundle_extra(bundle_dict))

    stats: dict[str, Any] = {"analysis_block_count": analysis_block_count}
    if privacy_transform_applied and privacy_provenance_stats:
        stats.update(dict(privacy_provenance_stats))

    return finalize_run_summary(
        stage="prepare_analysis",
        run_id=run_id,
        pipeline=["extract", "prepare_analysis"],
        doc_id=bundle_dict.get("doc_id"),
        file_name=None,
        inputs=post_mask_inputs(raw_inputs, base=base),
        outputs=outputs,
        git_root=BACKEND_ROOT,
        git_provenance=git_provenance,
        upstream_summary=upstream_summary,
        created_at=utc_now_iso(),
        source_type=bundle_dict.get("source_type"),
        input_bundle_schema_version=meta.get("bundle_schema_version"),
        input_parser_type=input_parser_type,
        input_parser_version=meta.get("parser_version") or meta.get("handler_version"),
        stats=stats,
        **extra,
    )


def metadata_profile_version(profile: MetadataProfile) -> str:
    """Profile version token from ``MetadataProfile.name`` (e.g. ``v0_1``), not module path."""
    name = profile.name
    if "." in name:
        return name.rsplit(".", 1)[-1]
    return name


def metadata_profile_provenance(profile: MetadataProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "version": metadata_profile_version(profile),
        "context_strategy": profile.context.strategy,
        "context_block_count": profile.context.default_block_count,
    }


def build_doc_meta_run_summary(
    *,
    run_id: str,
    doc_meta_bundle_path: Path,
    document_context_preview_path: Path,
    profile: MetadataProfile,
    doc_id: str | None = None,
    analysis_bundle_path: Path,
    analysis_bundle: dict[str, Any] | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    from runtime.run_layout import DOC_META_RUN_DIR_LAYOUT, run_dir_layout_metadata

    resolved_analysis_bundle_path = analysis_bundle_path
    resolved_analysis_bundle = analysis_bundle

    upstream_summary = load_upstream_run_summary(resolved_analysis_bundle_path)
    layout_extra = run_dir_layout_metadata(
        context="",
        run_dir_layout=DOC_META_RUN_DIR_LAYOUT,
    )
    base = paths_base or PATHS_BASE
    extra = {
        **layout_extra,
        **post_analysis_bundle_extra(resolved_analysis_bundle or {}),
        "metadata_profile": metadata_profile_provenance(profile),
    }
    return finalize_run_summary(
        stage="doc_meta",
        run_id=run_id,
        pipeline=["extract", "prepare_analysis", "doc_meta"],
        doc_id=doc_id,
        file_name=None,
        inputs=post_mask_inputs(
            {"analysis_bundle": str(resolved_analysis_bundle_path.resolve())},
            base=base,
        ),
        outputs={
            "doc_meta_bundle": doc_meta_bundle_path.name,
            "document_context_preview": document_context_preview_path.name,
            "run_summary": "run_summary.json",
        },
        git_root=BACKEND_ROOT,
        git_provenance=git_provenance,
        upstream_summary=upstream_summary,
        created_at=utc_now_iso(),
        source_stage="prepare_analysis",
        **extra,
    )


def build_filter_run_summary(
    *,
    run_id: str,
    bundle: dict[str, Any],
    bundle_path: Path,
    zone_config: Any,
    zone_bundle_path: Path,
    zone_bundle_debug_path: Path | None,
    coverage_bundle_path: Path | None = None,
    input_parser_type: str | None,
    input_parser_version: str | None,
    git_provenance: dict[str, str | bool | None] | None = None,
    run_context: str | None = None,
    zone_key: str | None = None,
    paths_base: Path | None = None,
    zone_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = bundle.get("document_meta") or {}
    pipeline = ["extract", "prepare_analysis", "filter"]
    outputs: dict[str, str] = {
        "zone_match_bundle": zone_bundle_path.name,
    }
    if coverage_bundle_path is not None:
        outputs["coverage_bundle"] = coverage_bundle_path.name

    base = paths_base or PATHS_BASE
    inputs = {
        "input_analysis_bundle": summary_artifact_path(bundle_path, base=base),
    }
    upstream_summary = load_upstream_run_summary(bundle_path)
    resolved_zone_key = sanitize_run_segment(zone_key or run_context).lower()
    layout_extra = run_dir_layout_metadata(
        context=resolved_zone_key,
        run_dir_layout=FILTER_RUN_DIR_LAYOUT,
    )
    extra: dict[str, Any] = {
        "artifacts": {
            "zone_match_bundle": zone_bundle_path.name,
            "zone_match_bundle_debug": (
                zone_bundle_debug_path.name
                if zone_bundle_debug_path is not None
                else None
            ),
        },
        "zone_key": resolved_zone_key,
        "output_privacy_contract": build_filter_output_privacy_contract(
            include_debug_bundle=zone_bundle_debug_path is not None,
            include_coverage_bundle=coverage_bundle_path is not None,
        ),
    }

    if coverage_bundle_path is not None:
        extra["artifacts"]["coverage_bundle"] = coverage_bundle_path.name

    extra.update(post_analysis_bundle_extra(bundle))
    resolved_filter_strategy_id = _resolved_filter_strategy_id_for_summary(
        zone_bundle=zone_bundle,
        zone_config=zone_config,
    )
    strategy_summary: dict[str, Any] = {
        "resolved_filter_strategy_id": resolved_filter_strategy_id,
    }
    return finalize_run_summary(
        stage="filter",
        run_id=run_id,
        pipeline=pipeline,
        doc_id=bundle.get("doc_id"),
        file_name=None,
        inputs=inputs,
        outputs=outputs,
        git_root=BACKEND_ROOT,
        git_provenance=git_provenance,
        upstream_summary=upstream_summary,
        created_at=utc_now_iso(),
        input_stage="prepare_analysis",
        source_type=bundle.get("source_type"),
        stage_scope=FILTER_STAGE_SCOPE,
        language=zone_config.language,
        input_bundle_schema_version=meta.get("bundle_schema_version"),
        input_parser_type=input_parser_type,
        input_parser_version=input_parser_version,
        zone_config_name=zone_config.zone_config_name,
        zone_config_version=zone_config.zone_config_version,
        **strategy_summary,
        **extra,
        **layout_extra,
    )


def filter_output_projection_lineage_from_zone_match_bundle(
    zone_match_bundle: Mapping[str, Any],
) -> tuple[str, list[str]]:
    """Derive projection upstream lineage from the consumed zone_match_bundle identity."""
    input_stage = str(zone_match_bundle.get("stage") or "filter").strip() or "filter"
    if input_stage == "candidate_scope":
        return (
            "candidate_scope",
            [
                "extract",
                "prepare_analysis",
                "filter",
                "candidate_scope",
                "filter_output_projection",
            ],
        )
    return (
        "filter",
        [
            "extract",
            "prepare_analysis",
            "filter",
            "filter_output_projection",
        ],
    )


def build_filter_output_projection_run_summary(
    *,
    run_id: str,
    filter_job_id: str,
    doc_id: str,
    zone_key: str,
    zone_match_bundle_path: Path,
    zone_match_bundle: Mapping[str, Any],
    analysis_bundle_path: Path,
    projection_bundle_path: Path | None,
    projected_source_count: int,
    semantic_outcome_count: int,
    llm_invocations: Sequence[Mapping[str, Any]] | None = None,
    run_status: str = "success",
    error: Mapping[str, Any] | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    base = paths_base or PATHS_BASE
    ctx = sanitize_run_segment(filter_job_id).lower()
    layout_extra = run_dir_layout_metadata(
        context=ctx,
        run_dir_layout=FILTER_RUN_DIR_LAYOUT,
    )
    upstream_summary = load_upstream_run_summary(zone_match_bundle_path)
    source_stage, pipeline = filter_output_projection_lineage_from_zone_match_bundle(
        zone_match_bundle
    )
    stats = {
        "projected_source_count": projected_source_count,
        "semantic_outcome_count": semantic_outcome_count,
    }
    outputs = {"run_summary": "run_summary.json"}
    if projection_bundle_path is not None:
        outputs["filter_output_projection_bundle"] = projection_bundle_path.name
    summary = finalize_run_summary(
        stage="filter_output_projection",
        run_id=run_id,
        pipeline=pipeline,
        doc_id=doc_id,
        file_name=None,
        inputs=post_mask_inputs(
            {
                "zone_match_bundle": str(zone_match_bundle_path),
                "analysis_bundle": str(analysis_bundle_path),
            },
            base=base,
        ),
        outputs=outputs,
        git_root=BACKEND_ROOT,
        git_provenance=git_provenance,
        upstream_summary=upstream_summary,
        created_at=utc_now_iso(),
        source_stage=source_stage,
        zone_key=zone_key,
        filter_job_id=filter_job_id,
        stats=stats,
        status=run_status,
        run_status=run_status,
        **layout_extra,
    )
    summary["llm_invocations"] = [dict(item) for item in (llm_invocations or ())]
    if error is not None:
        summary["error"] = dict(error)
    return summary


def build_projected_source_route_run_summary(
    *,
    run_id: str,
    doc_id: str,
    semantic_module_id: str,
    block_manifest_path: Path,
    doc_meta_bundle_path: Path,
    analysis_bundle_path: Path,
    routed_bundle_paths: dict[str, Path],
    routing_manifest_path: Path,
    route_counts: dict[str, int],
    selected_projected_source_count: int,
    projection_input_refs: Sequence[Mapping[str, str]] | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    upstream_summary = load_upstream_run_summary(block_manifest_path)
    base = paths_base or PATHS_BASE
    ctx = sanitize_run_segment(semantic_module_id).lower()
    layout_extra = run_dir_layout_metadata(
        context=ctx,
        run_dir_layout=ROUTE_RUN_DIR_LAYOUT,
    )
    stats: dict[str, Any] = {
        "selected_projected_source_count": selected_projected_source_count,
        "unit_count": route_counts.get("total_routed_unit_count", 0),
        "aggregate_unit_count": route_counts.get("aggregate_unit_count", 0),
        "table_unit_count": route_counts.get("table_unit_count", 0),
        "case_unit_count": route_counts.get("case_unit_count", 0),
        "unknown_unit_count": route_counts.get("unknown_unit_count", 0),
    }
    outputs: dict[str, str] = {
        "routed_units_aggregate": routed_bundle_paths["aggregate"].name,
        "routed_units_table": routed_bundle_paths["table"].name,
        "routed_units_case": routed_bundle_paths["case"].name,
        "routed_units_unknown": routed_bundle_paths["unknown"].name,
        "routing_manifest": routing_manifest_path.name,
        "run_summary": "run_summary.json",
    }
    path_inputs = post_mask_inputs(
        {
            "block_manifest": str(block_manifest_path),
            "doc_meta_bundle": str(doc_meta_bundle_path),
            "analysis_bundle": str(analysis_bundle_path),
        },
        base=base,
    )
    route_inputs: dict[str, Any] = dict(path_inputs)
    if projection_input_refs:
        route_inputs["projection_input_refs"] = [
            dict(ref) for ref in projection_input_refs
        ]
    return finalize_run_summary(
        stage="route",
        run_id=run_id,
        pipeline=[
            "extract",
            "prepare_analysis",
            "doc_meta",
            "filter",
            "filter_output_projection",
            "route",
        ],
        doc_id=doc_id,
        file_name=None,
        inputs=route_inputs,
        outputs=outputs,
        git_root=BACKEND_ROOT,
        git_provenance=git_provenance,
        upstream_summary=upstream_summary,
        created_at=utc_now_iso(),
        source_stage="filter_output_projection",
        semantic_module_id=semantic_module_id,
        stats=stats,
        **layout_extra,
    )


def build_aggregate_evidence_prepare_run_summary(
    *,
    run_id: str,
    doc_id: str,
    zone_key: str,
    coverage_bundle_path: Path | None = None,
    filter_job_coverage_refs: Sequence[Mapping[str, str]] | None = None,
    projection_input_refs: Sequence[Mapping[str, str]] | None = None,
    block_manifest_path: Path,
    doc_meta_bundle_path: Path,
    analysis_bundle_path: Path,
    routed_aggregate_bundle_path: Path,
    routing_manifest_path: Path,
    assessment_input_path: Path,
    assessment_input_preview_path: Path,
    private_audit_bundle_path: Path | None = None,
    raw_audit_source: str | None = None,
    assessment_input: dict[str, Any] | None = None,
    assessment_runtime_context: dict[str, Any] | None = None,
    assessment_runtime_context_path: Path | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    unit_integrity_status: str | None = None,
    unit_integrity_summary: dict[str, int] | None = None,
    unit_integrity_report_path: Path | None = None,
    aggregate_unit_count: int | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    projected_fan_in = bool(filter_job_coverage_refs)
    if projected_fan_in:
        upstream_summary = load_upstream_run_summary(routing_manifest_path)
    else:
        if coverage_bundle_path is None:
            raise ValueError(
                "coverage_bundle_path is required for single-source prepare run summary"
            )
        upstream_summary = load_upstream_run_summary(coverage_bundle_path)
    base = paths_base or PATHS_BASE
    ctx = sanitize_run_segment(zone_key or "process").lower()
    layout_extra = run_dir_layout_metadata(
        context=ctx,
        run_dir_layout=STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    )
    stats: dict[str, Any] = {
        "phase": "prepare",
    }
    if raw_audit_source is not None:
        stats["raw_audit_source"] = raw_audit_source
    if aggregate_unit_count is not None:
        stats["aggregate_unit_count"] = aggregate_unit_count
        stats["unit_count"] = aggregate_unit_count
        stats["assessment_unit_count"] = aggregate_unit_count
    if assessment_input:
        from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
            count_compact_assessment_stats,
        )

        compact_stats = count_compact_assessment_stats(assessment_input)
        stats["heading_scope_count"] = compact_stats["heading_scope_count"]
        stats["assessment_unit_count"] = compact_stats["assessment_unit_count"]
        stats["assessment_sentence_count"] = compact_stats["assessment_sentence_count"]
        stats["unit_count"] = compact_stats["assessment_unit_count"]
        stats["aggregate_unit_count"] = compact_stats["assessment_unit_count"]
        try:
            from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
                build_scope_assessment_task_manifest,
            )

            scope_tasks = build_scope_assessment_task_manifest(assessment_input)
            stats["scope_assessment_task_count"] = len(scope_tasks)
        except ValueError:
            pass
        warnings = assessment_input.get("warnings")
        if warnings:
            stats["warnings"] = warnings
    if assessment_runtime_context:
        stats["runtime_context_id"] = assessment_runtime_context.get(
            "runtime_context_id"
        )
        stats["runtime_provenance_unit_count"] = len(
            assessment_runtime_context.get("unit_provenance") or {}
        )
    if unit_integrity_status is not None:
        stats["unit_integrity_status"] = unit_integrity_status
    if unit_integrity_summary is not None:
        stats["unit_integrity_summary"] = dict(unit_integrity_summary)

    outputs: dict[str, str] = {
        "assessment_input": assessment_input_path.name,
        "assessment_input_preview": assessment_input_preview_path.name,
        "run_summary": "run_summary.json",
    }
    if assessment_runtime_context_path is not None:
        outputs["assessment_runtime_context"] = assessment_runtime_context_path.name
    if unit_integrity_report_path is not None:
        outputs["unit_integrity_report"] = unit_integrity_report_path.name

    inputs_payload: dict[str, str | list[dict[str, str]]] = {
        "block_manifest": str(block_manifest_path),
        "doc_meta_bundle": str(doc_meta_bundle_path),
        "analysis_bundle": str(analysis_bundle_path),
        "routed_aggregate_bundle": str(routed_aggregate_bundle_path),
        "routing_manifest": str(routing_manifest_path),
    }
    if projected_fan_in:
        inputs_payload["filter_job_coverage_refs"] = [
            {
                "filter_job_id": str(ref["filter_job_id"]),
                "coverage_bundle": str(ref["coverage_bundle"]),
            }
            for ref in filter_job_coverage_refs or ()
            if str(ref.get("filter_job_id") or "").strip()
            and str(ref.get("coverage_bundle") or "").strip()
        ]
        if projection_input_refs:
            inputs_payload["projection_input_refs"] = [
                {
                    "filter_job_id": str(ref["filter_job_id"]),
                    "zone_key": str(ref["zone_key"]),
                    "filter_output_projection_bundle_id": str(
                        ref["filter_output_projection_bundle_id"]
                    ),
                }
                for ref in projection_input_refs
                if str(ref.get("filter_job_id") or "").strip()
                and str(ref.get("zone_key") or "").strip()
                and str(ref.get("filter_output_projection_bundle_id") or "").strip()
            ]
    else:
        inputs_payload["coverage_bundle"] = str(coverage_bundle_path)
    if private_audit_bundle_path is not None:
        inputs_payload["private_audit_bundle"] = str(private_audit_bundle_path)

    string_inputs: dict[str, str] = {}
    structured_inputs: dict[str, Any] = {}
    for key, value in inputs_payload.items():
        if isinstance(value, list):
            structured_inputs[key] = _mask_structured_run_summary_inputs(value, base=base)
        else:
            string_inputs[key] = str(value)

    masked_inputs: dict[str, Any] = dict(post_mask_inputs(string_inputs, base=base))
    masked_inputs.update(structured_inputs)

    return finalize_run_summary(
        stage=EVIDENCE_SOURCE_PREPARATION_STAGE,
        run_id=run_id,
        pipeline=[
            "extract",
            "prepare_analysis",
            "doc_meta",
            "filter",
            "route",
            EVIDENCE_SOURCE_PREPARATION_STAGE,
        ],
        doc_id=doc_id,
        file_name=None,
        inputs=masked_inputs,
        outputs=outputs,
        git_root=BACKEND_ROOT,
        git_provenance=git_provenance,
        upstream_summary=upstream_summary,
        created_at=utc_now_iso(),
        source_stage="route",
        zone_key=zone_key,
        stats=stats,
        **layout_extra,
        **post_analysis_bundle_extra(assessment_input),
    )


def _mask_structured_run_summary_inputs(
    entries: Sequence[Mapping[str, str]],
    *,
    base: Path | None = None,
) -> list[dict[str, str]]:
    masked: list[dict[str, str]] = []
    root = base or PATHS_BASE
    for entry in entries:
        record: dict[str, str] = {}
        for key, value in entry.items():
            if key in {"coverage_bundle"}:
                record[key] = summary_artifact_path(Path(value), base=root)
            else:
                record[key] = str(value)
        masked.append(record)
    return masked


_USABLE_API_RESULT_FIELDS = (
    "api_result_usable",
    "fallback_used",
    "fallback_reason",
    "fallback_source",
)


def _build_failed_api_run_summary_usability_fields() -> dict[str, Any]:
    return {
        "api_result_usable": False,
        "fallback_used": False,
        "fallback_reason": None,
        "fallback_source": None,
    }


def api_run_summary_usability_fields(
    *,
    llm_mode: str,
    scope_assessments: dict[str, Any] | None,
    run_status: str,
) -> dict[str, Any]:
    if llm_mode != "api":
        return {}
    if scope_assessments is not None:
        api_result = scope_assessments.get("api_result")
        if isinstance(api_result, dict):
            return {
                field: api_result.get(field)
                for field in _USABLE_API_RESULT_FIELDS
            }
    if run_status == "failed":
        return _build_failed_api_run_summary_usability_fields()
    return {}


def build_aggregate_evidence_assess_run_summary(
    *,
    run_id: str,
    assessment_input: dict[str, Any],
    assessment_input_path: Path,
    scope_assessments_path: Path | None,
    scope_assessments: dict[str, Any] | None,
    scope_assessment_review_path: Path | None,
    scope_assessment_review: dict[str, Any] | None,
    assessment_profile_name: str,
    llm_mode: str,
    zone_key: str | None,
    phase: str,
    completed_operation: str,
    git_provenance: dict[str, str | bool | None] | None = None,
    llm_execution: dict[str, Any] | None = None,
    run_status: str = "success",
    error: dict[str, Any] | None = None,
    scope_assessment_trace: dict[str, Any] | None = None,
    scope_assessment_trace_path: Path | None = None,
    llm_invocations: Sequence[Mapping[str, Any]] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    upstream_summary = load_upstream_run_summary(assessment_input_path)
    base = paths_base or PATHS_BASE
    ctx = sanitize_run_segment(
        zone_key or assessment_input.get("zone_key") or "process"
    ).lower()
    layout_extra = run_dir_layout_metadata(
        context=ctx,
        run_dir_layout=STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    )

    raw_inputs: dict[str, str] = {
        "assessment_input": str(assessment_input_path),
    }

    scope_assessment_count = (
        scope_assessments.get("scope_assessment_count")
        if scope_assessments is not None
        else None
    )
    input_unit_count = 0
    scope_count = 0
    if assessment_input.get("heading_scopes"):
        from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
            count_compact_assessment_stats,
        )

        compact_stats = count_compact_assessment_stats(assessment_input)
        input_unit_count = compact_stats["assessment_unit_count"]
        scope_count = compact_stats["heading_scope_count"]
    else:
        input_unit_count = len(assessment_input.get("units") or [])

    safety_role_counts = {
        "primary_safety_finding_scope_count": 0,
        "safety_context_scope_count": 0,
        "not_applicable_scope_count": 0,
        "route_mismatch_scope_count": 0,
    }
    if scope_assessments is not None:
        for entry in scope_assessments.get("scope_assessments") or []:
            if not isinstance(entry, dict):
                continue
            safety_role = str(entry.get("safety_role") or "")
            if safety_role == "primary_safety_finding":
                safety_role_counts["primary_safety_finding_scope_count"] += 1
            elif safety_role == "safety_context":
                safety_role_counts["safety_context_scope_count"] += 1
            elif safety_role == "not_applicable":
                safety_role_counts["not_applicable_scope_count"] += 1
            route_qc = entry.get("route_qc")
            if isinstance(route_qc, dict) and route_qc.get("route_mismatch") is True:
                safety_role_counts["route_mismatch_scope_count"] += 1

    summary_extra: dict[str, Any] = {}
    if llm_execution:
        summary_extra["llm_execution"] = llm_execution
    summary_extra["llm_invocations"] = [
        dict(item) for item in (llm_invocations or ())
    ]

    outputs: dict[str, Any] = {"run_summary": "run_summary.json"}
    if scope_assessments_path is not None:
        outputs["scope_assessments"] = scope_assessments_path.name
        if scope_assessments is not None:
            outputs["scope_assessments_schema_version"] = scope_assessments.get(
                "schema_version"
            )
    if scope_assessment_review_path is not None:
        outputs["scope_assessment_review"] = scope_assessment_review_path.name
        if scope_assessment_review is not None:
            outputs["scope_assessment_review_schema_version"] = (
                scope_assessment_review.get("schema_version")
            )
    if scope_assessment_trace_path is not None:
        outputs["scope_assessment_trace"] = scope_assessment_trace_path.name

    stats: dict[str, Any] = {
        "phase": phase,
        "completed_operation": completed_operation,
        "input_unit_count": input_unit_count,
        "scope_count": scope_count,
        "scope_assessment_count": scope_assessment_count,
        "assessment_profile_name": assessment_profile_name,
        "llm_mode": llm_mode,
        **safety_role_counts,
    }
    if scope_assessments is not None:
        stats["prompt_name"] = scope_assessments.get("prompt_name")
        stats["prompt_version"] = scope_assessments.get("prompt_version")
        api_result = scope_assessments.get("api_result")
        if isinstance(api_result, dict):
            for key in (
                "api_response_rejected",
                "fallback_used",
                "fallback_source",
            ):
                if key in api_result:
                    stats[key] = api_result.get(key)
    if scope_assessment_trace is not None:
        for key in (
            "api_response_rejected",
            "fallback_used",
            "fallback_source",
        ):
            if key not in stats and key in scope_assessment_trace:
                stats[key] = scope_assessment_trace.get(key)

    masked_inputs = post_mask_inputs(raw_inputs, base=base)

    finalize_kwargs: dict[str, Any] = {
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "run_id": run_id,
        "pipeline": [
            "extract",
            "prepare_analysis",
            "doc_meta",
            "filter",
            "route",
            EVIDENCE_SOURCE_PREPARATION_STAGE,
        ],
        "doc_id": str(assessment_input.get("doc_id") or ""),
        "file_name": None,
        "inputs": masked_inputs,
        "outputs": outputs,
        "git_root": BACKEND_ROOT,
        "git_provenance": git_provenance,
        "upstream_summary": upstream_summary,
        "created_at": utc_now_iso(),
        "source_stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "zone_key": zone_key or assessment_input.get("zone_key"),
        "stats": stats,
        "run_status": run_status,
        "status": run_status,
        **layout_extra,
        **post_analysis_bundle_extra(assessment_input),
        **summary_extra,
        **api_run_summary_usability_fields(
            llm_mode=llm_mode,
            scope_assessments=scope_assessments,
            run_status=run_status,
        ),
    }
    if error is not None:
        finalize_kwargs["error"] = error
    return finalize_run_summary(**finalize_kwargs)


def build_aggregate_evidence_eligibility_run_summary(
    *,
    run_id: str,
    scope_assessments_path: Path,
    scope_assessments: dict[str, Any],
    heading_scope_eligibility_path: Path,
    heading_scope_eligibility: dict[str, Any],
    zone_key: str | None,
    phase: str,
    completed_operation: str,
    git_provenance: dict[str, str | bool | None] | None = None,
    run_status: str = "success",
    error: dict[str, Any] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    base = paths_base or PATHS_BASE
    ctx = sanitize_run_segment(
        zone_key or scope_assessments.get("zone_key") or "process"
    ).lower()
    layout_extra = run_dir_layout_metadata(
        context=ctx,
        run_dir_layout=STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    )

    source_ref = heading_scope_eligibility.get("source_scope_assessments_ref") or {}
    raw_inputs: dict[str, str] = {
        "scope_assessments": str(scope_assessments_path),
    }

    outputs: dict[str, Any] = {
        "run_summary": "run_summary.json",
        "heading_scope_eligibility": heading_scope_eligibility_path.name,
        "heading_scope_eligibility_schema_version": heading_scope_eligibility.get(
            "schema_version"
        ),
    }

    stats: dict[str, Any] = {
        "phase": phase,
        "completed_operation": completed_operation,
        "scope_count": heading_scope_eligibility.get("scope_count"),
        "auto_included_scope_count": heading_scope_eligibility.get(
            "auto_included_scope_count"
        ),
        "excluded_scope_count": heading_scope_eligibility.get("excluded_scope_count"),
        "review_ambiguous_scope_count": heading_scope_eligibility.get(
            "review_ambiguous_scope_count"
        ),
        "source_scope_assessments_ref": dict(source_ref),
    }
    eligibility_status_counts = heading_scope_eligibility.get(
        "eligibility_status_counts"
    )
    if isinstance(eligibility_status_counts, dict):
        stats["eligibility_status_counts"] = dict(eligibility_status_counts)

    masked_inputs = post_mask_inputs(raw_inputs, base=base)

    finalize_kwargs: dict[str, Any] = {
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "run_id": run_id,
        "pipeline": [
            "extract",
            "prepare_analysis",
            "doc_meta",
            "filter",
            "route",
            EVIDENCE_SOURCE_PREPARATION_STAGE,
        ],
        "doc_id": str(scope_assessments.get("doc_id") or ""),
        "file_name": None,
        "inputs": masked_inputs,
        "outputs": outputs,
        "git_root": BACKEND_ROOT,
        "git_provenance": git_provenance,
        "upstream_summary": None,
        "created_at": utc_now_iso(),
        "source_stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "zone_key": zone_key or scope_assessments.get("zone_key"),
        "stats": stats,
        "run_status": run_status,
        "status": run_status,
        "file_hash": scope_assessments.get("file_hash"),
        **layout_extra,
        **post_analysis_bundle_extra(scope_assessments),
    }
    if error is not None:
        finalize_kwargs["error"] = error
    return finalize_run_summary(**finalize_kwargs)


def build_aggregate_evidence_assemble_run_summary(
    *,
    run_id: str,
    assessment_input_path: Path,
    assessment_runtime_context_path: Path,
    scope_assessments_path: Path,
    heading_scope_eligibility_path: Path,
    aggregate_evidence_source_bundle_path: Path,
    aggregate_evidence_source_bundle: dict[str, Any],
    stats: Any,
    zone_key: str | None,
    phase: str,
    completed_operation: str,
    git_provenance: dict[str, str | bool | None] | None = None,
    run_status: str = "success",
    error: dict[str, Any] | None = None,
    paths_base: Path | None = None,
) -> dict[str, Any]:
    base = paths_base or PATHS_BASE
    ctx = sanitize_run_segment(zone_key or "process").lower()
    layout_extra = run_dir_layout_metadata(
        context=ctx,
        run_dir_layout=STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    )

    raw_inputs: dict[str, str] = {
        "assessment_input": str(assessment_input_path),
        "assessment_runtime_context": str(assessment_runtime_context_path),
        "scope_assessments": str(scope_assessments_path),
        "heading_scope_eligibility": str(heading_scope_eligibility_path),
    }

    outputs: dict[str, Any] = {
        "run_summary": "run_summary.json",
        "aggregate_evidence_source_bundle": aggregate_evidence_source_bundle_path.name,
        "aggregate_evidence_source_bundle_schema_version": aggregate_evidence_source_bundle.get(
            "schema_version"
        ),
    }

    summary_stats: dict[str, Any] = {
        "phase": phase,
        "completed_operation": completed_operation,
        "input_heading_scope_count": stats.input_heading_scope_count,
        "assembled_heading_scope_count": stats.assembled_heading_scope_count,
        "auto_included_count": stats.auto_included_count,
        "review_ambiguous_count": stats.review_ambiguous_count,
        "excluded_heading_scope_count": stats.excluded_heading_scope_count,
    }
    excluded_counts = getattr(stats, "excluded_counts_by_status", None)
    if isinstance(excluded_counts, dict) and excluded_counts:
        summary_stats["excluded_counts_by_status"] = dict(excluded_counts)

    masked_inputs = post_mask_inputs(raw_inputs, base=base)

    finalize_kwargs: dict[str, Any] = {
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "run_id": run_id,
        "pipeline": [
            "extract",
            "prepare_analysis",
            "doc_meta",
            "filter",
            "route",
            EVIDENCE_SOURCE_PREPARATION_STAGE,
        ],
        "doc_id": str(aggregate_evidence_source_bundle.get("doc_id") or ""),
        "file_name": None,
        "inputs": masked_inputs,
        "outputs": outputs,
        "git_root": BACKEND_ROOT,
        "git_provenance": git_provenance,
        "upstream_summary": None,
        "created_at": utc_now_iso(),
        "source_stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "zone_key": zone_key,
        "stats": summary_stats,
        "run_status": run_status,
        "status": run_status,
        "file_hash": aggregate_evidence_source_bundle.get("file_hash"),
        **layout_extra,
        **post_analysis_bundle_extra(aggregate_evidence_source_bundle),
    }
    if error is not None:
        finalize_kwargs["error"] = error
    return finalize_run_summary(**finalize_kwargs)


def build_request_file_intake_run_summary(
    *,
    run_id: str,
    source_file: Path,
    request_file_intake_result: dict[str, Any],
    git_root: Path,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> dict[str, Any]:
    """Operational summary for one single-source Request File Intake execution."""
    from runtime.run_summary_safe import summary_artifact_path

    document = request_file_intake_result.get("document")
    file_hash = None
    if isinstance(document, dict) and isinstance(document.get("file_hash"), str):
        file_hash = document["file_hash"].strip() or None
    inputs = {
        "source_file": summary_artifact_path(source_file, base=git_root),
    }
    layout_extra = run_dir_layout_metadata(
        context="request",
        run_dir_layout=REQUEST_FILE_INTAKE_RUN_DIR_LAYOUT,
    )
    return finalize_run_summary(
        stage="request_file_intake",
        run_id=run_id,
        pipeline=["request_file_intake"],
        doc_id=None,
        inputs=inputs,
        outputs={
            "request_file_intake_result": "request_file_intake_result.json",
            "run_summary": "run_summary.json",
        },
        git_root=git_root,
        git_provenance=git_provenance,
        upstream_summary=None,
        created_at=utc_now_iso(),
        status="success",
        file_hash=file_hash,
        **layout_extra,
    )
