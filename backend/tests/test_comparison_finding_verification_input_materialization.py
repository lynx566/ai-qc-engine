"""Tests for Comparison Finding Verification input materialization."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
    build_findings,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
    materialize_comparison_finding_assessment_llm_input,
    plan_comparison_finding_assessment_jobs,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    VERIFICATION_FINDINGS_HEADING,
    VERIFICATION_SOURCE_SCOPE_HEADING,
    materialize_comparison_finding_verification_input,
    render_verification_findings_section,
    resolve_frozen_assessment_job,
    serialize_comparison_groups_for_provenance,
    verify_findings_job_matches_frozen_job,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_PHASE,
    resolve_comparison_finding_assessment_execution_handoff,
    run_comparison_finding_assessment_execution,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    run_comparison_finding_assessment_plan_inspection,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_handoff import (
    materialize_comparison_finding_verification_inputs_from_assessment_run,
)
from runtime.io import load_json, save_json

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
_CROSS_EVIDENCE = (
    _FIXTURE_ROOT / "dsur_updated_ib" / "aggregate_comparison_evidence.json"
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


def _findings_job_envelope(
    *,
    frozen_job_index: int,
    job: ComparisonFindingAssessmentJob,
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "frozen_job_index": frozen_job_index,
        "comparison_mode_id": job.comparison_mode_id,
        "comparison_groups": serialize_comparison_groups_for_provenance(job),
        "findings": findings or [],
    }


def _create_plan_run(
    tmp_path: Path,
    *,
    evidence: Path | str,
    capability_id: str,
    run_id: str = "plan_test",
) -> Path:
    report = run_comparison_finding_assessment_plan_inspection(
        project_root=BACKEND_ROOT,
        evidence=evidence,
        capability_id=capability_id,
        output_dir=tmp_path / "plan",
        run_id=run_id,
    )
    return report.result.output_dir


def _write_assessment_run_summary(
    *,
    assessment_run_dir: Path,
    plan_run_dir: Path,
    evidence_path: Path,
    capability_id: str,
    findings_ref: str | None,
    jobs: list[dict[str, object]],
    run_id: str = "assessment_test",
) -> None:
    save_json(
        assessment_run_dir / "run_summary.json",
        {
            "run_id": run_id,
            "stage": "evidence_comparison",
            "evidence_scope": "clinical_safety",
            "specialization": "aggregate",
            "phase": COMPARISON_FINDING_ASSESSMENT_PHASE,
            "inputs": {
                "source_plan_run": {
                    "run_id": run_id.replace("assessment", "plan"),
                    "run_dir": plan_run_dir.resolve().as_posix(),
                    "capability_id": capability_id,
                },
                "aggregate_comparison_evidence": {
                    "path": Path(evidence_path).resolve().as_posix(),
                    "resolved_from": "source_plan_run",
                },
            },
            "outputs": {
                "run_summary": "run_summary.json",
                "jobs_dir": "jobs",
                "findings": findings_ref,
            },
            "jobs": jobs,
        },
    )


class _RecordingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        alias = "T0001"
        if f"[{alias}]" not in user_content:
            first_line = next(
                (line for line in user_content.splitlines() if "[T" in line),
                user_content,
            )
            start = first_line.index("[T") + 1
            end = first_line.index("]", start)
            alias = first_line[start:end]
        payload = {
            "candidates": [
                {
                    "candidate_focus": "测试结论",
                    "label": "fail",
                    "trigger_sentence_aliases": [alias],
                }
            ]
        }
        return LLMRawResult(
            provider_name="recording-mock",
            model="recording-mock",
            raw_text=json.dumps(payload, ensure_ascii=False),
        )


class _MixedOutcomeProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "[T0016]" in user_content:
            raise RuntimeError("provider down")
        if "[T0019]" in user_content:
            return LLMRawResult(
                provider_name="mixed-mock",
                model="mixed-mock",
                raw_text="not-json",
            )
        payload = {
            "candidates": [
                {
                    "candidate_focus": "mixed",
                    "label": "fail",
                    "trigger_sentence_aliases": ["T0001"],
                }
            ]
        }
        return LLMRawResult(
            provider_name="mixed-mock",
            model="mixed-mock",
            raw_text=json.dumps(payload, ensure_ascii=False),
        )


def test_execution_handoff_resolves_plan_evidence_and_findings(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "assessment",
        run_id="handoff_ok",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    handoff = resolve_comparison_finding_assessment_execution_handoff(
        report.result.output_dir
    )
    assert handoff.plan_run_dir.resolve() == plan_run_dir.resolve()
    assert handoff.evidence_path.resolve() == _INTERNAL_EVIDENCE.resolve()
    assert handoff.findings_path == report.result.output_dir / "findings.json"
    assert handoff.successful_jobs[0].frozen_job_index == 1


def test_execution_handoff_rejects_wrong_phase(tmp_path: Path) -> None:
    assessment_run_dir = tmp_path / "bad_phase"
    assessment_run_dir.mkdir()
    save_json(
        assessment_run_dir / "run_summary.json",
        {
            "run_id": "bad",
            "stage": "evidence_comparison",
            "phase": "comparison_finding_assessment_plan",
            "inputs": {},
            "outputs": {},
            "jobs": [],
        },
    )
    with pytest.raises(ValueError, match="phase must be comparison_finding_assessment"):
        resolve_comparison_finding_assessment_execution_handoff(assessment_run_dir)


def test_execution_handoff_rejects_null_findings_ref(tmp_path: Path) -> None:
    assessment_run_dir = tmp_path / "no_findings"
    assessment_run_dir.mkdir()
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
        run_id="plan_no_findings",
    )
    _write_assessment_run_summary(
        assessment_run_dir=assessment_run_dir,
        plan_run_dir=plan_run_dir,
        evidence_path=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
        findings_ref=None,
        jobs=[],
    )
    with pytest.raises(ValueError, match="no findings artifact"):
        resolve_comparison_finding_assessment_execution_handoff(assessment_run_dir)


def test_frozen_job_index_resolves_unique_plan_job() -> None:
    evidence = _evidence()
    config = resolve_installed_comparison_finding_assessment_config("internal_dsur")
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    resolved = resolve_frozen_assessment_job(frozen_jobs=jobs, frozen_job_index=2)
    assert resolved.comparison_mode_id == "scope_local"
    assert resolved.groups[0].scope_aliases == ("H0002",)


def test_frozen_job_index_out_of_range_fails() -> None:
    evidence = _evidence()
    config = resolve_installed_comparison_finding_assessment_config("internal_dsur")
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    with pytest.raises(ValueError, match="frozen_job_index must be between"):
        resolve_frozen_assessment_job(frozen_jobs=jobs, frozen_job_index=999)


def test_provenance_mismatch_fails_on_mode_and_groups() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    envelope = _findings_job_envelope(frozen_job_index=1, job=job)
    wrong_mode = dict(envelope)
    wrong_mode["comparison_mode_id"] = "focus_comparison"
    with pytest.raises(ValueError, match="comparison_mode_id"):
        verify_findings_job_matches_frozen_job(
            wrong_mode,
            frozen_job=job,
            frozen_job_index=1,
        )
    wrong_groups = dict(envelope)
    wrong_groups["comparison_groups"] = [
        {"group_role": "scope", "scope_aliases": ["H0002"]},
    ]
    with pytest.raises(ValueError, match="comparison_groups"):
        verify_findings_job_matches_frozen_job(
            wrong_groups,
            frozen_job=job,
            frozen_job_index=1,
        )


@pytest.mark.parametrize(
    ("comparison_mode_id", "groups"),
    [
        ("scope_local", (("scope", ("H0001",)),)),
        (
            "focus_comparison",
            (
                ("focus_scope", ("H0002",)),
                ("comparison_scopes", ("H0003", "H0001")),
            ),
        ),
        (
            "ib_to_dsur",
            (
                ("ib_scope", ("H0003",)),
                ("dsur_scopes", ("H0001", "H0002")),
            ),
        ),
        (
            "dsur_to_ib",
            (
                ("dsur_scopes", ("H0001", "H0002")),
                ("ib_scopes", ("H0003",)),
            ),
        ),
    ],
)
def test_source_scope_matches_assessment_materializer(
    comparison_mode_id: str,
    groups: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    evidence = _evidence()
    job = _job(comparison_mode_id, *groups)
    envelope = _findings_job_envelope(frozen_job_index=1, job=job)
    materialized = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=evidence,
        findings_job_envelope=envelope,
        frozen_job_index=1,
    )
    expected = materialize_comparison_finding_assessment_llm_input(
        job=job,
        aggregate_comparison_evidence=evidence,
    )
    assert materialized.source_scope_text == expected


def test_findings_rendering_preserves_order_and_fields() -> None:
    rendered = render_verification_findings_section(
        [
            {
                "finding_id": "L001",
                "conclusion": "第一条",
                "label": "pass",
                "source_sentence_aliases": ["T0001", "T0002"],
            },
            {
                "finding_id": "L002",
                "conclusion": "第二条",
                "label": "fail",
                "source_sentence_aliases": ["T0003"],
            },
        ]
    )
    assert rendered == (
        "L001\n"
        "- `conclusion`: 第一条\n"
        "- `label`: pass\n"
        "- `source_sentence_aliases`: T0001, T0002\n"
        "L002\n"
        "- `conclusion`: 第二条\n"
        "- `label`: fail\n"
        "- `source_sentence_aliases`: T0003"
    )


def test_empty_findings_section_and_full_input(tmp_path: Path) -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    evidence = _evidence()
    envelope = _findings_job_envelope(frozen_job_index=1, job=job, findings=[])
    materialized = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=evidence,
        findings_job_envelope=envelope,
        frozen_job_index=1,
    )
    source_scope = materialize_comparison_finding_assessment_llm_input(
        job=job,
        aggregate_comparison_evidence=evidence,
    )
    assert materialized.user_input_text == (
        f"{VERIFICATION_SOURCE_SCOPE_HEADING}\n"
        f"{source_scope}\n\n"
        f"{VERIFICATION_FINDINGS_HEADING}\n"
    )


def test_materialize_from_assessment_run_end_to_end(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingProvider(),
        output_dir=tmp_path / "assessment",
        run_id="materialize_ok",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    inputs = materialize_comparison_finding_verification_inputs_from_assessment_run(
        report.result.output_dir
    )
    assert len(inputs) == 1
    assert inputs[0].frozen_job_index == 1
    assert inputs[0].findings[0]["finding_id"] == "L001"
    assert VERIFICATION_SOURCE_SCOPE_HEADING in inputs[0].user_input_text
    assert VERIFICATION_FINDINGS_HEADING in inputs[0].user_input_text


def test_success_job_subset_only_materializes_findings_jobs(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_MixedOutcomeProvider(),
        output_dir=tmp_path / "assessment_mixed",
        run_id="mixed_subset",
        comparison_modes=["scope_local"],
        max_jobs=4,
    )
    assert [result.status for result in report.result.job_results] == [
        "success",
        "failed",
        "failed",
        "success",
    ]
    inputs = materialize_comparison_finding_verification_inputs_from_assessment_run(
        report.result.output_dir
    )
    assert [item.frozen_job_index for item in inputs] == [1, 4]


def test_cross_artifact_ib_to_dsur_source_scope_equivalence() -> None:
    evidence = load_json(_CROSS_EVIDENCE)
    config = resolve_installed_comparison_finding_assessment_config("dsur_updated_ib")
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    ib_to_dsur_job = next(job for job in jobs if job.comparison_mode_id == "ib_to_dsur")
    frozen_job_index = jobs.index(ib_to_dsur_job) + 1
    envelope = _findings_job_envelope(
        frozen_job_index=frozen_job_index,
        job=ib_to_dsur_job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "cross",
                "label": "pass",
                "source_sentence_aliases": ["T0001", "T0002"],
            }
        ],
    )
    materialized = materialize_comparison_finding_verification_input(
        job=ib_to_dsur_job,
        aggregate_comparison_evidence=evidence,
        findings_job_envelope=envelope,
        frozen_job_index=frozen_job_index,
    )
    expected = materialize_comparison_finding_assessment_llm_input(
        job=ib_to_dsur_job,
        aggregate_comparison_evidence=evidence,
    )
    assert materialized.source_scope_text == expected
    assert materialized.source_scope_text.startswith("## IB Scope\n")


def test_build_findings_job_envelope_supports_empty_findings() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    payload = build_findings(
        jobs=[_findings_job_envelope(frozen_job_index=1, job=job, findings=[])]
    )
    assert payload["jobs"][0]["findings"] == []
