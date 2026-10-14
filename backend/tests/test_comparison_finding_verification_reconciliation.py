"""Tests for Comparison Finding Verification reconciliation and assembly."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
    build_findings,
    validate_findings,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    AdditionalFindingEligibilityResult,
    ComparisonFindingVerificationAdditionalFinding,
    ComparisonFindingVerificationConfirmedEntry,
    ComparisonFindingVerificationRejectedEntry,
    ComparisonFindingVerificationRevisedEntry,
    ComparisonFindingVerificationValidatedResponse,
    assemble_verified_findings_artifact,
    filter_eligible_additional_findings,
    max_finding_sequence_number,
    reconcile_existing_findings,
    reconcile_verification_job,
)

_FIXTURE_ROOT = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)
_INTERNAL_EVIDENCE = (
    _FIXTURE_ROOT / "internal_dsur" / "aggregate_comparison_evidence.json"
)


def _evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": "bundle_test",
                "doc_id": "doc_test",
                "file_hash": "sha256:test",
                "scopes": [
                    {
                        "scope_id": "HS0001",
                        "scope_alias": "H0001",
                        "heading_path": ["Overview", "Safety"],
                        "units": [
                            {
                                "unit_id": "TU0001",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "C0001:S001",
                                        "sentence_alias": "T0001",
                                        "text": "Alpha",
                                    },
                                    {
                                        "sentence_id": "C0001:S002",
                                        "sentence_alias": "T0002",
                                        "text": "Beta",
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0002",
                        "scope_alias": "H0002",
                        "heading_path": ["Comparison"],
                        "units": [
                            {
                                "unit_id": "TU0002",
                                "unit_alias": "U0002",
                                "sentences": [
                                    {
                                        "sentence_id": "C0002:S001",
                                        "sentence_alias": "T0003",
                                        "text": "Delta",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0003",
                        "scope_alias": "H0003",
                        "heading_path": ["IB"],
                        "units": [
                            {
                                "unit_id": "TU0003",
                                "unit_alias": "U0003",
                                "sentences": [
                                    {
                                        "sentence_id": "C0003:S001",
                                        "sentence_alias": "T0004",
                                        "text": "Epsilon",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ]
    )


def _job(
    comparison_mode_id: str,
    *groups: tuple[str, tuple[str, ...]],
) -> ComparisonFindingAssessmentJob:
    return ComparisonFindingAssessmentJob(
        comparison_mode_id=comparison_mode_id,  # type: ignore[arg-type]
        groups=tuple(
            ComparisonFindingAssessmentGroup(
                group_role=role,  # type: ignore[arg-type]
                scope_aliases=aliases,
            )
            for role, aliases in groups
        ),
    )


def _original_finding(
    finding_id: str,
    *,
    conclusion: str = "A",
    label: str = "fail",
    aliases: tuple[str, ...] = ("T0001",),
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "conclusion": conclusion,
        "label": label,
        "source_sentence_aliases": list(aliases),
    }


def _validated(
    *entries: ComparisonFindingVerificationConfirmedEntry
    | ComparisonFindingVerificationRevisedEntry
    | ComparisonFindingVerificationRejectedEntry,
    additional: tuple[ComparisonFindingVerificationAdditionalFinding, ...] = (),
) -> ComparisonFindingVerificationValidatedResponse:
    return ComparisonFindingVerificationValidatedResponse(
        finding_verifications=tuple(entries),
        additional_findings=additional,
    )


def _empty_eligibility() -> AdditionalFindingEligibilityResult:
    return AdditionalFindingEligibilityResult(
        accepted_additional_findings=(),
        dropped_additional_findings=(),
        received_additional_finding_count=0,
        accepted_additional_finding_count=0,
        dropped_additional_finding_count=0,
        drop_reason_counts={},
    )


def test_confirmed_preserves_original_finding() -> None:
    original = [
        _original_finding("L001", conclusion="A", label="fail", aliases=("T0001",))
    ]
    validated = _validated(
        ComparisonFindingVerificationConfirmedEntry(
            finding_id="L001",
            verification_result="confirmed",
        )
    )
    reconciled, confirmed_count, revised_count, rejected_count = reconcile_existing_findings(
        original,
        validated_response=validated,
    )
    assert list(reconciled) == [
        {
            "finding_id": "L001",
            "conclusion": "A",
            "label": "fail",
            "source_sentence_aliases": ["T0001"],
        }
    ]
    assert confirmed_count == 1
    assert revised_count == 0
    assert rejected_count == 0


def test_revised_applies_replacement_without_alias_ownership_gate() -> None:
    original = [
        _original_finding("L001", conclusion="A", label="fail", aliases=("T0001",))
    ]
    validated = _validated(
        ComparisonFindingVerificationRevisedEntry(
            finding_id="L001",
            verification_result="revised",
            conclusion="B",
            label="fail",
            source_sentence_aliases=("T9999",),
        )
    )
    reconciled, _, revised_count, rejected_count = reconcile_existing_findings(
        original,
        validated_response=validated,
    )
    assert list(reconciled) == [
        {
            "finding_id": "L001",
            "conclusion": "B",
            "label": "fail",
            "source_sentence_aliases": ["T9999"],
        }
    ]
    assert revised_count == 1
    assert rejected_count == 0


def test_mixed_confirmed_revised_and_rejected_preserves_active_order() -> None:
    originals = [
        _original_finding("L001", conclusion="one"),
        _original_finding("L002", conclusion="two"),
        _original_finding("L003", conclusion="three"),
    ]
    validated = _validated(
        ComparisonFindingVerificationConfirmedEntry(
            finding_id="L001",
            verification_result="confirmed",
        ),
        ComparisonFindingVerificationRevisedEntry(
            finding_id="L002",
            verification_result="revised",
            conclusion="two-corrected",
            label="fail",
            source_sentence_aliases=("T0002",),
        ),
        ComparisonFindingVerificationRejectedEntry(
            finding_id="L003",
            verification_result="rejected",
        ),
    )
    reconciled, confirmed_count, revised_count, rejected_count = reconcile_existing_findings(
        originals,
        validated_response=validated,
    )
    assert [row["finding_id"] for row in reconciled] == ["L001", "L002"]
    assert reconciled[0]["conclusion"] == "one"
    assert reconciled[1]["conclusion"] == "two-corrected"
    assert confirmed_count == 1
    assert revised_count == 1
    assert rejected_count == 1


def test_rejected_omits_original_finding_but_remains_in_validated_response() -> None:
    original = [_original_finding("L001", conclusion="A", label="fail")]
    rejected = ComparisonFindingVerificationRejectedEntry(
        finding_id="L001",
        verification_result="rejected",
    )
    validated = _validated(rejected)

    reconciled, confirmed_count, revised_count, rejected_count = (
        reconcile_existing_findings(original, validated_response=validated)
    )

    assert validated.finding_verifications == (rejected,)
    assert reconciled == ()
    assert confirmed_count == 0
    assert revised_count == 0
    assert rejected_count == 1


def test_additional_scope_local_accepts_in_job_alias() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    additional = ComparisonFindingVerificationAdditionalFinding(
        conclusion="extra",
        label="fail",
        source_sentence_aliases=("T0001",),
    )
    result = filter_eligible_additional_findings(
        [additional],
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    assert result.accepted_additional_finding_count == 1
    assert result.dropped_additional_finding_count == 0


def test_additional_scope_local_drops_out_of_job_alias() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    additional = ComparisonFindingVerificationAdditionalFinding(
        conclusion="extra",
        label="fail",
        source_sentence_aliases=("T9999",),
    )
    result = filter_eligible_additional_findings(
        [additional],
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    assert result.accepted_additional_finding_count == 0
    assert result.dropped_additional_finding_count == 1
    assert result.drop_reason_counts["alias_outside_job_input"] == 1


@pytest.mark.parametrize(
    ("aliases", "accepted"),
    [
        (("T0002", "T0003"), True),
        (("T0002",), False),
        (("T0003",), False),
    ],
)
def test_additional_focus_comparison_side_coverage(
    aliases: tuple[str, ...],
    accepted: bool,
) -> None:
    job = _job(
        "focus_comparison",
        ("focus_scope", ("H0002",)),
        ("comparison_scopes", ("H0003", "H0001")),
    )
    additional = ComparisonFindingVerificationAdditionalFinding(
        conclusion="extra",
        label="fail",
        source_sentence_aliases=aliases,
    )
    result = filter_eligible_additional_findings(
        [additional],
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    assert result.accepted_additional_finding_count == (1 if accepted else 0)


@pytest.mark.parametrize(
    ("aliases", "accepted"),
    [
        (("T0004", "T0001"), True),
        (("T0004",), False),
        (("T0001",), False),
    ],
)
def test_additional_ib_to_dsur_side_coverage(
    aliases: tuple[str, ...],
    accepted: bool,
) -> None:
    job = _job(
        "ib_to_dsur",
        ("ib_scope", ("H0003",)),
        ("dsur_scopes", ("H0001", "H0002")),
    )
    additional = ComparisonFindingVerificationAdditionalFinding(
        conclusion="extra",
        label="fail",
        source_sentence_aliases=aliases,
    )
    result = filter_eligible_additional_findings(
        [additional],
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    assert result.accepted_additional_finding_count == (1 if accepted else 0)


@pytest.mark.parametrize(
    ("aliases", "accepted"),
    [
        (("T0001", "T0004"), True),
        (("T0001",), False),
        (("T0004",), False),
    ],
)
def test_additional_dsur_to_ib_side_coverage(
    aliases: tuple[str, ...],
    accepted: bool,
) -> None:
    job = _job(
        "dsur_to_ib",
        ("dsur_scopes", ("H0001", "H0002")),
        ("ib_scopes", ("H0003",)),
    )
    additional = ComparisonFindingVerificationAdditionalFinding(
        conclusion="extra",
        label="fail",
        source_sentence_aliases=aliases,
    )
    result = filter_eligible_additional_findings(
        [additional],
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    assert result.accepted_additional_finding_count == (1 if accepted else 0)


def test_partial_additional_drop_keeps_job_eligible_for_assembly() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    additional = [
        ComparisonFindingVerificationAdditionalFinding(
            conclusion="ok",
            label="fail",
            source_sentence_aliases=("T0001",),
        ),
        ComparisonFindingVerificationAdditionalFinding(
            conclusion="bad",
            label="fail",
            source_sentence_aliases=("T9999",),
        ),
        ComparisonFindingVerificationAdditionalFinding(
            conclusion="also ok",
            label="fail",
            source_sentence_aliases=("T0002",),
        ),
    ]
    eligibility = filter_eligible_additional_findings(
        additional,
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    assert eligibility.received_additional_finding_count == 3
    assert eligibility.accepted_additional_finding_count == 2
    assert eligibility.dropped_additional_finding_count == 1


def test_all_additional_dropped_still_reconciles_existing() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    originals = [_original_finding("L001")]
    validated = _validated(
        ComparisonFindingVerificationConfirmedEntry(
            finding_id="L001",
            verification_result="confirmed",
        ),
        additional=(
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="bad",
                label="fail",
                source_sentence_aliases=("T9999",),
            ),
        ),
    )
    eligibility = filter_eligible_additional_findings(
        validated.additional_findings,
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )
    reconciled_job = reconcile_verification_job(
        frozen_job_index=1,
        job=job,
        original_findings=originals,
        validated_response=validated,
        additional_eligibility=eligibility,
    )
    assert len(reconciled_job.findings) == 1
    assert eligibility.accepted_additional_finding_count == 0


def test_global_id_allocation_uses_max_existing_id() -> None:
    assessment_artifact = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]},
                ],
                "findings": [
                    _original_finding("L001"),
                    _original_finding("L002"),
                    _original_finding("L004"),
                ],
            }
        ]
    )
    assert max_finding_sequence_number(assessment_artifact) == 4

    job = _job("scope_local", ("scope", ("H0001",)))
    eligibility = AdditionalFindingEligibilityResult(
        accepted_additional_findings=(
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="extra1",
                label="fail",
                source_sentence_aliases=("T0001",),
            ),
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="extra2",
                label="fail",
                source_sentence_aliases=("T0002",),
            ),
        ),
        dropped_additional_findings=(),
        received_additional_finding_count=2,
        accepted_additional_finding_count=2,
        dropped_additional_finding_count=0,
        drop_reason_counts={},
    )
    job_reconciliation = reconcile_verification_job(
        frozen_job_index=1,
        job=job,
        original_findings=[
            _original_finding("L001"),
            _original_finding("L002"),
            _original_finding("L004"),
        ],
        validated_response=_validated(
            ComparisonFindingVerificationConfirmedEntry(
                finding_id="L001",
                verification_result="confirmed",
            ),
            ComparisonFindingVerificationConfirmedEntry(
                finding_id="L002",
                verification_result="confirmed",
            ),
            ComparisonFindingVerificationConfirmedEntry(
                finding_id="L004",
                verification_result="confirmed",
            ),
        ),
        additional_eligibility=eligibility,
    )
    assembly = assemble_verified_findings_artifact(
        assessment_findings_artifact=assessment_artifact,
        job_reconciliations=[(job_reconciliation, eligibility)],
    )
    finding_ids = [
        finding["finding_id"]
        for finding in assembly.findings_artifact["jobs"][0]["findings"]
    ]
    assert finding_ids == ["L001", "L002", "L004", "L005", "L006"]
    validate_findings(assembly.findings_artifact)


def test_cross_job_id_allocation_orders_by_frozen_job_index() -> None:
    assessment_artifact = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]},
                ],
                "findings": [_original_finding("L004")],
            }
        ]
    )
    job1 = _job("scope_local", ("scope", ("H0001",)))
    job2 = _job("scope_local", ("scope", ("H0001",)))
    eligibility1 = AdditionalFindingEligibilityResult(
        accepted_additional_findings=(
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="j1a",
                label="fail",
                source_sentence_aliases=("T0001",),
            ),
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="j1b",
                label="fail",
                source_sentence_aliases=("T0002",),
            ),
        ),
        dropped_additional_findings=(),
        received_additional_finding_count=2,
        accepted_additional_finding_count=2,
        dropped_additional_finding_count=0,
        drop_reason_counts={},
    )
    eligibility2 = AdditionalFindingEligibilityResult(
        accepted_additional_findings=(
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="j2a",
                label="fail",
                source_sentence_aliases=("T0001",),
            ),
        ),
        dropped_additional_findings=(),
        received_additional_finding_count=1,
        accepted_additional_finding_count=1,
        dropped_additional_finding_count=0,
        drop_reason_counts={},
    )
    reconciliation1 = reconcile_verification_job(
        frozen_job_index=2,
        job=job2,
        original_findings=[],
        validated_response=_validated(),
        additional_eligibility=eligibility2,
    )
    reconciliation2 = reconcile_verification_job(
        frozen_job_index=1,
        job=job1,
        original_findings=[_original_finding("L004")],
        validated_response=_validated(
            ComparisonFindingVerificationConfirmedEntry(
                finding_id="L004",
                verification_result="confirmed",
            )
        ),
        additional_eligibility=eligibility1,
    )
    assembly = assemble_verified_findings_artifact(
        assessment_findings_artifact=assessment_artifact,
        job_reconciliations=[
            (reconciliation1, eligibility2),
            (reconciliation2, eligibility1),
        ],
    )
    job_rows = {
        row["frozen_job_index"]: row for row in assembly.findings_artifact["jobs"]
    }
    assert [finding["finding_id"] for finding in job_rows[1]["findings"]] == [
        "L004",
        "L005",
        "L006",
    ]
    assert [finding["finding_id"] for finding in job_rows[2]["findings"]] == ["L007"]


def test_empty_original_findings_additional_starts_at_l001() -> None:
    assessment_artifact = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]},
                ],
                "findings": [],
            }
        ]
    )
    job = _job("scope_local", ("scope", ("H0001",)))
    eligibility = AdditionalFindingEligibilityResult(
        accepted_additional_findings=(
            ComparisonFindingVerificationAdditionalFinding(
                conclusion="first",
                label="fail",
                source_sentence_aliases=("T0001",),
            ),
        ),
        dropped_additional_findings=(),
        received_additional_finding_count=1,
        accepted_additional_finding_count=1,
        dropped_additional_finding_count=0,
        drop_reason_counts={},
    )
    reconciliation = reconcile_verification_job(
        frozen_job_index=1,
        job=job,
        original_findings=[],
        validated_response=_validated(),
        additional_eligibility=eligibility,
    )
    assembly = assemble_verified_findings_artifact(
        assessment_findings_artifact=assessment_artifact,
        job_reconciliations=[(reconciliation, eligibility)],
    )
    assert assembly.findings_artifact["jobs"][0]["findings"][0]["finding_id"] == "L001"


def test_empty_findings_no_additional_produces_empty_job_findings() -> None:
    assessment_artifact = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]},
                ],
                "findings": [],
            }
        ]
    )
    job = _job("scope_local", ("scope", ("H0001",)))
    reconciliation = reconcile_verification_job(
        frozen_job_index=1,
        job=job,
        original_findings=[],
        validated_response=_validated(),
        additional_eligibility=_empty_eligibility(),
    )
    assembly = assemble_verified_findings_artifact(
        assessment_findings_artifact=assessment_artifact,
        job_reconciliations=[(reconciliation, _empty_eligibility())],
    )
    assert assembly.findings_artifact["jobs"][0]["findings"] == []
    validate_findings(assembly.findings_artifact)
