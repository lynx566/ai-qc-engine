"""Tests for Comparison Finding Assessment candidate eligibility."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCandidate,
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
    ComparisonFindingAssessmentValidatedResponse,
    assemble_findings_for_job,
    collect_job_group_sentence_aliases,
    filter_eligible_candidates,
    parse_and_validate_comparison_finding_assessment_response,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    run_comparison_finding_assessment_execution,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    run_comparison_finding_assessment_plan_inspection,
)
from runtime.io import load_json


def _sentence(sentence_alias: str, text: str) -> dict[str, str]:
    return {
        "sentence_id": f"C:{sentence_alias}",
        "sentence_alias": sentence_alias,
        "text": text,
    }


def _scope(
    scope_index: int,
    *,
    scope_alias: str,
    sentence_aliases: tuple[str, ...],
) -> dict:
    # sentence_aliases must follow artifact-wide T0001, T0002, ... order (not per-scope gaps).
    return {
        "scope_id": f"HS{scope_index:04d}",
        "scope_alias": scope_alias,
        "heading_path": [f"Heading {scope_index}"],
        "units": [
            {
                "unit_id": f"TU{scope_index:04d}",
                "unit_alias": f"U{scope_index:04d}",
                "sentences": [
                    _sentence(alias, f"text-{alias}") for alias in sentence_aliases
                ],
            }
        ],
    }


def _single_scope_evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": "bundle",
                "doc_id": "doc",
                "file_hash": "sha256:test",
                "scopes": [_scope(1, scope_alias="H0001", sentence_aliases=("T0001",))],
            }
        ],
    )


def _two_scope_single_participant_evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": "bundle",
                "doc_id": "doc",
                "file_hash": "sha256:test",
                "scopes": [
                    _scope(1, scope_alias="H0001", sentence_aliases=("T0001",)),
                    _scope(2, scope_alias="H0002", sentence_aliases=("T0002",)),
                ],
            }
        ],
    )


def _cross_participant_evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "ib",
                "aggregate_evidence_source_bundle_id": "bundle-ib",
                "doc_id": "doc-ib",
                "file_hash": "sha256:ib",
                "scopes": [_scope(1, scope_alias="H0001", sentence_aliases=("T0001",))],
            },
            {
                "role_id": "dsur",
                "aggregate_evidence_source_bundle_id": "bundle-dsur",
                "doc_id": "doc-dsur",
                "file_hash": "sha256:dsur",
                "scopes": [_scope(2, scope_alias="H0002", sentence_aliases=("T0002",))],
            },
        ],
    )


def _validated_candidates(
    *rows: tuple[str, str, tuple[str, ...]],
) -> ComparisonFindingAssessmentValidatedResponse:
    return ComparisonFindingAssessmentValidatedResponse(
        candidates=tuple(
            ComparisonFindingAssessmentCandidate(
                candidate_focus=focus,
                label=label,
                trigger_sentence_aliases=aliases,
            )
            for focus, label, aliases in rows
        ),
    )


def _scope_local_job() -> ComparisonFindingAssessmentJob:
    return ComparisonFindingAssessmentJob(
        comparison_mode_id="scope_local",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="scope",
                scope_aliases=("H0001",),
            ),
        ),
    )


def _focus_comparison_job() -> ComparisonFindingAssessmentJob:
    return ComparisonFindingAssessmentJob(
        comparison_mode_id="focus_comparison",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="focus_scope",
                scope_aliases=("H0001",),
            ),
            ComparisonFindingAssessmentGroup(
                group_role="comparison_scopes",
                scope_aliases=("H0002",),
            ),
        ),
    )


def _ib_to_dsur_job() -> ComparisonFindingAssessmentJob:
    return ComparisonFindingAssessmentJob(
        comparison_mode_id="ib_to_dsur",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="ib_scope",
                scope_aliases=("H0001",),
            ),
            ComparisonFindingAssessmentGroup(
                group_role="dsur_scopes",
                scope_aliases=("H0002",),
            ),
        ),
    )


def _dsur_to_ib_job() -> ComparisonFindingAssessmentJob:
    return ComparisonFindingAssessmentJob(
        comparison_mode_id="dsur_to_ib",
        groups=(
            ComparisonFindingAssessmentGroup(
                group_role="dsur_scopes",
                scope_aliases=("H0002",),
            ),
            ComparisonFindingAssessmentGroup(
                group_role="ib_scopes",
                scope_aliases=("H0001",),
            ),
        ),
    )


def test_collect_job_group_sentence_aliases_maps_group_roles() -> None:
    evidence = _two_scope_single_participant_evidence()
    job = _focus_comparison_job()
    grouped = collect_job_group_sentence_aliases(job=job, aggregate_comparison_evidence=evidence)
    assert grouped["focus_scope"] == frozenset({"T0001"})
    assert grouped["comparison_scopes"] == frozenset({"T0002"})


@pytest.mark.parametrize(
    ("raw_text", "match"),
    [
        ("not-json", "valid JSON"),
        (
            json.dumps({"unexpected": []}),
            "exactly one field: candidates",
        ),
        (
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "x",
                            "trigger_sentence_aliases": ["T0001"],
                        }
                    ]
                }
            ),
            "candidate_focus, label",
        ),
        (
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "x",
                            "label": "unknown",
                            "trigger_sentence_aliases": ["T0001"],
                        }
                    ]
                }
            ),
            "must be one of",
        ),
        (
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "x",
                            "label": "fail",
                            "trigger_sentence_aliases": ["BAD"],
                        }
                    ]
                }
            ),
            "Tdddd",
        ),
    ],
)
def test_strict_validation_remains_blocking(raw_text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_and_validate_comparison_finding_assessment_response(raw_text)


def test_scope_local_valid_alias_accepted() -> None:
    evidence = _single_scope_evidence()
    job = _scope_local_job()
    validated = _validated_candidates(("ok", "fail", ("T0001",)))
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    assert result.accepted_candidate_count == 1
    assert result.dropped_candidate_count == 0


def test_out_of_job_alias_drops_only_that_candidate() -> None:
    evidence = _single_scope_evidence()
    job = _scope_local_job()
    validated = _validated_candidates(
        ("good", "fail", ("T0001",)),
        ("bad", "fail", ("T0099",)),
    )
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    assert result.accepted_candidate_count == 1
    assert result.dropped_candidate_count == 1
    assert result.accepted_response.candidates[0].candidate_focus == "good"
    assert result.dropped_candidates[0].reason == "alias_outside_job_input"
    assert result.dropped_candidates[0].candidate_index == 1


def test_all_candidates_out_of_job_yield_empty_accepted() -> None:
    evidence = _single_scope_evidence()
    job = _scope_local_job()
    validated = _validated_candidates(("bad", "fail", ("T0099",)))
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    assert result.accepted_candidate_count == 0
    assert result.dropped_candidate_count == 1
    assert result.drop_reason_counts["alias_outside_job_input"] == 1


@pytest.mark.parametrize(
    ("aliases", "accepted"),
    [
        (("T0001", "T0002"), True),
        (("T0001",), False),
        (("T0002",), False),
    ],
)
def test_focus_comparison_side_coverage(aliases: tuple[str, ...], accepted: bool) -> None:
    evidence = _two_scope_single_participant_evidence()
    job = _focus_comparison_job()
    validated = _validated_candidates(("focus compare", "fail", aliases))
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    assert result.accepted_candidate_count == (1 if accepted else 0)
    if not accepted:
        assert result.dropped_candidates[0].reason == "missing_required_comparison_side"
        assert set(result.dropped_candidates[0].missing_group_roles) == {
            "focus_scope" if aliases == ("T0002",) else "comparison_scopes",
        }


@pytest.mark.parametrize(
    ("aliases", "accepted"),
    [
        (("T0001", "T0002"), True),
        (("T0001",), False),
        (("T0002",), False),
    ],
)
def test_ib_to_dsur_side_coverage(aliases: tuple[str, ...], accepted: bool) -> None:
    evidence = _cross_participant_evidence()
    job = _ib_to_dsur_job()
    validated = _validated_candidates(("cross", "fail", aliases))
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    assert result.accepted_candidate_count == (1 if accepted else 0)
    if not accepted:
        assert result.dropped_candidates[0].reason == "missing_required_comparison_side"


@pytest.mark.parametrize(
    ("aliases", "accepted"),
    [
        (("T0001", "T0002"), True),
        (("T0002",), False),
        (("T0001",), False),
    ],
)
def test_dsur_to_ib_side_coverage(aliases: tuple[str, ...], accepted: bool) -> None:
    evidence = _cross_participant_evidence()
    job = _dsur_to_ib_job()
    validated = _validated_candidates(("cross", "fail", aliases))
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    assert result.accepted_candidate_count == (1 if accepted else 0)
    if not accepted:
        assert result.dropped_candidates[0].reason == "missing_required_comparison_side"


def test_filtering_preserves_accepted_order_and_finding_ids() -> None:
    job = _scope_local_job()
    validated = _validated_candidates(
        ("first", "fail", ("T0001",)),
        ("second", "fail", ("T0099",)),
        ("third", "need_review", ("T0001",)),
    )
    evidence = _single_scope_evidence()
    result = filter_eligible_candidates(validated, job=job, aggregate_comparison_evidence=evidence)
    findings = assemble_findings_for_job(result.accepted_response, job=job)
    assert [finding.finding_id for finding in findings] == ["L001", "L002"]
    assert findings[0].conclusion == "first"
    assert findings[1].conclusion == "third"
    assert findings[0].label == "fail"
    assert findings[1].label == "need_review"
    assert findings[0].source_sentence_aliases == ("T0001",)
    assert findings[1].source_sentence_aliases == ("T0001",)


def _create_plan_run(tmp_path: Path, evidence: dict, run_id: str = "plan") -> Path:
    evidence_path = tmp_path / "aggregate_comparison_evidence.json"
    from runtime.io import save_json

    save_json(evidence_path, evidence)
    report = run_comparison_finding_assessment_plan_inspection(
        project_root=BACKEND_ROOT,
        evidence=evidence_path,
        capability_id="internal_dsur",
        output_dir=tmp_path / "plan",
        run_id=run_id,
    )
    return report.result.output_dir


def test_runtime_mixed_valid_and_out_of_job_alias_succeeds(tmp_path: Path) -> None:
    class _MixedProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="mixed",
                model="mixed",
                raw_text=json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_focus": "good",
                                "label": "fail",
                                "trigger_sentence_aliases": ["T0001"],
                            },
                            {
                                "candidate_focus": "bad",
                                "label": "fail",
                                "trigger_sentence_aliases": ["T0099"],
                            },
                        ]
                    }
                ),
            )

    plan_run_dir = _create_plan_run(tmp_path, _single_scope_evidence())
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_MixedProvider(),
        output_dir=tmp_path / "run",
        run_id="mixed_drop",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    result = report.result.job_results[0]
    assert result.status == "success"
    assert result.candidate_count == 2
    assert result.accepted_candidate_count == 1
    assert result.dropped_candidate_count == 1
    assert result.finding_count == 1
    eligibility = load_json(result.job_dir / "debug" / "candidate_eligibility.json")
    assert eligibility["drop_reason_counts"]["alias_outside_job_input"] == 1
    findings = load_json(report.result.output_dir / "findings.json")
    assert findings["jobs"][0]["findings"][0]["conclusion"] == "good"


def test_runtime_all_dropped_candidates_still_succeeds(tmp_path: Path) -> None:
    class _AllDroppedProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="all-dropped",
                model="all-dropped",
                raw_text=json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_focus": "bad-1",
                                "label": "fail",
                                "trigger_sentence_aliases": ["T0099"],
                            },
                            {
                                "candidate_focus": "bad-2",
                                "label": "fail",
                                "trigger_sentence_aliases": ["T0098"],
                            },
                        ]
                    }
                ),
            )

    plan_run_dir = _create_plan_run(tmp_path, _single_scope_evidence())
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_AllDroppedProvider(),
        output_dir=tmp_path / "run",
        run_id="all_dropped",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    result = report.result.job_results[0]
    assert result.status == "success"
    assert result.accepted_candidate_count == 0
    assert result.finding_count == 0
    findings = load_json(report.result.output_dir / "findings.json")
    assert findings["jobs"][0]["findings"] == []


def test_runtime_empty_candidates_array_succeeds(tmp_path: Path) -> None:
    class _EmptyProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="empty",
                model="empty",
                raw_text=json.dumps({"candidates": []}),
            )

    plan_run_dir = _create_plan_run(tmp_path, _single_scope_evidence())
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_EmptyProvider(),
        output_dir=tmp_path / "run",
        run_id="empty_candidates",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    result = report.result.job_results[0]
    assert result.status == "success"
    assert result.candidate_count == 0
    assert result.finding_count == 0
