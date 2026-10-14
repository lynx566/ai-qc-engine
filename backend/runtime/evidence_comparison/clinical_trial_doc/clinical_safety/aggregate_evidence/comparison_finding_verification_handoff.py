"""Resolve persisted Verification inputs from an Assessment execution run."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_aggregate_comparison_evidence,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    validate_findings,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    ComparisonFindingVerificationInput,
    materialize_comparison_finding_verification_inputs,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    resolve_comparison_finding_assessment_execution_handoff,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    resolve_comparison_finding_assessment_plan_handoff,
    verify_participant_provenance,
)
from runtime.io import load_json


def _load_validated_evidence(path: Path) -> dict:
    payload = load_json(path.resolve())
    validate_aggregate_comparison_evidence(payload)
    return payload


def materialize_comparison_finding_verification_inputs_from_assessment_run(
    assessment_run_dir: Path | str,
) -> tuple[ComparisonFindingVerificationInput, ...]:
    """Resolve Assessment lineage and materialize Verification inputs for all findings jobs."""

    execution_handoff = resolve_comparison_finding_assessment_execution_handoff(
        assessment_run_dir
    )
    plan_handoff = resolve_comparison_finding_assessment_plan_handoff(
        execution_handoff.plan_run_dir
    )
    if plan_handoff.plan_run_id != execution_handoff.plan_run_id:
        raise ValueError(
            "assessment source plan run_id does not match resolved plan handoff"
        )
    if plan_handoff.capability_id != execution_handoff.capability_id:
        raise ValueError(
            "assessment source capability_id does not match resolved plan handoff"
        )
    if (
        plan_handoff.evidence_path.resolve()
        != execution_handoff.evidence_path.resolve()
    ):
        raise ValueError(
            "assessment aggregate_comparison_evidence path does not match plan handoff"
        )

    aggregate_comparison_evidence = _load_validated_evidence(
        execution_handoff.evidence_path
    )
    verify_participant_provenance(
        expected=plan_handoff.participant_provenance,
        evidence=aggregate_comparison_evidence,
    )

    findings_payload = load_json(execution_handoff.findings_path)
    validate_findings(findings_payload)

    successful_frozen_job_indexes = frozenset(
        job.frozen_job_index for job in execution_handoff.successful_jobs
    )
    return materialize_comparison_finding_verification_inputs(
        planned_jobs=plan_handoff.frozen_jobs,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        assessment_findings_artifact=findings_payload,
        successful_frozen_job_indexes=successful_frozen_job_indexes,
    )


__all__ = ["materialize_comparison_finding_verification_inputs_from_assessment_run"]
