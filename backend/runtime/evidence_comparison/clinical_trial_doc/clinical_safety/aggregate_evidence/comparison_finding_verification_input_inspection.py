"""Standalone dev runtime for Comparison Finding Verification input inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    ComparisonFindingVerificationInput,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_handoff import (
    materialize_comparison_finding_verification_inputs_from_assessment_run,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME,
    resolve_comparison_finding_assessment_execution_handoff,
)
from runtime.io import save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import (
    resolve_unique_session_dir,
    sanitize_run_segment,
    utc_now_iso,
)
from runtime.run_provenance import snapshot_git_provenance_before_run

EVIDENCE_COMPARISON_STAGE = "evidence_comparison"
CLINICAL_SAFETY_EVIDENCE_SCOPE = "clinical_safety"
AGGREGATE_COMPARISON_SPECIALIZATION = "aggregate"
COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_PHASE = (
    "comparison_finding_verification_input"
)
COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_RUN_DIR_LAYOUT = (
    "stage/evidence_scope/specialization/phase/run_id"
)
COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_OPERATION = (
    "aggregate_evidence.inspect_comparison_finding_verification_inputs"
)
VERIFICATION_INPUT_FILENAME = "verification_input.txt"
RUN_SUMMARY_FILENAME = "run_summary.json"


@dataclass(frozen=True)
class ComparisonFindingVerificationInputInspectionJobResult:
    frozen_job_index: int
    comparison_mode_id: str
    job_dir: Path
    verification_input_path: Path


@dataclass(frozen=True)
class ComparisonFindingVerificationInputInspectionResult:
    run_id: str
    output_dir: Path
    run_summary_path: Path
    source_assessment_run_dir: Path
    job_results: tuple[ComparisonFindingVerificationInputInspectionJobResult, ...]


@dataclass(frozen=True)
class ComparisonFindingVerificationInputInspectionReport:
    result: ComparisonFindingVerificationInputInspectionResult
    messages: tuple[str, ...]


def _resolve_output(
    *,
    project_root: Path,
    output_dir: Path | str | None,
    run_id: str | None,
) -> tuple[Path, str]:
    requested_run_id = run_id.strip() if run_id is not None else ""
    if run_id is not None and not requested_run_id:
        raise ValueError("run_id must be a non-empty string when provided")

    if output_dir is not None:
        resolved_output = Path(output_dir).resolve()
        resolved_output.mkdir(parents=True, exist_ok=True)
        resolved_run_id = requested_run_id or format_run_timestamp(utc_run_stamp())
        return resolved_output, resolved_run_id

    phase_root = (
        project_root.resolve()
        / "runs"
        / EVIDENCE_COMPARISON_STAGE
        / CLINICAL_SAFETY_EVIDENCE_SCOPE
        / AGGREGATE_COMPARISON_SPECIALIZATION
        / COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_PHASE
    )
    session_name = requested_run_id or format_run_timestamp(utc_run_stamp())
    session_dir = resolve_unique_session_dir(
        phase_root,
        sanitize_run_segment(session_name),
    )
    return session_dir.resolve(), session_dir.name


def _write_job_input(
    *,
    output_root: Path,
    verification_input: ComparisonFindingVerificationInput,
) -> ComparisonFindingVerificationInputInspectionJobResult:
    job_dir = (
        output_root
        / COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME
        / f"{verification_input.frozen_job_index:03d}_{verification_input.comparison_mode_id}"
    )
    job_dir.mkdir(parents=True, exist_ok=True)
    verification_input_path = job_dir / VERIFICATION_INPUT_FILENAME
    verification_input_path.write_text(
        verification_input.user_input_text,
        encoding="utf-8",
    )
    return ComparisonFindingVerificationInputInspectionJobResult(
        frozen_job_index=verification_input.frozen_job_index,
        comparison_mode_id=verification_input.comparison_mode_id,
        job_dir=job_dir,
        verification_input_path=verification_input_path,
    )


def run_comparison_finding_verification_input_inspection(
    *,
    project_root: Path,
    assessment_run_dir: Path | str,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
) -> ComparisonFindingVerificationInputInspectionReport:
    """Materialize Verification user inputs from one Assessment execution run."""

    source_assessment_run_dir = Path(assessment_run_dir).resolve()
    execution_handoff = resolve_comparison_finding_assessment_execution_handoff(
        source_assessment_run_dir
    )
    verification_inputs = materialize_comparison_finding_verification_inputs_from_assessment_run(
        source_assessment_run_dir
    )

    git_provenance = snapshot_git_provenance_before_run(root=project_root)
    resolved_output, resolved_run_id = _resolve_output(
        project_root=project_root,
        output_dir=output_dir,
        run_id=run_id,
    )
    job_results = tuple(
        _write_job_input(output_root=resolved_output, verification_input=verification_input)
        for verification_input in verification_inputs
    )

    run_summary_path = resolved_output / RUN_SUMMARY_FILENAME
    save_json(
        run_summary_path,
        {
            "run_id": resolved_run_id,
            "stage": EVIDENCE_COMPARISON_STAGE,
            "evidence_scope": CLINICAL_SAFETY_EVIDENCE_SCOPE,
            "specialization": AGGREGATE_COMPARISON_SPECIALIZATION,
            "phase": COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_PHASE,
            "created_at": utc_now_iso(),
            "git_commit": git_provenance["git_commit"],
            "git_dirty": git_provenance["git_dirty"],
            "git_dirty_checked_at": git_provenance["git_dirty_checked_at"],
            "status": "success",
            "run_status": "success",
            "run_dir_layout": (
                COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_RUN_DIR_LAYOUT
            ),
            "completed_operation": (
                COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_OPERATION
            ),
            "inputs": {
                "source_assessment_run": {
                    "run_id": execution_handoff.assessment_run_id,
                    "run_dir": execution_handoff.assessment_run_dir.as_posix(),
                    "findings_path": execution_handoff.findings_path.as_posix(),
                    "source_plan_run": {
                        "run_id": execution_handoff.plan_run_id,
                        "run_dir": execution_handoff.plan_run_dir.as_posix(),
                        "capability_id": execution_handoff.capability_id,
                    },
                    "aggregate_comparison_evidence": {
                        "path": execution_handoff.evidence_path.as_posix(),
                        "resolved_from": "source_assessment_run",
                    },
                },
            },
            "outputs": {
                "run_summary": RUN_SUMMARY_FILENAME,
                "jobs_dir": COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME,
            },
            "stats": {
                "verification_input_count": len(job_results),
            },
            "jobs": [
                {
                    "frozen_job_index": result.frozen_job_index,
                    "comparison_mode_id": result.comparison_mode_id,
                    "job_dir": (
                        f"{COMPARISON_FINDING_ASSESSMENT_JOBS_DIRNAME}/"
                        f"{result.frozen_job_index:03d}_{result.comparison_mode_id}"
                    ),
                    "verification_input": VERIFICATION_INPUT_FILENAME,
                }
                for result in job_results
            ],
        },
    )

    result = ComparisonFindingVerificationInputInspectionResult(
        run_id=resolved_run_id,
        output_dir=resolved_output,
        run_summary_path=run_summary_path,
        source_assessment_run_dir=source_assessment_run_dir,
        job_results=job_results,
    )
    return ComparisonFindingVerificationInputInspectionReport(
        result=result,
        messages=(
            f"run_id: {resolved_run_id}",
            f"source_assessment_run: {source_assessment_run_dir}",
            f"verification_inputs: {len(job_results)}",
            f"run_summary: {run_summary_path}",
        ),
    )


__all__ = [
    "COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_OPERATION",
    "COMPARISON_FINDING_VERIFICATION_INPUT_INSPECTION_PHASE",
    "VERIFICATION_INPUT_FILENAME",
    "ComparisonFindingVerificationInputInspectionReport",
    "ComparisonFindingVerificationInputInspectionResult",
    "run_comparison_finding_verification_input_inspection",
]
