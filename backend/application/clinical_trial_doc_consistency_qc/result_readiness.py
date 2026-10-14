"""Lightweight prerequisite checks for an internal DCQC Result."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    validate_flow_run_summary,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_final_findings,
)
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    resolve_flow_run_output_dir,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.job_serialization import (
    COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME,
)
from runtime.io import load_json

INTERNAL_RESULT_CAPABILITY_IDS = frozenset({"internal_dsur", "internal_ib", "internal_csr"})


@dataclass(frozen=True, slots=True)
class ResultPrerequisites:
    comparison_output_dir: Path
    final_findings_path: Path
    run_summary_path: Path
    aggregate_comparison_evidence_path: Path
    plan_path: Path


def _path(value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty path")
    return Path(value)


def _readable(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        head = handle.read(1)
    if not head:
        raise ValueError(f"present Result prerequisite is empty: {path.as_posix()}")
    return True


def _require_owned_path(path: Path, *, flow_root: Path) -> None:
    if not path.resolve().is_relative_to(flow_root.resolve()):
        raise ValueError(f"Result prerequisite is outside FlowRun: {path.as_posix()}")


def resolve_result_prerequisites(
    *, project_root: Path, flow_run_id: str, summary: Mapping[str, Any],
) -> ResultPrerequisites | None:
    """Resolve only the files needed to start the full Result read."""

    validate_flow_run_summary(summary)
    if summary["flow_run_id"] != flow_run_id:
        raise ValueError("flow_run_summary.flow_run_id does not match requested Flow")
    if summary["capability_id"] not in INTERNAL_RESULT_CAPABILITY_IDS:
        raise ValueError("Flow capability is unsupported by the internal Result")
    if summary["status"] == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        return None
    try:
        flow_root = resolve_flow_run_output_dir(
            project_root=project_root, flow_run_id=flow_run_id,
        )
    except FlowResumeError:
        return None
    comparison = summary.get("evidence_comparison")
    if comparison is None:
        return None
    if not isinstance(comparison, Mapping):
        raise TypeError("evidence_comparison provenance must be a mapping")
    if not comparison.get("stage_executed"):
        return None
    declared_output_path = comparison.get("declared_output_path")
    if declared_output_path is None:
        return None
    root = _path(comparison.get("output_dir"), field="evidence_comparison.output_dir")
    final_findings = _path(
        declared_output_path,
        field="evidence_comparison.declared_output_path",
    )
    run_summary = _path(comparison.get("run_summary_path"),
                        field="evidence_comparison.run_summary_path")
    evidence = root / "aggregate_comparison_evidence.json"
    plan = root / COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME
    for path in (root, final_findings, run_summary, evidence, plan):
        _require_owned_path(path, flow_root=flow_root)
    if not root.is_dir():
        return None
    for path in (final_findings, run_summary, evidence, plan):
        if not _readable(path):
            return None
    validate_final_findings(load_json(final_findings))
    participants = comparison.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ValueError("evidence_comparison.participants must be non-empty")
    for participant in participants:
        if not isinstance(participant, Mapping):
            raise TypeError("evidence_comparison participant is malformed")
        slot_id = participant.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id:
            raise ValueError("evidence_comparison participant slot_id is malformed")
        esp = _path(participant.get("declared_output_path"),
                    field="evidence_comparison.participant.declared_output_path")
        extract = flow_root / "participants" / slot_id / "extract" / "bundle.json"
        _require_owned_path(esp, flow_root=flow_root)
        _require_owned_path(extract, flow_root=flow_root)
        if not _readable(esp) or not _readable(extract):
            return None
    return ResultPrerequisites(
        comparison_output_dir=root,
        final_findings_path=final_findings,
        run_summary_path=run_summary,
        aggregate_comparison_evidence_path=evidence, plan_path=plan,
    )


def probe_result_readiness(
    *, project_root: Path, flow_run_id: str, summary: Mapping[str, Any],
) -> bool:
    """Return readiness without constructing findings or scope results."""

    validate_flow_run_summary(summary)
    if summary["flow_run_id"] != flow_run_id:
        raise ValueError("flow_run_summary.flow_run_id does not match requested Flow")
    if summary["capability_id"] not in INTERNAL_RESULT_CAPABILITY_IDS:
        return False
    return resolve_result_prerequisites(
        project_root=project_root, flow_run_id=flow_run_id, summary=summary,
    ) is not None


__all__ = [
    "INTERNAL_RESULT_CAPABILITY_IDS",
    "ResultPrerequisites",
    "probe_result_readiness",
    "resolve_result_prerequisites",
]
