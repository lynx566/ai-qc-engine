"""Production CLI entry for the installed Document Consistency QC flow.

``main()`` runs the clinical-trial installed application composition through
Evidence Comparison. Programmatic callers can use the installed
prepare/allocate and execute-prepared application boundaries.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))

from application import (
    build_installed_document_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc import (
    execute_prepared_installed_clinical_trial_document_consistency_qc,
    prepare_and_allocate_installed_clinical_trial_document_consistency_qc,
)
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from execution_flow.document_consistency_qc import (
    CandidateScopeDecisionMode,
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcFlowReport,
    DocumentConsistencyQcParticipantRunInput,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolutionStatus,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from runtime.request_file_intake import (
    RequestFileIntakeOperationReport,
    run_request_file_intake_operation,
)

PrepareRequestOptionsLoader = Callable[[Path | None], PrepareAnalysisRequestOptions]

CURRENT_SOURCE_LANGUAGE_CHOICES = ("zh",)

_FLOW_STAGE_DESCRIPTION = (
    "Input → Intake → Extract → Prepare Analysis → Doc Meta → Filter "
    "→ Filter Output Projection → Route → Evidence Source Preparation "
    "→ Evidence Comparison"
)


def _resolve_project_root(value: str | None) -> Path:
    if value is None:
        return DEFAULT_PROJECT_ROOT
    return Path(value).resolve()


def _resolve_source_path(path: str) -> Path:
    """Resolve source arguments using the caller's working directory."""
    return Path(path).resolve()


def _validate_args(
    args: argparse.Namespace,
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> None:
    slot_count = len(capability_config.slots)
    has_source = args.source is not None
    has_source_a = args.source_a is not None
    has_source_b = args.source_b is not None
    has_privacy = args.privacy_config is not None
    has_privacy_a = args.privacy_config_a is not None
    has_privacy_b = args.privacy_config_b is not None

    if slot_count == 1:
        if has_source_a or has_source_b or has_privacy_a or has_privacy_b:
            raise SystemExit(
                "selected capability requires one participant input set; "
                "do not pass suffixed participant arguments."
            )
        if not has_source:
            raise SystemExit("selected capability requires --source.")
        return

    if slot_count == 2:
        if has_source or has_privacy:
            raise SystemExit(
                "selected capability requires two participant input sets; "
                "do not pass unsuffixed participant arguments."
            )
        missing: list[str] = []
        if not has_source_a:
            missing.append("--source-a")
        if not has_source_b:
            missing.append("--source-b")
        if missing:
            raise SystemExit(
                "selected capability requires " + " and ".join(missing) + "."
            )
        if has_privacy_a and not has_privacy_b:
            raise SystemExit(
                "two-slot capabilities require both --privacy-config-a and "
                "--privacy-config-b when supplying privacy configuration; "
                "omit both for identity/raw Prepare."
            )
        if has_privacy_b and not has_privacy_a:
            raise SystemExit(
                "two-slot capabilities require both --privacy-config-a and "
                "--privacy-config-b when supplying privacy configuration; "
                "omit both for identity/raw Prepare."
            )
        return

    raise SystemExit(
        f"selected capability has unsupported participant-slot count: {slot_count}"
    )


def _build_uploads(
    args: argparse.Namespace,
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> dict[str, Path]:
    slots = capability_config.slots
    if len(slots) == 1:
        return {
            slots[0].slot_id: _resolve_source_path(args.source),
        }

    if len(slots) != 2:
        raise ValueError("participant-slot count must be one or two")
    return {
        slots[0].slot_id: _resolve_source_path(args.source_a),
        slots[1].slot_id: _resolve_source_path(args.source_b),
    }


def _build_participant_privacy_paths(
    args: argparse.Namespace,
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
) -> dict[str, Path | None]:
    slots = capability_config.slots
    if len(slots) == 1:
        privacy_path = Path(args.privacy_config) if args.privacy_config else None
        return {slots[0].slot_id: privacy_path}

    if len(slots) != 2:
        raise ValueError("participant-slot count must be one or two")
    privacy_a = Path(args.privacy_config_a) if args.privacy_config_a else None
    privacy_b = Path(args.privacy_config_b) if args.privacy_config_b else None
    return {
        slots[0].slot_id: privacy_a,
        slots[1].slot_id: privacy_b,
    }


def _build_participant_inputs(
    args: argparse.Namespace,
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    load_prepare_request_options: PrepareRequestOptionsLoader,
) -> dict[str, DocumentConsistencyQcParticipantRunInput]:
    slots = capability_config.slots
    if len(slots) == 1:
        privacy_path = Path(args.privacy_config) if args.privacy_config else None
        return {
            slots[0].slot_id: DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=load_prepare_request_options(
                    privacy_path
                ),
            )
        }

    if len(slots) != 2:
        raise ValueError("participant-slot count must be one or two")
    privacy_a = Path(args.privacy_config_a) if args.privacy_config_a else None
    privacy_b = Path(args.privacy_config_b) if args.privacy_config_b else None
    return {
        slots[0].slot_id: DocumentConsistencyQcParticipantRunInput(
            prepare_analysis_request_options=load_prepare_request_options(privacy_a),
        ),
        slots[1].slot_id: DocumentConsistencyQcParticipantRunInput(
            prepare_analysis_request_options=load_prepare_request_options(privacy_b),
        ),
    }


def _intake_file_hash(intake_report: Any) -> str | None:
    document = intake_report.result.request_file_intake_result.get("document")
    if not isinstance(document, Mapping):
        return None
    file_hash = document.get("file_hash")
    return file_hash if isinstance(file_hash, str) else None


def _intake_original_file_name(intake_report: Any) -> str | None:
    document = intake_report.result.request_file_intake_result.get("document")
    if not isinstance(document, Mapping):
        return None
    original_file_name = document.get("original_file_name")
    return original_file_name if isinstance(original_file_name, str) else None


def _print_section(title: str) -> None:
    print(f"--- {title} ---")


def _print_input(*, source_path: Path, slot_id: str) -> None:
    _print_section("Input")
    print(f"slot_id: {slot_id}")
    print(f"source: {source_path.as_posix()}")


def _print_intake(intake_report: Any) -> None:
    _print_section("Intake")
    print(f"run_id: {intake_report.result.run_id}")
    file_hash = _intake_file_hash(intake_report)
    if file_hash is not None:
        print(f"file_hash: {file_hash}")
    original_file_name = _intake_original_file_name(intake_report)
    if original_file_name is not None:
        print(f"original_file_name: {original_file_name}")
    print(f"output_dir: {intake_report.result.output_dir.as_posix()}")
    print(f"run_summary: {intake_report.result.run_summary_path.as_posix()}")


def _print_processing_identity(identity: Any) -> None:
    _print_section("Processing identity")
    print(f"doc_id: {identity.doc_id}")
    print(f"file_hash: {identity.file_hash}")
    print(f"file_name: {identity.file_name}")
    print(f"display_name: {identity.display_name}")


def _print_extract(extract_report: Any) -> None:
    bundle = extract_report.result.document.bundle
    _print_section("Extract")
    print(f"run_id: {extract_report.result.run_id}")
    print(f"source_type: {bundle.source_type}")
    print(f"output_dir: {extract_report.result.output_dir.as_posix()}")
    print(f"bundle: {extract_report.result.document.bundle_path.as_posix()}")
    print(f"run_summary: {extract_report.result.document.run_summary_path.as_posix()}")


def _print_prepare_analysis(prepare_analysis_report: Any) -> None:
    document = prepare_analysis_report.documents[0]
    _print_section("Prepare Analysis")
    print(f"run_id: {document.run_id}")
    if document.paths is not None:
        print(f"analysis_bundle: {document.paths.analysis_bundle.as_posix()}")
        print(f"block_manifest: {document.paths.block_manifest.as_posix()}")
        print(f"run_summary: {document.paths.run_summary.as_posix()}")


def _print_doc_meta(doc_meta_report: Any) -> None:
    _print_section("Doc Meta")
    print(f"output_dir: {doc_meta_report['output_dir']}")
    print(f"doc_meta_bundle: {doc_meta_report['doc_meta_bundle_path']}")
    print(f"context_preview: {doc_meta_report['document_context_preview_path']}")
    print(f"run_summary: {doc_meta_report['run_summary_path']}")


def _print_filter_job(filter_job: Any) -> None:
    _print_section(f"Filter ({filter_job.filter_job_id})")
    print(f"zone_config_name: {filter_job.zone_config_name}")
    print(f"output_dir: {filter_job.stage_result.output_dir.as_posix()}")
    print(f"zone_match_bundle: {filter_job.stage_result.zone_bundle_path.as_posix()}")
    print(f"coverage_bundle: {filter_job.stage_result.coverage_bundle_path.as_posix()}")
    print(f"run_summary: {filter_job.stage_result.run_summary_path.as_posix()}")


def _print_projection_job(projection_job: Any) -> None:
    _print_section(f"Filter Output Projection ({projection_job.filter_job_id})")
    stage = projection_job.stage_result
    print(f"run_id: {stage.run_id}")
    print(f"output_dir: {stage.output_dir.as_posix()}")
    print(f"projection_bundle: {stage.projection_bundle_path.as_posix()}")
    print(f"projected_source_count: {len(stage.step_result.projected_sources)}")
    print(f"semantic_outcome_count: {len(stage.step_result.semantic_outcomes)}")
    print(f"run_summary: {stage.run_summary_path.as_posix()}")


def _print_route_semantic_module(route_module: Any) -> None:
    _print_section(f"Route ({route_module.semantic_module_id})")
    print(
        f"selected_projected_source_count: {route_module.selected_projected_source_count}"
    )
    print(f"route_invoked: {route_module.route_invoked}")
    if route_module.stage_result is not None:
        stage = route_module.stage_result
        print(f"run_id: {stage.run_id}")
        print(f"output_dir: {stage.output_dir.as_posix()}")
        print(f"routing_manifest: {stage.routing_manifest_path.as_posix()}")
        aggregate_path = stage.routed_bundle_paths.get("aggregate")
        if aggregate_path is not None:
            print(f"routed_units_aggregate: {aggregate_path.as_posix()}")
        print(f"run_summary: {stage.run_summary_path.as_posix()}")
    _print_evidence_source_preparation(route_module)


def _print_evidence_source_preparation(route_module: Any) -> None:
    print(
        "evidence_source_preparation_invoked: "
        f"{route_module.evidence_source_preparation_invoked}"
    )
    esp_stage = route_module.evidence_source_preparation_stage_result
    if esp_stage is None:
        return
    _print_section(f"Evidence Source Preparation ({route_module.semantic_module_id})")
    print(f"run_id: {esp_stage.run_id}")
    print(f"stage_executor_id: {esp_stage.stage_executor_id}")
    print(f"output_dir: {esp_stage.output_dir.as_posix()}")
    print(f"declared_output: {esp_stage.declared_output_path.as_posix()}")
    print(f"run_summary: {esp_stage.run_summary_path.as_posix()}")


def _count_declared_job_final_findings(
    declared_output_path: Path | None,
) -> int | None:
    if declared_output_path is None:
        return None
    path = declared_output_path.resolve()
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return None
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return None
    total = 0
    for job in jobs:
        if isinstance(job, Mapping):
            findings = job.get("findings")
            if isinstance(findings, list):
                total += len(findings)
    return total


def _print_evidence_comparison(*, report: DocumentConsistencyQcFlowReport) -> None:
    _print_section("Evidence Comparison")
    handoff = report.result.evidence_comparison_handoff_resolution
    print(f"handoff_status: {handoff.status.value}")

    stage_result = report.result.evidence_comparison_stage_result
    if (
        handoff.status is not EvidenceComparisonHandoffResolutionStatus.READY
        or stage_result is None
    ):
        print("run_status: (not run)")
        print("job_final_finding_count: (not run)")
        print("declared_output_path: (none)")
        print("output_dir: (none)")
        return

    print(f"run_status: {stage_result.run_status}")
    declared_output_path = stage_result.declared_output_path
    if declared_output_path is None:
        print("declared_output_path: (none)")
        print("job_final_finding_count: (none)")
    else:
        print(f"declared_output_path: {declared_output_path.as_posix()}")
        finding_count = _count_declared_job_final_findings(declared_output_path)
        if finding_count is None:
            print("job_final_finding_count: (unknown)")
        else:
            print(f"job_final_finding_count: {finding_count}")
    print(f"output_dir: {stage_result.output_dir.as_posix()}")


def _print_flow_slot(
    *,
    slot_id: str,
    source_path: Path,
    intake_report: Any,
    extract_report: Any,
    prepare_analysis_report: Any,
    doc_meta_report: Any,
    filter_results: Any,
    projection_results: Any,
    route_semantic_module_results: Any,
) -> None:
    _print_input(source_path=source_path, slot_id=slot_id)
    _print_intake(intake_report)
    _print_processing_identity(extract_report.result.document.identity)
    _print_extract(extract_report)
    _print_prepare_analysis(prepare_analysis_report)
    _print_doc_meta(doc_meta_report)
    for filter_job in filter_results:
        _print_filter_job(filter_job)
    for projection_job in projection_results:
        _print_projection_job(projection_job)
    for route_module in route_semantic_module_results:
        _print_route_semantic_module(route_module)


def _print_summary(
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    report: DocumentConsistencyQcFlowReport,
    standalone_intake_reports: Mapping[str, RequestFileIntakeOperationReport],
) -> None:
    print(f"=== {capability_config.capability_id} consistency QC flow ===")
    print()
    _print_section("Flow execution")
    print(f"flow_run_id: {report.flow_run_id}")
    print(f"flow_run_summary: {report.flow_run_summary_path.as_posix()}")
    print()
    _print_evidence_comparison(report=report)
    print()

    for slot in report.result.slots:
        intake_report = standalone_intake_reports[slot.slot_id]
        source_path = slot.admitted_source.source_path
        if len(report.result.slots) > 1:
            print(f"=== slot: {slot.slot_id} ===")
        _print_flow_slot(
            slot_id=slot.slot_id,
            source_path=source_path,
            intake_report=intake_report,
            extract_report=slot.extract_report,
            prepare_analysis_report=slot.prepare_analysis_report,
            doc_meta_report=slot.doc_meta_report,
            filter_results=slot.filter_results,
            projection_results=slot.projection_results,
            route_semantic_module_results=slot.route_semantic_module_results,
        )
        if len(report.result.slots) > 1:
            print()


def _parse_args(
    capabilities: Mapping[str, DocumentConsistencyQcCapabilityConfig],
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f"Document Consistency QC production entry ({_FLOW_STAGE_DESCRIPTION})."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--capability",
        choices=sorted(capabilities),
        required=True,
        help="Document-consistency capability configuration to run.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help=(
            "Source document for a one-slot capability; "
            "relative paths use the current working directory."
        ),
    )
    parser.add_argument(
        "--source-a",
        default=None,
        help=(
            "First upload position for two-slot capabilities; relative paths "
            "use the current working directory."
        ),
    )
    parser.add_argument(
        "--source-b",
        default=None,
        help=(
            "Second upload position for two-slot capabilities; relative paths "
            "use the current working directory."
        ),
    )
    parser.add_argument(
        "--privacy-config",
        default=None,
        help="Optional Prepare privacy configuration input for a one-slot participant.",
    )
    parser.add_argument(
        "--privacy-config-a",
        default=None,
        help="Optional Prepare privacy configuration input for the first participant.",
    )
    parser.add_argument(
        "--privacy-config-b",
        default=None,
        help="Optional Prepare privacy configuration input for the second participant.",
    )
    parser.add_argument(
        "--source-language",
        default="zh",
        choices=CURRENT_SOURCE_LANGUAGE_CHOICES,
        help=(
            "Source-document processing language for this QC run "
            "(currently only zh is supported)."
        ),
    )
    parser.add_argument(
        "--candidate-scope-mode",
        default=CandidateScopeDecisionMode.AUTOMATIC_CONTINUE.value,
        choices=tuple(mode.value for mode in CandidateScopeDecisionMode),
        help=(
            "Candidate Scope execution policy (defaults to automatic_continue; "
            "use pause_at_candidate_scope for a resumable checkpoint)."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help=(
            "Project root for run artifact layout (defaults to backend/ "
            "via script location)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run with the Document Consistency QC application installed for this process."""

    composition = build_installed_document_consistency_qc_application_composition()
    args = _parse_args(composition.capabilities, argv)
    capability_config = composition.capabilities[args.capability]
    _validate_args(args, capability_config=capability_config)
    project_root = _resolve_project_root(args.project_root)
    source_paths = _build_uploads(args, capability_config=capability_config)
    participant_privacy_paths = _build_participant_privacy_paths(
        args,
        capability_config=capability_config,
    )
    admitted_sources: dict[str, object] = {}
    standalone_intake_reports: dict[str, RequestFileIntakeOperationReport] = {}
    for slot_id, source_path in source_paths.items():
        intake_report = run_request_file_intake_operation(
            project_root=project_root,
            source_file=source_path,
        )
        standalone_intake_reports[slot_id] = intake_report
        admitted_sources[slot_id] = intake_report.result.source_binding
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=args.capability,
        project_root=project_root,
        participant_inputs=admitted_sources,
        participant_privacy_paths=participant_privacy_paths,
        source_language=args.source_language,
        candidate_scope_decision_mode=CandidateScopeDecisionMode(
            args.candidate_scope_mode
        ),
    )
    prepared = prepare_and_allocate_installed_clinical_trial_document_consistency_qc(
        composition=composition,
        request=request,
    )
    result = execute_prepared_installed_clinical_trial_document_consistency_qc(
        prepared
    )
    _print_summary(
        capability_config=capability_config,
        report=result.flow_report,
        standalone_intake_reports=standalone_intake_reports,
    )


if __name__ == "__main__":
    main()
