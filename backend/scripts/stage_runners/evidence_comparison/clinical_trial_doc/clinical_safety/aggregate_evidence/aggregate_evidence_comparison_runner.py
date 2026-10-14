"""CLI adapter for standalone Aggregate Evidence Comparison from a FlowRun ESP handoff."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc.execution import (
    materialize_installed_evidence_comparison_execution_dependencies,
)
from execution_flow.document_consistency_qc.evidence_comparison_produced_outputs import (
    collect_produced_evidence_source_preparation_outputs_from_flow_execution,
)
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    load_flow_run_execution,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolutionStatus,
    resolve_evidence_comparison_handoff,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonStageContext,
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    resolve_evidence_comparison_stage_run_id,
)
from runtime.evidence_comparison_stage import run_evidence_comparison_stage
from runtime.run_layout import resolve_unique_session_dir, sanitize_run_segment
from runtime.run_provenance import snapshot_git_provenance_before_run
from scripts.stage_runners.common import ensure_project_on_path

_STANDALONE_EVIDENCE_COMPARISON_RUNS_ROOT = (
    "evidence_comparison/clinical_safety/aggregate/standalone"
)


def _default_project_root(value: str | None) -> Path:
    if value is None:
        return PROJECT_ROOT
    return Path(value).resolve()


def _resolve_output_dir(
    *,
    project_root: Path,
    output_dir: Path | str | None,
    run_id: str,
) -> Path:
    if output_dir is not None:
        resolved = Path(output_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    phase_root = project_root / "runs" / _STANDALONE_EVIDENCE_COMPARISON_RUNS_ROOT
    return resolve_unique_session_dir(
        phase_root,
        sanitize_run_segment(run_id),
    ).resolve()


def _format_handoff_not_ready_message(
    *,
    flow_run_id: str,
    resolution,
) -> str:
    if resolution.status is EvidenceComparisonHandoffResolutionStatus.UNBOUND:
        return (
            f"Evidence Comparison handoff is unbound for flow_run_id={flow_run_id!r}"
        )
    missing = resolution.missing_participant_requirements
    if not missing:
        return (
            f"Evidence Comparison handoff is not ready for flow_run_id={flow_run_id!r}"
        )
    missing_parts = [
        f"{requirement.role_id} ({requirement.slot_id}, "
        f"{requirement.semantic_module_id})"
        for requirement in missing
    ]
    return (
        f"Evidence Comparison handoff is incomplete for flow_run_id={flow_run_id!r}; "
        f"missing participant outputs: {', '.join(missing_parts)}"
    )


def run_standalone_aggregate_evidence_comparison_from_flow_run(
    *,
    project_root: Path,
    flow_run_id: str,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
) -> EvidenceComparisonStageResult:
    """Run canonical Evidence Comparison stage from one FlowRun ESP handoff."""

    execution = load_flow_run_execution(
        project_root=project_root,
        flow_run_id=flow_run_id,
    )
    composition = build_installed_document_consistency_qc_application_composition()
    capability_id = execution.capability_id
    if capability_id not in composition.capabilities:
        raise ValueError(
            f"flow capability_id {capability_id!r} is not installed in composition"
        )

    consumer_binding = (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            capability_id
        )
    )
    if consumer_binding is None:
        raise ValueError(
            f"no Evidence Comparison consumer binding for capability {capability_id!r}"
        )

    try:
        produced_outputs = (
            collect_produced_evidence_source_preparation_outputs_from_flow_execution(
                execution
            )
        )
    except ValueError as exc:
        raise ValueError(
            f"flow_run_id {flow_run_id!r} has no usable ESP outputs: {exc}"
        ) from exc
    if not produced_outputs:
        raise ValueError(
            f"flow_run_id {flow_run_id!r} has no usable ESP outputs"
        )

    handoff_resolution = resolve_evidence_comparison_handoff(
        consumer_binding=consumer_binding,
        produced_outputs=produced_outputs,
    )
    if (
        handoff_resolution.status
        is not EvidenceComparisonHandoffResolutionStatus.READY
    ):
        raise ValueError(
            _format_handoff_not_ready_message(
                flow_run_id=flow_run_id,
                resolution=handoff_resolution,
            )
        )
    handoff = handoff_resolution.handoff
    if handoff is None:
        raise ValueError(
            f"Evidence Comparison handoff is not ready for flow_run_id={flow_run_id!r}"
        )

    execution_dependencies = (
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
        )
    )

    requested_run_id = run_id.strip() if run_id is not None else ""
    if run_id is not None and not requested_run_id:
        raise ValueError("run_id must be a non-empty string when provided")
    resolved_run_id = requested_run_id or resolve_evidence_comparison_stage_run_id()
    resolved_output_dir = _resolve_output_dir(
        project_root=project_root,
        output_dir=output_dir,
        run_id=resolved_run_id,
    )
    git_provenance = snapshot_git_provenance_before_run(root=project_root)

    stage_input = EvidenceComparisonStageInput(
        participants=handoff.participants,
        context=EvidenceComparisonStageContext(
            output_dir=resolved_output_dir,
            run_id=resolved_run_id,
            git_provenance=git_provenance,
        ),
        execution_dependencies=execution_dependencies,
    )
    return run_evidence_comparison_stage(
        stage_input=stage_input,
        stage_executor=handoff.consumer_binding.stage_executor,
    )


def _format_stage_result_messages(
    result: EvidenceComparisonStageResult,
) -> tuple[str, ...]:
    messages = [
        f"run_id: {result.run_id}",
        f"status: {result.run_status}",
        f"output_dir: {result.output_dir.as_posix()}",
        f"run_summary: {result.run_summary_path.as_posix()}",
    ]
    if result.declared_output_path is not None:
        messages.append(f"findings: {result.declared_output_path.as_posix()}")
    else:
        messages.append("findings: (none)")
    return tuple(messages)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run canonical Aggregate Evidence Comparison from a completed "
            "Document Consistency QC FlowRun ESP handoff."
        )
    )
    parser.add_argument(
        "--flow-run-id",
        required=True,
        help=(
            "Document Consistency QC flow_run_id "
            "(document_consistency_qc_<timestamp>)."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root for runs layout (defaults to backend/).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Evidence Comparison stage output directory. When omitted, allocates a "
            "fresh directory under runs/evidence_comparison/.../standalone/."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional Evidence Comparison stage run id (defaults to a new timestamp).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    project_root = _default_project_root(args.project_root)
    try:
        result = run_standalone_aggregate_evidence_comparison_from_flow_run(
            project_root=project_root,
            flow_run_id=args.flow_run_id,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except FlowResumeError as exc:
        raise SystemExit(str(exc)) from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except OSError as exc:
        raise SystemExit(str(exc)) from exc

    for message in _format_stage_result_messages(result):
        print(message)


if __name__ == "__main__":
    main()
