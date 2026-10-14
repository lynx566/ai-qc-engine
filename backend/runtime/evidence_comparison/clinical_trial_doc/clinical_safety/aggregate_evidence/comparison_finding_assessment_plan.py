"""Standalone dev runtime for Comparison Finding Assessment plan inspection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME,
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
    materialize_comparison_finding_assessment_llm_inputs,
    plan_comparison_finding_assessment_jobs,
    serialize_comparison_finding_assessment_jobs,
)
from runtime.io import load_json, save_json
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
COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE = "comparison_finding_assessment_plan"
COMPARISON_FINDING_ASSESSMENT_PLAN_RUN_DIR_LAYOUT = (
    "stage/evidence_scope/specialization/phase/run_id"
)
COMPARISON_FINDING_ASSESSMENT_PLAN_OPERATION = (
    "aggregate_evidence.plan_comparison_finding_assessment_jobs"
)
COMPARISON_FINDING_ASSESSMENT_LLM_INPUTS_DIRNAME = "llm_inputs"
RUN_SUMMARY_FILENAME = "run_summary.json"


@dataclass(frozen=True)
class ComparisonFindingAssessmentPlanHandoff:
    plan_run_id: str
    plan_run_dir: Path
    capability_id: str
    frozen_jobs: tuple[ComparisonFindingAssessmentJob, ...]
    evidence_path: Path
    participant_provenance: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class ComparisonFindingAssessmentPlanInspectionResult:
    run_id: str
    output_dir: Path
    inspection_payload: dict[str, Any]
    inspection_path: Path
    llm_inputs_dir: Path
    llm_input_count: int
    run_summary_path: Path


@dataclass(frozen=True)
class ComparisonFindingAssessmentPlanInspectionReport:
    result: ComparisonFindingAssessmentPlanInspectionResult
    messages: tuple[str, ...]


def _load_validated_evidence(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(
            f"aggregate_comparison_evidence must point to an existing file: {resolved}"
        )
    payload = load_json(resolved)
    validate_aggregate_comparison_evidence(payload)
    return payload


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
        / COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE
    )
    session_name = requested_run_id or format_run_timestamp(utc_run_stamp())
    session_dir = resolve_unique_session_dir(
        phase_root,
        sanitize_run_segment(session_name),
    )
    return session_dir.resolve(), session_dir.name


def _deserialize_group(
    payload: Mapping[str, Any], *, path: str
) -> ComparisonFindingAssessmentGroup:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{path} must be a mapping")
    group_role = payload.get("group_role")
    if not isinstance(group_role, str) or not group_role.strip():
        raise ValueError(f"{path}.group_role must be a non-empty string")
    scope_aliases_raw = payload.get("scope_aliases")
    if not isinstance(scope_aliases_raw, list) or not scope_aliases_raw:
        raise ValueError(f"{path}.scope_aliases must be a non-empty list")
    scope_aliases = tuple(str(alias) for alias in scope_aliases_raw)
    return ComparisonFindingAssessmentGroup(
        group_role=group_role.strip(),  # type: ignore[arg-type]
        scope_aliases=scope_aliases,
    )


def _deserialize_job(
    payload: Mapping[str, Any], *, path: str
) -> ComparisonFindingAssessmentJob:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{path} must be a mapping")
    comparison_mode_id = payload.get("comparison_mode_id")
    if not isinstance(comparison_mode_id, str) or not comparison_mode_id.strip():
        raise ValueError(f"{path}.comparison_mode_id must be a non-empty string")
    groups_raw = payload.get("groups")
    if not isinstance(groups_raw, list) or not groups_raw:
        raise ValueError(f"{path}.groups must be a non-empty list")
    groups = tuple(
        _deserialize_group(group, path=f"{path}.groups[{index}]")
        for index, group in enumerate(groups_raw)
    )
    return ComparisonFindingAssessmentJob(
        comparison_mode_id=comparison_mode_id.strip(),  # type: ignore[arg-type]
        groups=groups,
    )


def deserialize_comparison_finding_assessment_job(
    payload: Mapping[str, Any],
) -> ComparisonFindingAssessmentJob:
    """Deserialize one persisted discovery job envelope."""

    return _deserialize_job(payload, path="job")


def load_comparison_finding_assessment_jobs_from_plan(
    plan_run_dir: Path | str,
) -> tuple[str, tuple[ComparisonFindingAssessmentJob, ...]]:
    """Load frozen discovery jobs from a persisted plan run directory."""

    resolved_plan_run_dir = Path(plan_run_dir).resolve()
    jobs_path = resolved_plan_run_dir / COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME
    if not jobs_path.is_file():
        raise ValueError(
            f"comparison_finding_assessment_jobs must exist under plan run: {jobs_path}"
        )
    payload = load_json(jobs_path)
    if not isinstance(payload, Mapping):
        raise TypeError("comparison_finding_assessment_jobs must be a mapping")
    capability_id = payload.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError(
            "comparison_finding_assessment_jobs.capability_id must be non-empty"
        )
    jobs_raw = payload.get("jobs")
    if not isinstance(jobs_raw, list) or not jobs_raw:
        raise ValueError(
            "comparison_finding_assessment_jobs.jobs must be a non-empty list"
        )
    jobs = tuple(
        _deserialize_job(job, path=f"jobs[{index}]")
        for index, job in enumerate(jobs_raw)
    )
    return capability_id.strip(), jobs


def participant_provenance_from_evidence(
    evidence: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    return tuple(_participant_provenance(evidence))


def verify_participant_provenance(
    *,
    expected: Sequence[Mapping[str, str]],
    evidence: Mapping[str, Any],
) -> None:
    actual = participant_provenance_from_evidence(evidence)
    if len(actual) != len(expected):
        raise ValueError(
            "aggregate_comparison_evidence participant count does not match plan run"
        )
    for index, (expected_row, actual_row) in enumerate(
        zip(expected, actual, strict=True)
    ):
        if dict(expected_row) != actual_row:
            raise ValueError(
                f"aggregate_comparison_evidence participant provenance mismatch at "
                f"index {index}"
            )


def resolve_comparison_finding_assessment_plan_handoff(
    plan_run_dir: Path | str,
) -> ComparisonFindingAssessmentPlanHandoff:
    """Resolve frozen jobs and evidence reference from a plan inspection run."""

    resolved_plan_run_dir = Path(plan_run_dir).resolve()
    if not resolved_plan_run_dir.is_dir():
        raise ValueError(
            f"plan_run_dir must be an existing directory: {resolved_plan_run_dir}"
        )

    summary_path = resolved_plan_run_dir / RUN_SUMMARY_FILENAME
    if not summary_path.is_file():
        raise ValueError(f"plan run_summary must exist: {summary_path}")
    summary = load_json(summary_path)
    if not isinstance(summary, Mapping):
        raise TypeError("plan run_summary must be a mapping")
    if summary.get("stage") != EVIDENCE_COMPARISON_STAGE:
        raise ValueError("plan run_summary.stage must be evidence_comparison")
    if summary.get("phase") != COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE:
        raise ValueError(
            "plan run_summary.phase must be comparison_finding_assessment_plan"
        )

    run_id = summary.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("plan run_summary.run_id must be a non-empty string")

    inputs = summary.get("inputs")
    if not isinstance(inputs, Mapping):
        raise TypeError("plan run_summary.inputs must be a mapping")

    evidence_inputs = inputs.get("aggregate_comparison_evidence")
    if not isinstance(evidence_inputs, Mapping):
        raise TypeError(
            "plan run_summary.inputs.aggregate_comparison_evidence must be a mapping"
        )
    evidence_path_raw = evidence_inputs.get("path")
    if not isinstance(evidence_path_raw, str) or not evidence_path_raw.strip():
        raise ValueError(
            "plan run_summary.inputs.aggregate_comparison_evidence.path "
            "must be a non-empty string"
        )

    participants = inputs.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ValueError(
            "plan run_summary.inputs.participants must be a non-empty list"
        )
    participant_provenance_rows: list[dict[str, str]] = []
    for index, row in enumerate(participants):
        if not isinstance(row, Mapping):
            raise TypeError(
                f"plan run_summary.inputs.participants[{index}] must be a mapping"
            )
        participant_provenance_rows.append(
            {
                "role_id": str(row["role_id"]),
                "aggregate_evidence_source_bundle_id": str(
                    row["aggregate_evidence_source_bundle_id"]
                ),
                "doc_id": str(row["doc_id"]),
                "file_hash": str(row["file_hash"]),
            }
        )
    participant_provenance = tuple(participant_provenance_rows)

    capability_id, frozen_jobs = load_comparison_finding_assessment_jobs_from_plan(
        resolved_plan_run_dir
    )
    summary_capability_id = inputs.get("capability_id")
    if (
        isinstance(summary_capability_id, str)
        and summary_capability_id.strip()
        and summary_capability_id.strip() != capability_id
    ):
        raise ValueError(
            "plan run_summary.inputs.capability_id does not match "
            "comparison_finding_assessment_jobs.capability_id"
        )

    return ComparisonFindingAssessmentPlanHandoff(
        plan_run_id=run_id.strip(),
        plan_run_dir=resolved_plan_run_dir,
        capability_id=capability_id,
        frozen_jobs=frozen_jobs,
        evidence_path=Path(evidence_path_raw.strip()).resolve(),
        participant_provenance=participant_provenance,
    )


def _participant_provenance(
    evidence: Mapping[str, Any],
) -> list[dict[str, str]]:
    participants = evidence["participants"]
    provenance: list[dict[str, str]] = []
    for index, participant in enumerate(participants):
        if not isinstance(participant, Mapping):
            raise TypeError(f"participants[{index}] must be a mapping")
        provenance.append(
            {
                "role_id": str(participant["role_id"]),
                "aggregate_evidence_source_bundle_id": str(
                    participant["aggregate_evidence_source_bundle_id"]
                ),
                "doc_id": str(participant["doc_id"]),
                "file_hash": str(participant["file_hash"]),
            }
        )
    return provenance


def _stats(
    *,
    evidence: Mapping[str, Any],
    jobs: tuple[ComparisonFindingAssessmentJob, ...],
    llm_input_count: int,
) -> dict[str, Any]:
    participants = evidence["participants"]
    scope_count = sum(len(participant["scopes"]) for participant in participants)
    job_count_by_comparison_mode = dict(Counter(job.comparison_mode_id for job in jobs))
    group_scope_count_by_comparison_mode = {
        comparison_mode_id: sum(
            len(group.scope_aliases)
            for job in jobs
            if job.comparison_mode_id == comparison_mode_id
            for group in job.groups
        )
        for comparison_mode_id in job_count_by_comparison_mode
    }
    return {
        "participant_count": len(participants),
        "scope_count": scope_count,
        "job_count": len(jobs),
        "llm_input_count": llm_input_count,
        "job_count_by_comparison_mode": job_count_by_comparison_mode,
        "group_scope_count_by_comparison_mode": group_scope_count_by_comparison_mode,
    }


def run_comparison_finding_assessment_plan_inspection(
    *,
    project_root: Path,
    evidence: Path | str,
    capability_id: str,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
) -> ComparisonFindingAssessmentPlanInspectionReport:
    """Plan discovery jobs from formal evidence and persist dev inspection outputs."""

    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("capability_id must be a non-empty string")
    normalized_capability_id = capability_id.strip()

    evidence_path = Path(evidence)
    aggregate_comparison_evidence = _load_validated_evidence(evidence_path)
    discovery_config = resolve_installed_comparison_finding_assessment_config(
        normalized_capability_id
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        config=discovery_config,
    )
    rendered_llm_inputs = materialize_comparison_finding_assessment_llm_inputs(
        jobs=jobs,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )

    git_provenance = snapshot_git_provenance_before_run(root=project_root)
    resolved_output, resolved_run_id = _resolve_output(
        project_root=project_root,
        output_dir=output_dir,
        run_id=run_id,
    )

    inspection_payload = serialize_comparison_finding_assessment_jobs(
        capability_id=normalized_capability_id,
        jobs=jobs,
    )
    inspection_path = resolved_output / COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME
    llm_inputs_dir = resolved_output / COMPARISON_FINDING_ASSESSMENT_LLM_INPUTS_DIRNAME
    run_summary_path = resolved_output / "run_summary.json"
    save_json(inspection_path, inspection_payload)
    llm_inputs_dir.mkdir(parents=True, exist_ok=True)
    for index, (job, rendered_input) in enumerate(
        zip(jobs, rendered_llm_inputs, strict=True),
        start=1,
    ):
        filename = f"{index:03d}_{job.comparison_mode_id}.txt"
        (llm_inputs_dir / filename).write_text(rendered_input, encoding="utf-8")
    save_json(
        run_summary_path,
        {
            "run_id": resolved_run_id,
            "stage": EVIDENCE_COMPARISON_STAGE,
            "evidence_scope": CLINICAL_SAFETY_EVIDENCE_SCOPE,
            "specialization": AGGREGATE_COMPARISON_SPECIALIZATION,
            "phase": COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE,
            "created_at": utc_now_iso(),
            "git_commit": git_provenance["git_commit"],
            "git_dirty": git_provenance["git_dirty"],
            "git_dirty_checked_at": git_provenance["git_dirty_checked_at"],
            "status": "success",
            "run_status": "success",
            "run_dir_layout": COMPARISON_FINDING_ASSESSMENT_PLAN_RUN_DIR_LAYOUT,
            "completed_operation": COMPARISON_FINDING_ASSESSMENT_PLAN_OPERATION,
            "inputs": {
                "aggregate_comparison_evidence": {
                    "path": evidence_path.resolve().as_posix(),
                },
                "capability_id": normalized_capability_id,
                "participants": _participant_provenance(aggregate_comparison_evidence),
            },
            "outputs": {
                "run_summary": "run_summary.json",
                "comparison_finding_assessment_jobs": (
                    COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME
                ),
                "llm_inputs_dir": COMPARISON_FINDING_ASSESSMENT_LLM_INPUTS_DIRNAME,
            },
            "stats": _stats(
                evidence=aggregate_comparison_evidence,
                jobs=jobs,
                llm_input_count=len(rendered_llm_inputs),
            ),
        },
    )

    result = ComparisonFindingAssessmentPlanInspectionResult(
        run_id=resolved_run_id,
        output_dir=resolved_output,
        inspection_payload=inspection_payload,
        inspection_path=inspection_path,
        llm_inputs_dir=llm_inputs_dir,
        llm_input_count=len(rendered_llm_inputs),
        run_summary_path=run_summary_path,
    )
    return ComparisonFindingAssessmentPlanInspectionReport(
        result=result,
        messages=(
            f"run_id: {resolved_run_id}",
            f"comparison_finding_assessment_jobs: {inspection_path}",
            f"llm_inputs: {llm_inputs_dir} ({len(rendered_llm_inputs)})",
            f"run_summary: {run_summary_path}",
        ),
    )


__all__ = [
    "COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME",
    "COMPARISON_FINDING_ASSESSMENT_LLM_INPUTS_DIRNAME",
    "COMPARISON_FINDING_ASSESSMENT_PLAN_PHASE",
    "ComparisonFindingAssessmentPlanHandoff",
    "ComparisonFindingAssessmentPlanInspectionReport",
    "ComparisonFindingAssessmentPlanInspectionResult",
    "deserialize_comparison_finding_assessment_job",
    "load_comparison_finding_assessment_jobs_from_plan",
    "participant_provenance_from_evidence",
    "resolve_comparison_finding_assessment_plan_handoff",
    "run_comparison_finding_assessment_plan_inspection",
    "verify_participant_provenance",
]
