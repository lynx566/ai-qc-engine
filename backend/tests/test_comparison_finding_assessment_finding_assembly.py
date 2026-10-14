"""Tests for deterministic Finding assembly from validated Assessment candidates."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
    ComparisonFindingAssessmentValidatedResponse,
    ComparisonFindingAssessmentCandidate,
    assemble_findings_for_job,
    assemble_findings_for_jobs,
    build_findings_artifact_from_bundles,
    format_finding_id,
)


def _validated(*texts: str) -> ComparisonFindingAssessmentValidatedResponse:
    return ComparisonFindingAssessmentValidatedResponse(
        candidates=tuple(
            ComparisonFindingAssessmentCandidate(
                candidate_focus=text,
                label="fail",
                trigger_sentence_aliases=("T0001",),
            )
            for text in texts
        )
    )


def test_candidate_to_finding_mapping_preserves_text() -> None:
    job = ComparisonFindingAssessmentJob(
        comparison_mode_id="scope_local",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="scope",
                scope_aliases=("S0001",),
            ),
        ),
    )
    validated = _validated("原始结论")
    findings = assemble_findings_for_job(validated, job=job)
    assert len(findings) == 1
    assert findings[0].conclusion == "原始结论"
    assert findings[0].label == "fail"
    assert findings[0].source_sentence_aliases == ("T0001",)
    assert findings[0].finding_id == "L001"


def test_artifact_wide_finding_ids_follow_frozen_job_order() -> None:
    job_a = ComparisonFindingAssessmentJob(
        comparison_mode_id="scope_local",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="scope",
                scope_aliases=("S0001",),
            ),
        ),
    )
    job_b = ComparisonFindingAssessmentJob(
        comparison_mode_id="scope_local",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="scope",
                scope_aliases=("S0002",),
            ),
        ),
    )
    bundles = assemble_findings_for_jobs(
        [
            (2, job_b, _validated("second")),
            (1, job_a, _validated("first-a", "first-b")),
        ]
    )
    artifact = build_findings_artifact_from_bundles(bundles)
    finding_ids = [
        finding["finding_id"]
        for job in artifact["jobs"]
        for finding in job["findings"]
    ]
    assert finding_ids == ["L001", "L002", "L003"]
    assert artifact["jobs"][0]["frozen_job_index"] == 1
    assert artifact["jobs"][1]["frozen_job_index"] == 2
    assert artifact["jobs"][0]["comparison_mode_id"] == "scope_local"


def test_format_finding_id() -> None:
    assert format_finding_id(1) == "L001"
    assert format_finding_id(42) == "L042"
