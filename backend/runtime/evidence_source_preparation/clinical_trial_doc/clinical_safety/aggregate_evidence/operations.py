# ruff: noqa: TRY004
"""Runtime operations for aggregate-evidence phase dev/debug harness runs.

Phase dev/debug harness — not a canonical runtime stage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_FILENAME,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from plugins.clinical_trial_doc.evidence_source_preparation import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.assessment_registry import (
    DEFAULT_WRITE_LLM_DEBUG_ARTIFACTS,
    normalize_assessment_profile_name,
    resolve_assessment_profile,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assemble import (
    run_assemble,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.eligibility import (
    run_eligibility,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
    run_prepare,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.results import (
    AssembleResult,
    AssessResult,
    EligibilityResult,
    PrepareResult,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stop_points import (
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_STEP,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
)
from runtime.io import load_json, save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_index import (
    build_aggregate_evidence_assemble_index_document,
    build_aggregate_evidence_assess_index_document,
    build_aggregate_evidence_eligibility_index_document,
    build_aggregate_evidence_prepare_index_document,
    resolve_index_root,
    write_run_index,
)
from runtime.run_layout import posix_relative, resolve_stage_phase_artifact_dir
from runtime.run_provenance import snapshot_git_provenance_before_run


@dataclass(frozen=True)
class RuntimeOperationReport:
    result: PrepareResult | AssessResult | EligibilityResult | AssembleResult
    messages: tuple[str, ...]


def run_assemble_operation(
    *,
    phase_dependencies: Any,
    project_root: Path,
    assessment_input: str,
    assessment_runtime_context: str,
    assessments: str,
    eligibility: str,
    output_dir: str | None,
    output_root: str | None,
    run_id: str | None,
) -> RuntimeOperationReport:
    assessment_input_path = _existing_file(assessment_input, flag="--assessment-input")
    runtime_context_path = _existing_file(
        assessment_runtime_context,
        flag="--assessment-runtime-context",
    )
    assessments_path = _existing_file(assessments, flag="--assessments")
    eligibility_path = _existing_file(eligibility, flag="--eligibility")
    assessment_payload = _load_object(assessment_input_path, label="assessment_input")
    doc_id = _required_string(assessment_payload, "doc_id")
    semantic_module_id = _resolve_harness_semantic_module_id(
        phase_dependencies=phase_dependencies,
        artifact_payload=assessment_payload,
    )
    stamp = utc_run_stamp()
    resolved_run_id = _run_id(run_id, stamp=stamp)
    out_dir, index_root = _resolve_output(
        project_root=project_root,
        phase="assemble",
        doc_id=doc_id,
        semantic_module_id=semantic_module_id,
        run_id=resolved_run_id,
        stamp=stamp,
        output_dir=output_dir,
        output_root=output_root,
    )
    result = run_assemble(
        run_assemble_phase=phase_dependencies.run_assemble_phase,
        assessment_input_path=assessment_input_path,
        assessment_runtime_context_path=runtime_context_path,
        scope_assessments_path=assessments_path,
        heading_scope_eligibility_path=eligibility_path,
        output_dir=out_dir,
        run_id=resolved_run_id,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        git_provenance=snapshot_git_provenance_before_run(root=project_root),
    )
    index_path = _write_index(
        index_root=index_root,
        step=EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_STEP,
        run_id=resolved_run_id,
        document=build_aggregate_evidence_assemble_index_document(
            bundle=assessment_payload,
            out_dir=out_dir,
            index_root=index_root,
            task_key=semantic_module_id,
        )
        if index_root is not None
        else None,
    )
    messages = [
        f"stage={EVIDENCE_SOURCE_PREPARATION_STAGE}",
        "phase=assemble",
        "operation=aggregate_evidence.assemble_aggregate_evidence_source_bundle",
        "route=aggregate",
        f"evidence_form_id={AGGREGATE_EVIDENCE_FORM_ID}",
        f"semantic_module_id={semantic_module_id}",
        f"source assessment_input: {posix_relative(assessment_input_path, project_root)}",
        f"source assessment_runtime_context: {posix_relative(runtime_context_path, project_root)}",
        f"source assessments: {posix_relative(assessments_path, project_root)}",
        f"source eligibility: {posix_relative(eligibility_path, project_root)}",
        f"run_id: {result.run_id}",
        f"aggregate_evidence_source_bundle: {result.aggregate_evidence_source_bundle_path}",
        f"input_heading_scope_count: {result.input_heading_scope_count}",
        f"assembled_heading_scope_count: {result.assembled_heading_scope_count}",
        f"auto_included_count: {result.auto_included_count}",
        f"review_ambiguous_count: {result.review_ambiguous_count}",
        f"excluded_heading_scope_count: {result.excluded_heading_scope_count}",
        f"run summary: {result.run_summary_path}",
    ]
    if index_path is not None:
        messages.append(f"Session index:           {index_path}")
    return RuntimeOperationReport(result=result, messages=tuple(messages))


def run_eligibility_operation(
    *,
    phase_dependencies: Any,
    project_root: Path,
    assessments: str,
    output_dir: str | None,
    output_root: str | None,
    run_id: str | None,
) -> RuntimeOperationReport:
    assessments_path = _existing_file(assessments, flag="--assessments")
    scope_assessments = _load_object(assessments_path, label="scope_assessments")
    doc_id = _required_string(scope_assessments, "doc_id")
    semantic_module_id = _resolve_harness_semantic_module_id(
        phase_dependencies=phase_dependencies,
        artifact_payload=scope_assessments,
    )
    stamp = utc_run_stamp()
    resolved_run_id = _run_id(run_id, stamp=stamp)
    out_dir, index_root = _resolve_output(
        project_root=project_root,
        phase="eligibility",
        doc_id=doc_id,
        semantic_module_id=semantic_module_id,
        run_id=resolved_run_id,
        stamp=stamp,
        output_dir=output_dir,
        output_root=output_root,
    )
    result = run_eligibility(
        run_evaluate_eligibility_phase=phase_dependencies.run_evaluate_eligibility_phase,
        build_heading_scope_eligibility_entries=(
            phase_dependencies.semantic_binding.build_heading_scope_eligibility_entries
        ),
        artifact_reference_root=project_root,
        scope_assessments_path=assessments_path,
        output_dir=out_dir,
        run_id=resolved_run_id,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        git_provenance=snapshot_git_provenance_before_run(root=project_root),
    )
    index_path = _write_index(
        index_root=index_root,
        step=EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
        run_id=resolved_run_id,
        document=build_aggregate_evidence_eligibility_index_document(
            bundle=scope_assessments,
            out_dir=out_dir,
            index_root=index_root,
            task_key=semantic_module_id,
        )
        if index_root is not None
        else None,
    )
    messages = [
        f"stage={EVIDENCE_SOURCE_PREPARATION_STAGE}",
        "phase=eligibility",
        "operation=aggregate_evidence.evaluate_heading_scope_eligibility",
        "route=aggregate",
        f"evidence_form_id={AGGREGATE_EVIDENCE_FORM_ID}",
        f"semantic_module_id={semantic_module_id}",
        f"source assessments: {posix_relative(assessments_path, project_root)}",
        f"output: {out_dir / HEADING_SCOPE_ELIGIBILITY_FILENAME}",
        f"run summary: {result.run_summary_path}",
        f"auto_included scopes:  {result.auto_included_scope_count}",
        f"excluded scopes:       {result.excluded_scope_count}",
        f"review_ambiguous:      {result.review_ambiguous_scope_count}",
    ]
    if index_path is not None:
        messages.append(f"Session index:           {index_path}")
    return RuntimeOperationReport(result=result, messages=tuple(messages))


def run_assess_operation(
    *,
    phase_dependencies: Any,
    project_root: Path,
    assessment_input: str,
    assessment_runtime_context: str | None,
    assessment_profile: str | None,
    llm_mode: str,
    llm_profile: str | None,
    thinking: bool | None,
    output_dir: str | None,
    output_root: str | None,
    run_id: str | None,
    no_llm_debug_artifacts: bool,
    allow_api_parse_fallback: bool,
) -> RuntimeOperationReport:
    from llm.execution_errors import APIStructuredResponseError
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assess import (
        run_assess_with_error_handling,
    )
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection import (
        build_aggregate_evidence_llm_execution,
    )

    assessment_input_path = _existing_file(assessment_input, flag="--assessment-input")
    assessment_payload = _load_object(assessment_input_path, label="assessment_input")
    profile_name = _resolve_assessment_profile(assessment_payload, assessment_profile)
    doc_id = _required_string(assessment_payload, "doc_id")
    semantic_module_id = _resolve_harness_semantic_module_id(
        phase_dependencies=phase_dependencies,
        artifact_payload=assessment_payload,
    )
    runtime_context_path = (
        _existing_file(assessment_runtime_context, flag="--assessment-runtime-context")
        if assessment_runtime_context is not None
        else None
    )
    stamp = utc_run_stamp()
    resolved_run_id = _run_id(run_id, stamp=stamp)
    out_dir, index_root = _resolve_output(
        project_root=project_root,
        phase="assess",
        doc_id=doc_id,
        semantic_module_id=semantic_module_id,
        run_id=resolved_run_id,
        stamp=stamp,
        output_dir=output_dir,
        output_root=output_root,
    )
    write_debug = DEFAULT_WRITE_LLM_DEBUG_ARTIFACTS and not no_llm_debug_artifacts
    provider = None
    llm_execution_config = None
    if llm_mode == "api":
        if llm_profile is None:
            raise ValueError("llm_profile is required for API assessment")
        resolved_execution = build_aggregate_evidence_llm_execution(
            llm_profile=llm_profile,
            thinking=thinking,
        )
        provider = resolved_execution.provider
        llm_execution_config = resolved_execution.metadata()
        print(resolved_execution.format_pre_execution_summary())
    try:
        result = run_assess_with_error_handling(
            run_assess_phase=phase_dependencies.run_assess_phase,
            assessment_input_path=assessment_input_path,
            output_dir=out_dir,
            run_id=resolved_run_id,
            evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
            assessment_profile_name=profile_name,
            llm_mode=llm_mode,
            llm_profile=(
                llm_execution_config["canonical_profile"]
                if llm_execution_config is not None
                else llm_profile
            ),
            provider=provider,
            llm_execution_config=llm_execution_config,
            allow_api_parse_fallback=allow_api_parse_fallback,
            git_provenance=snapshot_git_provenance_before_run(root=project_root),
            assessment_runtime_context_path=runtime_context_path,
        )
    except APIStructuredResponseError as exc:
        _persist_llm_debug(out_dir, exc.debug_artifacts if write_debug else None)
        raise
    debug_dir = _persist_llm_debug(
        out_dir,
        result.llm_debug_artifacts if write_debug and llm_mode == "api" else None,
    )
    summary = _load_object(result.run_summary_path, label="run_summary")
    stats = summary.get("stats") if isinstance(summary.get("stats"), dict) else {}
    index_path = None
    if result.run_status != "failed":
        index_path = _write_index(
            index_root=index_root,
            step=EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
            run_id=resolved_run_id,
            document=build_aggregate_evidence_assess_index_document(
                bundle=assessment_payload,
                out_dir=out_dir,
                index_root=index_root,
                task_key=semantic_module_id,
            )
            if index_root is not None
            else None,
        )
    messages = [
        f"stage={EVIDENCE_SOURCE_PREPARATION_STAGE}",
        "phase=assess",
        "route=aggregate",
        f"evidence_form_id={AGGREGATE_EVIDENCE_FORM_ID}",
        f"assessment_profile={profile_name}",
        f"semantic_module_id={semantic_module_id}",
        f"llm={llm_mode}",
    ]
    if llm_mode == "api":
        messages.append(
            f"llm_profile={llm_execution_config['canonical_profile']}"
            if llm_execution_config is not None
            else f"llm_profile={llm_profile}"
        )
    messages.extend(
        [
            f"assessment input: {posix_relative(assessment_input_path, project_root)}",
            "completed_operation=aggregate_evidence.assess_heading_scopes",
            f"scope assessments:     {out_dir / SCOPE_ASSESSMENTS_FILENAME}",
            f"run summary:           {out_dir / 'run_summary.json'}",
            f"scope assessments:     {result.scope_assessment_count}",
            f"scope_count:             {stats.get('scope_count')}",
            f"prompt_name:             {stats.get('prompt_name')}",
            f"prompt_version:          {stats.get('prompt_version')}",
        ]
    )
    if debug_dir is not None:
        messages.append(f"llm debug:    {debug_dir}")
    if index_path is not None:
        messages.append(f"Session index:           {index_path}")
    return RuntimeOperationReport(result=result, messages=tuple(messages))


def run_prepare_operation(
    *,
    phase_dependencies: Any,
    project_root: Path,
    routed_aggregate_bundle: str,
    coverage_bundle: str | None,
    block_manifest: str | None,
    doc_meta_bundle_path: str | None,
    analysis_bundle: str | None,
    filter_run_dirs: Sequence[str] | None,
    doc_meta_dir: str | None,
    output_dir: str | None,
    output_root: str | None,
    run_id: str | None,
    semantic_module_id: str,
) -> RuntimeOperationReport:
    routed_path = _existing_file(
        routed_aggregate_bundle,
        flag="--routed-aggregate-bundle",
    )
    from artifacts.routing.schema import ROUTING_MANIFEST_FILENAME
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare_harness_resolver import (
        resolve_prepare_harness_inputs,
    )

    routing_manifest_path = routed_path.parent / ROUTING_MANIFEST_FILENAME
    routing_manifest = load_json(routing_manifest_path)
    if not isinstance(routing_manifest, dict):
        raise ValueError("routing_manifest must be a JSON object")

    harness_inputs, discovery_message = resolve_prepare_harness_inputs(
        routing_manifest=routing_manifest,
        filter_run_dirs=filter_run_dirs,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle=analysis_bundle,
        doc_meta_dir=doc_meta_dir,
        project_root=project_root,
    )
    coverage_path = harness_inputs.coverage_bundle_path
    block_path = harness_inputs.block_manifest_path
    resolved_doc_meta_bundle_path = harness_inputs.doc_meta_bundle_path
    analysis_path = harness_inputs.analysis_bundle_path
    private_audit_path = harness_inputs.private_audit_bundle_path
    doc_id = harness_inputs.doc_id
    layout_semantic_module_id = semantic_module_id
    stamp = utc_run_stamp()
    resolved_run_id = _run_id(run_id, stamp=stamp)
    out_dir, index_root = _resolve_output(
        project_root=project_root,
        phase="prepare",
        doc_id=doc_id,
        semantic_module_id=layout_semantic_module_id,
        run_id=resolved_run_id,
        stamp=stamp,
        output_dir=output_dir,
        output_root=output_root,
    )
    result = run_prepare(
        run_prepare_phase=phase_dependencies.run_prepare_phase,
        prepare_semantic=phase_dependencies.semantic_binding.prepare,
        routed_aggregate_bundle_path=routed_path,
        routing_manifest_path=routing_manifest_path,
        coverage_bundle_path=coverage_path,
        block_manifest_path=block_path,
        doc_meta_bundle_path=resolved_doc_meta_bundle_path,
        analysis_bundle_path=analysis_path,
        private_audit_bundle_path=private_audit_path,
        output_dir=out_dir,
        run_id=resolved_run_id,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        git_provenance=snapshot_git_provenance_before_run(root=project_root),
        projection_input_refs=harness_inputs.projection_input_refs,
        projected_coverage_by_filter_job=harness_inputs.projected_coverage_by_filter_job,
        filter_job_coverage_refs=harness_inputs.filter_job_coverage_refs,
        semantic_module_id=semantic_module_id,
        route_counts=dict(routing_manifest.get("route_counts") or {}),
    )
    analysis_payload = _load_object(analysis_path, label="analysis_bundle")
    index_path = _write_index(
        index_root=index_root,
        step=EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
        run_id=resolved_run_id,
        document=build_aggregate_evidence_prepare_index_document(
            bundle=analysis_payload,
            out_dir=out_dir,
            index_root=index_root,
            task_key=layout_semantic_module_id,
        )
        if index_root is not None
        else None,
    )
    messages: list[str] = []
    if discovery_message:
        messages.append(discovery_message)
    messages.extend(
        [
            f"stage={EVIDENCE_SOURCE_PREPARATION_STAGE}",
            "phase=prepare",
            "route=aggregate",
            f"evidence_form_id={AGGREGATE_EVIDENCE_FORM_ID}",
            f"semantic_module_id={layout_semantic_module_id}",
            f"output dir:              {out_dir}",
            f"assessment input:        {out_dir / 'assessment_input.json'}",
            f"assessment preview:      {out_dir / 'assessment_input_preview.json'}",
        ]
    )
    messages.extend(
        [
            f"unit integrity report:   {out_dir / 'unit_integrity_report.json'}",
            f"run summary:             {out_dir / 'run_summary.json'}",
            f"aggregate_units:         {result.aggregate_unit_count}",
            f"run_id:                  {result.run_id}",
        ]
    )
    if index_path is not None:
        messages.append(f"Session index:           {index_path}")
    return RuntimeOperationReport(result=result, messages=tuple(messages))


def _resolve_assessment_profile(payload: dict[str, Any], override: str | None) -> str:
    if override is not None:
        return resolve_assessment_profile(override)
    if "tag_profile_ref" in payload:
        raise ValueError("assessment input must use assessment_profile_ref")
    profile_ref = payload.get("assessment_profile_ref")
    if not isinstance(profile_ref, str) or not profile_ref.strip():
        raise ValueError("assessment input missing assessment_profile_ref")
    return resolve_assessment_profile(normalize_assessment_profile_name(profile_ref))


def _write_llm_debug_artifact_files(debug_dir: Path, artifacts: dict[str, Any]) -> None:
    save_json(debug_dir / "llm_messages.json", artifacts["llm_messages"])
    (debug_dir / "prompt.txt").write_text(artifacts["prompt_txt"], encoding="utf-8")
    (debug_dir / "raw_text.txt").write_text(artifacts["raw_text"], encoding="utf-8")
    (debug_dir / "parse_error.txt").write_text(
        artifacts.get("parse_error") or "",
        encoding="utf-8",
    )
    save_json(debug_dir / "run_metadata.json", artifacts["run_metadata"])


def _persist_llm_debug(out_dir: Path, artifacts: dict[str, Any] | None) -> Path | None:
    if artifacts is None:
        return None
    debug_dir = out_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    _write_llm_debug_artifact_files(debug_dir, artifacts)
    trace = artifacts.get("scope_assessment_trace")
    if isinstance(trace, dict):
        save_json(debug_dir / "scope_assessment_trace.json", trace)
    return debug_dir


def _resolve_harness_semantic_module_id(
    *,
    phase_dependencies: Any,
    artifact_payload: dict[str, Any] | None = None,
) -> str:
    installed = str(phase_dependencies.semantic_module_id or "").strip()
    if not installed:
        raise ValueError("installed semantic_module_id is required for harness layout")
    from_artifact: str | None = None
    if artifact_payload is not None:
        candidate = str(artifact_payload.get("semantic_module_id") or "").strip()
        if candidate:
            from_artifact = candidate
    if from_artifact is not None and from_artifact != installed:
        raise ValueError(
            "semantic_module_id mismatch between artifact and installation: "
            f"artifact={from_artifact!r} installed={installed!r}"
        )
    return from_artifact or installed


def _resolve_output(
    *,
    project_root: Path,
    phase: str,
    doc_id: str,
    semantic_module_id: str,
    run_id: str,
    stamp: Any,
    output_dir: str | None,
    output_root: str | None,
) -> tuple[Path, Path | None]:
    if output_dir is not None:
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir, resolve_index_root(
            session_dir=(
                project_root / "runs" / EVIDENCE_SOURCE_PREPARATION_STAGE / "_session"
            ),
            custom_output_dir=out_dir,
        )
    return resolve_stage_phase_artifact_dir(
        project_root=project_root,
        stage=EVIDENCE_SOURCE_PREPARATION_STAGE,
        zone_key=semantic_module_id,
        doc_id=doc_id,
        run_id=run_id,
        stamp=stamp,
        phase=phase,
        output_root=Path(output_root).resolve() if output_root is not None else None,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )


def _write_index(
    *, index_root: Path | None, step: str, run_id: str, document: Any
) -> Path | None:
    if index_root is None or document is None:
        return None
    return write_run_index(index_root, step=step, documents=[document], run_id=run_id)


def _run_id(provided: str | None, *, stamp: Any) -> str:
    if provided is not None and provided.strip():
        return provided.strip()
    return format_run_timestamp(stamp)


def _existing_file(value: str, *, flag: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f"{flag} must point to an existing file: {path}")
    return path


def _existing_dir(value: str, *, flag: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir():
        raise ValueError(f"{flag} must point to an existing directory: {path}")
    return path


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()
