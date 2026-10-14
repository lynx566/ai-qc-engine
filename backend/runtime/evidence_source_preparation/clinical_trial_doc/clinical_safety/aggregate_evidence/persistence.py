"""Persist Aggregate Evidence executions to canonical run artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_prepare_integrity import (
    UNIT_INTEGRITY_REPORT_FILENAME,
    compact_unit_integrity_summary,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
    ASSESSMENT_INPUT_FILENAME,
    ASSESSMENT_INPUT_PREVIEW_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_review import (
    SCOPE_ASSESSMENT_REVIEW_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENT_TRACE_FILENAME,
    SCOPE_ASSESSMENTS_FILENAME,
)
from llm.invocation import serialize_llm_invocations
from operations.evidence_source_preparation.stage import (
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    ASSEMBLE_AGGREGATE_EVIDENCE_SOURCE_BUNDLE_OPERATION,
    ASSESS_HEADING_SCOPES_OPERATION,
    EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceAssemblyExecution,
    AggregateEvidenceAssessmentExecution,
    AggregateEvidenceEligibilityExecution,
    AggregateEvidenceExecution,
    AggregateEvidencePrepareExecution,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.results import (
    AssembleResult,
    AssessResult,
    EligibilityResult,
    PrepareResult,
)
from runtime.io import save_json
from runtime.run_summaries import (
    build_aggregate_evidence_assemble_run_summary,
    build_aggregate_evidence_assess_run_summary,
    build_aggregate_evidence_eligibility_run_summary,
    build_aggregate_evidence_prepare_run_summary,
)


def _resolve_raw_audit_source(
    *,
    private_audit_bundle: dict[str, Any] | None,
) -> str:
    if private_audit_bundle is not None:
        return "prepare_analysis_private_audit_bundle"
    return "analysis_bundle_fallback"


def _run_summary_filter_job_coverage_refs(
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference],
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "filter_job_id": ref.filter_job_id,
            "coverage_bundle": ref.coverage_bundle_path.as_posix(),
        }
        for ref in filter_job_coverage_refs
    )


def _run_summary_projection_input_refs(
    projection_input_refs: Sequence[ProjectionInputRefRecord],
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "filter_job_id": ref.filter_job_id,
            "zone_key": ref.zone_key,
            "filter_output_projection_bundle_id": ref.filter_output_projection_bundle_id,
        }
        for ref in projection_input_refs
    )


def _validate_persist_coverage_bundle_path(
    *,
    coverage_bundle_path: Path | None,
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference] | None,
) -> None:
    fan_in = bool(filter_job_coverage_refs)
    if fan_in:
        if coverage_bundle_path is not None:
            raise ValueError(
                "coverage_bundle_path must be None when filter_job_coverage_refs "
                "is provided for projected fan-in prepare persistence"
            )
        return
    if coverage_bundle_path is None:
        raise ValueError(
            "coverage_bundle_path is required for single-source prepare persistence"
        )


def persist_prepare_execution(
    *,
    execution: AggregateEvidencePrepareExecution,
    output_dir: Path | str,
    run_id: str,
    coverage_bundle_path: Path | None,
    block_manifest_path: Path,
    doc_meta_bundle_path: Path,
    analysis_bundle_path: Path,
    routed_aggregate_bundle_path: Path,
    routing_manifest_path: Path,
    private_audit_bundle_path: Path | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    private_audit_bundle: dict[str, Any] | None = None,
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference] | None = None,
    projection_input_refs: Sequence[ProjectionInputRefRecord] | None = None,
) -> PrepareResult:
    _validate_persist_coverage_bundle_path(
        coverage_bundle_path=coverage_bundle_path,
        filter_job_coverage_refs=filter_job_coverage_refs,
    )
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    assessment_input_path = out_dir / ASSESSMENT_INPUT_FILENAME
    runtime_context_path = out_dir / ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    preview_path = out_dir / ASSESSMENT_INPUT_PREVIEW_FILENAME
    summary_path = out_dir / "run_summary.json"

    save_json(assessment_input_path, execution.assessment_input)
    save_json(runtime_context_path, execution.assessment_runtime_context)
    save_json(preview_path, execution.assessment_input_preview)

    unit_integrity_report_path = out_dir / UNIT_INTEGRITY_REPORT_FILENAME
    save_json(unit_integrity_report_path, execution.unit_integrity_report)

    fan_in_coverage_refs = (
        _run_summary_filter_job_coverage_refs(filter_job_coverage_refs)
        if filter_job_coverage_refs
        else None
    )
    fan_in_projection_refs = (
        _run_summary_projection_input_refs(projection_input_refs)
        if projection_input_refs
        else None
    )

    summary = build_aggregate_evidence_prepare_run_summary(
        run_id=run_id,
        doc_id=execution.doc_id,
        zone_key=execution.zone_key,
        coverage_bundle_path=(
            None if fan_in_coverage_refs else coverage_bundle_path
        ),
        filter_job_coverage_refs=fan_in_coverage_refs,
        projection_input_refs=fan_in_projection_refs,
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        routed_aggregate_bundle_path=routed_aggregate_bundle_path,
        routing_manifest_path=routing_manifest_path,
        private_audit_bundle_path=private_audit_bundle_path,
        raw_audit_source=_resolve_raw_audit_source(
            private_audit_bundle=private_audit_bundle,
        ),
        assessment_input_path=assessment_input_path,
        assessment_input_preview_path=preview_path,
        assessment_input=execution.assessment_input,
        assessment_runtime_context=execution.assessment_runtime_context,
        git_provenance=git_provenance,
        unit_integrity_status=str(execution.unit_integrity_report.get("status") or "pass"),
        unit_integrity_summary=compact_unit_integrity_summary(execution.unit_integrity_report),
        unit_integrity_report_path=unit_integrity_report_path,
        aggregate_unit_count=execution.aggregate_unit_count,
        assessment_runtime_context_path=runtime_context_path,
    )
    save_json(summary_path, summary)

    return PrepareResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=execution.doc_id,
        zone_key=execution.zone_key,
        assessment_input_path=assessment_input_path,
        unit_integrity_report_path=unit_integrity_report_path,
        run_summary_path=summary_path,
        aggregate_unit_count=execution.aggregate_unit_count,
    )


def persist_assess_execution(
    *,
    execution: AggregateEvidenceAssessmentExecution,
    output_dir: Path | str,
    run_id: str,
    assessment_input: dict[str, Any],
    assessment_input_path: Path,
    llm_mode: str,
    effective_llm_execution: dict[str, Any] | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> AssessResult:
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    scope_assessments_path = out_dir / SCOPE_ASSESSMENTS_FILENAME
    scope_assessment_review_path: Path | None = None
    scope_assessment_trace_path: Path | None = None
    summary_path = out_dir / "run_summary.json"

    save_json(scope_assessments_path, execution.scope_assessments)
    if execution.scope_assessment_review is not None:
        scope_assessment_review_path = out_dir / SCOPE_ASSESSMENT_REVIEW_FILENAME
        save_json(scope_assessment_review_path, execution.scope_assessment_review)
    if execution.scope_assessment_trace is not None:
        scope_assessment_trace_path = out_dir / SCOPE_ASSESSMENT_TRACE_FILENAME
        save_json(scope_assessment_trace_path, execution.scope_assessment_trace)

    doc_id = str(assessment_input.get("doc_id") or "")
    zone_key = str(assessment_input.get("zone_key") or "")

    summary = build_aggregate_evidence_assess_run_summary(
        run_id=run_id,
        assessment_input=assessment_input,
        assessment_input_path=assessment_input_path,
        scope_assessments_path=scope_assessments_path,
        scope_assessments=execution.scope_assessments,
        scope_assessment_review_path=scope_assessment_review_path,
        scope_assessment_review=execution.scope_assessment_review,
        scope_assessment_trace_path=scope_assessment_trace_path,
        assessment_profile_name=execution.profile_name,
        llm_mode=llm_mode,
        zone_key=zone_key,
        phase=EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
        completed_operation=ASSESS_HEADING_SCOPES_OPERATION,
        git_provenance=git_provenance,
        llm_execution=effective_llm_execution,
        run_status=execution.run_status,
        scope_assessment_trace=execution.scope_assessment_trace,
        llm_invocations=serialize_llm_invocations(execution.llm_invocations),
    )
    save_json(summary_path, summary)

    return AssessResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=doc_id,
        zone_key=zone_key,
        scope_assessments_path=scope_assessments_path,
        scope_assessment_review_path=scope_assessment_review_path,
        scope_assessment_trace_path=scope_assessment_trace_path,
        run_summary_path=summary_path,
        scope_assessment_count=execution.scope_assessment_count,
        run_status=execution.run_status,
        llm_debug_artifacts=execution.llm_debug_artifacts,
    )


def persist_eligibility_execution(
    *,
    execution: AggregateEvidenceEligibilityExecution,
    output_dir: Path | str,
    run_id: str,
    scope_assessments_path: Path,
    scope_assessments: dict[str, Any],
    git_provenance: dict[str, str | bool | None] | None = None,
) -> EligibilityResult:
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    heading_scope_eligibility_path = out_dir / HEADING_SCOPE_ELIGIBILITY_FILENAME
    summary_path = out_dir / "run_summary.json"

    save_json(heading_scope_eligibility_path, execution.heading_scope_eligibility)

    doc_id = str(scope_assessments.get("doc_id") or "")
    zone_key = str(scope_assessments.get("zone_key") or "")

    summary = build_aggregate_evidence_eligibility_run_summary(
        run_id=run_id,
        scope_assessments_path=scope_assessments_path,
        scope_assessments=scope_assessments,
        heading_scope_eligibility_path=heading_scope_eligibility_path,
        heading_scope_eligibility=execution.heading_scope_eligibility,
        zone_key=zone_key,
        phase=EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE,
        completed_operation=EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION,
        git_provenance=git_provenance,
        run_status="success",
    )
    save_json(summary_path, summary)

    return EligibilityResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=doc_id,
        zone_key=zone_key,
        heading_scope_eligibility_path=heading_scope_eligibility_path,
        run_summary_path=summary_path,
        source_scope_assessments_path=scope_assessments_path.resolve(),
        auto_included_scope_count=execution.auto_included_scope_count,
        excluded_scope_count=execution.excluded_scope_count,
        review_ambiguous_scope_count=execution.review_ambiguous_scope_count,
    )


def persist_assemble_execution(
    *,
    execution: AggregateEvidenceAssemblyExecution,
    output_dir: Path | str,
    run_id: str,
    assessment_input_path: Path,
    assessment_runtime_context_path: Path,
    scope_assessments_path: Path,
    heading_scope_eligibility_path: Path,
    doc_id: str,
    zone_key: str,
    phase: str,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> AssembleResult:
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    aggregate_evidence_source_bundle_path = out_dir / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    summary_path = out_dir / "run_summary.json"

    aggregate_evidence_source_bundle = execution.aggregate_evidence_source_bundle
    save_json(aggregate_evidence_source_bundle_path, aggregate_evidence_source_bundle)

    summary = build_aggregate_evidence_assemble_run_summary(
        run_id=run_id,
        assessment_input_path=assessment_input_path,
        assessment_runtime_context_path=assessment_runtime_context_path,
        scope_assessments_path=scope_assessments_path,
        heading_scope_eligibility_path=heading_scope_eligibility_path,
        aggregate_evidence_source_bundle_path=aggregate_evidence_source_bundle_path,
        aggregate_evidence_source_bundle=aggregate_evidence_source_bundle,
        stats=execution.stats,
        zone_key=zone_key,
        phase=phase,
        completed_operation=ASSEMBLE_AGGREGATE_EVIDENCE_SOURCE_BUNDLE_OPERATION,
        git_provenance=git_provenance,
        run_status="success",
    )
    save_json(summary_path, summary)

    stats = execution.stats
    return AssembleResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=doc_id,
        zone_key=zone_key,
        aggregate_evidence_source_bundle_path=aggregate_evidence_source_bundle_path,
        run_summary_path=summary_path,
        input_heading_scope_count=stats.input_heading_scope_count,
        assembled_heading_scope_count=stats.assembled_heading_scope_count,
        auto_included_count=stats.auto_included_count,
        review_ambiguous_count=stats.review_ambiguous_count,
        excluded_heading_scope_count=stats.excluded_heading_scope_count,
    )


@dataclass(frozen=True)
class UnifiedExecutionPersistResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    assessment_input_path: Path
    assessment_runtime_context_path: Path
    scope_assessments_path: Path
    heading_scope_eligibility_path: Path
    aggregate_evidence_source_bundle_path: Path
    run_summary_path: Path


def persist_unified_aggregate_evidence_execution(
    *,
    execution: AggregateEvidenceExecution,
    output_dir: Path | str,
    run_id: str,
    coverage_bundle_path: Path | None,
    block_manifest_path: Path,
    doc_meta_bundle_path: Path,
    analysis_bundle_path: Path,
    routed_aggregate_bundle_path: Path,
    routing_manifest_path: Path,
    private_audit_bundle_path: Path | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
    llm_mode: str = "mock",
    private_audit_bundle: dict[str, Any] | None = None,
    filter_job_coverage_refs: Sequence[FilterJobCoverageReference] | None = None,
    projection_input_refs: Sequence[ProjectionInputRefRecord] | None = None,
) -> UnifiedExecutionPersistResult:
    """Persist one unified aggregate ESP execution to a single output directory."""

    _validate_persist_coverage_bundle_path(
        coverage_bundle_path=coverage_bundle_path,
        filter_job_coverage_refs=filter_job_coverage_refs,
    )
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prepare_execution = execution.prepare
    assess_execution = execution.assess
    eligibility_execution = execution.eligibility
    assemble_execution = execution.assemble

    assessment_input_path = out_dir / ASSESSMENT_INPUT_FILENAME
    runtime_context_path = out_dir / ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    preview_path = out_dir / ASSESSMENT_INPUT_PREVIEW_FILENAME
    unit_integrity_report_path = out_dir / UNIT_INTEGRITY_REPORT_FILENAME
    scope_assessments_path = out_dir / SCOPE_ASSESSMENTS_FILENAME
    heading_scope_eligibility_path = out_dir / HEADING_SCOPE_ELIGIBILITY_FILENAME
    aggregate_evidence_source_bundle_path = (
        out_dir / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    )
    summary_path = out_dir / "run_summary.json"

    save_json(assessment_input_path, prepare_execution.assessment_input)
    save_json(runtime_context_path, prepare_execution.assessment_runtime_context)
    save_json(preview_path, prepare_execution.assessment_input_preview)
    save_json(unit_integrity_report_path, prepare_execution.unit_integrity_report)
    save_json(scope_assessments_path, assess_execution.scope_assessments)
    save_json(
        heading_scope_eligibility_path,
        eligibility_execution.heading_scope_eligibility,
    )
    save_json(
        aggregate_evidence_source_bundle_path,
        assemble_execution.aggregate_evidence_source_bundle,
    )

    scope_assessment_review_path: Path | None = None
    scope_assessment_trace_path: Path | None = None

    if assess_execution.scope_assessment_review is not None:
        scope_assessment_review_path = out_dir / SCOPE_ASSESSMENT_REVIEW_FILENAME
        save_json(
            scope_assessment_review_path,
            assess_execution.scope_assessment_review,
        )
    if assess_execution.scope_assessment_trace is not None:
        scope_assessment_trace_path = out_dir / SCOPE_ASSESSMENT_TRACE_FILENAME
        save_json(scope_assessment_trace_path, assess_execution.scope_assessment_trace)

    fan_in_coverage_refs = (
        _run_summary_filter_job_coverage_refs(filter_job_coverage_refs)
        if filter_job_coverage_refs
        else None
    )
    fan_in_projection_refs = (
        _run_summary_projection_input_refs(projection_input_refs)
        if projection_input_refs
        else None
    )

    _ = build_aggregate_evidence_prepare_run_summary(
        run_id=run_id,
        doc_id=prepare_execution.doc_id,
        zone_key=prepare_execution.zone_key,
        coverage_bundle_path=(
            None if fan_in_coverage_refs else coverage_bundle_path
        ),
        filter_job_coverage_refs=fan_in_coverage_refs,
        projection_input_refs=fan_in_projection_refs,
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        routed_aggregate_bundle_path=routed_aggregate_bundle_path,
        routing_manifest_path=routing_manifest_path,
        private_audit_bundle_path=private_audit_bundle_path,
        raw_audit_source=_resolve_raw_audit_source(
            private_audit_bundle=private_audit_bundle,
        ),
        assessment_input_path=assessment_input_path,
        assessment_input_preview_path=preview_path,
        assessment_input=prepare_execution.assessment_input,
        assessment_runtime_context=prepare_execution.assessment_runtime_context,
        git_provenance=git_provenance,
        unit_integrity_status=str(
            prepare_execution.unit_integrity_report.get("status") or "pass"
        ),
        unit_integrity_summary=compact_unit_integrity_summary(
            prepare_execution.unit_integrity_report
        ),
        unit_integrity_report_path=unit_integrity_report_path,
        aggregate_unit_count=prepare_execution.aggregate_unit_count,
        assessment_runtime_context_path=runtime_context_path,
    )
    _ = build_aggregate_evidence_assess_run_summary(
        run_id=run_id,
        assessment_input=prepare_execution.assessment_input,
        assessment_input_path=assessment_input_path,
        scope_assessments_path=scope_assessments_path,
        scope_assessments=assess_execution.scope_assessments,
        scope_assessment_review_path=scope_assessment_review_path,
        scope_assessment_review=assess_execution.scope_assessment_review,
        scope_assessment_trace_path=scope_assessment_trace_path,
        assessment_profile_name=assess_execution.profile_name,
        llm_mode=llm_mode,
        zone_key=prepare_execution.zone_key,
        phase=EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
        completed_operation=ASSESS_HEADING_SCOPES_OPERATION,
        git_provenance=git_provenance,
        llm_execution=None,
        run_status=assess_execution.run_status,
        scope_assessment_trace=assess_execution.scope_assessment_trace,
        llm_invocations=serialize_llm_invocations(
            assess_execution.llm_invocations
        ),
    )
    _ = build_aggregate_evidence_eligibility_run_summary(
        run_id=run_id,
        scope_assessments_path=scope_assessments_path,
        scope_assessments=assess_execution.scope_assessments,
        heading_scope_eligibility_path=heading_scope_eligibility_path,
        heading_scope_eligibility=eligibility_execution.heading_scope_eligibility,
        zone_key=prepare_execution.zone_key,
        phase=EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE,
        completed_operation=EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION,
        git_provenance=git_provenance,
        run_status="success",
    )
    summary = build_aggregate_evidence_assemble_run_summary(
        run_id=run_id,
        assessment_input_path=assessment_input_path,
        assessment_runtime_context_path=runtime_context_path,
        scope_assessments_path=scope_assessments_path,
        heading_scope_eligibility_path=heading_scope_eligibility_path,
        aggregate_evidence_source_bundle_path=aggregate_evidence_source_bundle_path,
        aggregate_evidence_source_bundle=(
            assemble_execution.aggregate_evidence_source_bundle
        ),
        stats=assemble_execution.stats,
        zone_key=prepare_execution.zone_key,
        phase=EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE,
        completed_operation=ASSEMBLE_AGGREGATE_EVIDENCE_SOURCE_BUNDLE_OPERATION,
        git_provenance=git_provenance,
        run_status="success",
    )
    summary["llm_invocations"] = serialize_llm_invocations(
        assess_execution.llm_invocations
    )
    save_json(summary_path, summary)

    return UnifiedExecutionPersistResult(
        output_dir=out_dir,
        run_id=run_id,
        doc_id=prepare_execution.doc_id,
        zone_key=prepare_execution.zone_key,
        assessment_input_path=assessment_input_path,
        assessment_runtime_context_path=runtime_context_path,
        scope_assessments_path=scope_assessments_path,
        heading_scope_eligibility_path=heading_scope_eligibility_path,
        aggregate_evidence_source_bundle_path=aggregate_evidence_source_bundle_path,
        run_summary_path=summary_path,
    )
