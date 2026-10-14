"""Tests for Comparison Finding Verification execution runtime."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDINGS_FILENAME,
    build_findings,
    validate_findings,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    serialize_comparison_groups_for_provenance,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_PHASE,
    run_comparison_finding_assessment_execution,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    run_comparison_finding_assessment_plan_inspection,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    VALIDATED_RESPONSE_FILENAME,
    VERIFICATION_INPUT_FILENAME,
    run_comparison_finding_verification_execution,
)
from runtime.io import load_json, save_json
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    comparison_finding_verification_runner,
)
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_mock_provider import (
    ComparisonFindingVerificationStandaloneMockProvider,
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


class _RecordingAssessmentProvider:
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


class _RevisedAndAdditionalProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="scenario-mock",
            model="scenario-mock",
            raw_text=json.dumps(
                {
                    "finding_verifications": [
                        {
                            "finding_id": "L001",
                            "verification_result": "revised",
                            "conclusion": "corrected conclusion",
                            "label": "fail",
                            "source_sentence_aliases": ["T9999"],
                        }
                    ],
                    "additional_findings": [
                        {
                            "conclusion": "new additional",
                            "label": "fail",
                            "source_sentence_aliases": ["T0001"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )


class _InvalidJsonProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="invalid-mock",
            model="invalid-mock",
            raw_text="not-json",
        )


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
    findings_payload: dict[str, object],
    jobs: list[dict[str, object]],
    run_id: str = "assessment_test",
) -> None:
    findings_path = assessment_run_dir / "findings.json"
    save_json(findings_path, findings_payload)
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
                "findings": "findings.json",
            },
            "jobs": jobs,
        },
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


def _run_assessment_for_verification(tmp_path: Path) -> Path:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
    )
    report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingAssessmentProvider(),
        output_dir=tmp_path / "assessment",
        run_id="verification_upstream",
        comparison_modes=["scope_local"],
        max_jobs=1,
    )
    return report.result.output_dir


def test_runtime_mock_execution_requires_injected_provider(tmp_path: Path) -> None:
    assessment_run_dir = _run_assessment_for_verification(tmp_path)
    with pytest.raises(
        ValueError, match="mock execution requires an injected provider"
    ):
        run_comparison_finding_verification_execution(
            project_root=BACKEND_ROOT,
            assessment_run_dir=assessment_run_dir,
            llm_mode="mock",
            output_dir=tmp_path / "verification_no_provider",
        )


def test_runtime_mock_execution_end_to_end(tmp_path: Path) -> None:
    assessment_run_dir = _run_assessment_for_verification(tmp_path)
    report = run_comparison_finding_verification_execution(
        project_root=BACKEND_ROOT,
        assessment_run_dir=assessment_run_dir,
        llm_mode="mock",
        provider=ComparisonFindingVerificationStandaloneMockProvider(),
        output_dir=tmp_path / "verification",
        run_id="verification_ok",
    )
    assert report.result.job_results[0].status == "success"
    job_result = report.result.job_results[0]
    assert job_result.comparison_mode_id == "scope_local"
    assert job_result.prompt_id == "comparison_finding_verification.scope_local"
    assert job_result.prompt_version == "0.2.2"
    assert job_result.input_finding_count == 1
    assert job_result.finding_verification_count == 1
    assert job_result.additional_finding_count == 0
    assert job_result.confirmed_finding_count == 1
    assert job_result.revised_finding_count == 0
    assert job_result.rejected_finding_count == 0

    job_dir = report.result.output_dir / "jobs" / "001_scope_local"
    assert (job_dir / VERIFICATION_INPUT_FILENAME).is_file()
    assert (job_dir / "result.txt").is_file()
    validated = load_json(job_dir / VALIDATED_RESPONSE_FILENAME)
    assert validated["finding_verifications"] == [
        {"finding_id": "L001", "verification_result": "confirmed"}
    ]
    findings = load_json(report.result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings)
    assert findings["jobs"][0]["findings"][0]["finding_id"] == "L001"
    metadata = load_json(job_dir / "debug" / "run_metadata.json")
    assert metadata["prompt_id"] == "comparison_finding_verification.scope_local"
    assert metadata["prompt_version"] == "0.2.2"
    assert metadata["confirmed_finding_count"] == 1
    assert metadata["revised_finding_count"] == 0
    assert metadata["rejected_finding_count"] == 0
    assert metadata["response_format_applied"] is False
    summary = load_json(report.result.run_summary_path)
    assert summary["stats"]["adopted_finding_count"] == 1
    assert summary["jobs"][0]["adopted_finding_count"] == 1
    assert "final_finding_count" not in summary["stats"]
    assert "final_finding_count" not in summary["jobs"][0]
    assert summary["jobs"][0]["response_format_applied"] is False
    assert summary["stats"]["confirmed_finding_count"] == 1
    assert summary["stats"]["revised_finding_count"] == 0
    assert summary["stats"]["rejected_finding_count"] == 0


def test_api_execution_uses_formal_comparison_response_format_policy(
    tmp_path: Path,
) -> None:
    assessment_run_dir = _run_assessment_for_verification(tmp_path)
    captured: dict[str, object] = {}

    def fake_build_api_provider(
        **kwargs: object,
    ) -> ComparisonFindingVerificationStandaloneMockProvider:
        captured.update(kwargs)
        return ComparisonFindingVerificationStandaloneMockProvider()

    with patch(
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification.build_api_provider",
        new=fake_build_api_provider,
    ):
        report = run_comparison_finding_verification_execution(
            project_root=BACKEND_ROOT,
            assessment_run_dir=assessment_run_dir,
            llm_mode="api",
            llm_profile="qwen3_7_plus_2026_05_26",
            output_dir=tmp_path / "verification_formal_response_format_policy",
            run_id="verification_formal_response_format_policy",
        )

    assert captured["response_format"] is None
    job_result = report.result.job_results[0]
    runtime_request = load_json(
        job_result.job_dir / "debug" / "runtime_request.json"
    )
    assert runtime_request["response_format"] is None


def test_empty_findings_job_still_calls_provider(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
        run_id="plan_empty",
    )
    assessment_run_dir = tmp_path / "assessment_empty"
    assessment_run_dir.mkdir()
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_payload = build_findings(
        jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": job.comparison_mode_id,
                "comparison_groups": serialize_comparison_groups_for_provenance(job),
                "findings": [],
            }
        ]
    )
    _write_assessment_run_summary(
        assessment_run_dir=assessment_run_dir,
        plan_run_dir=plan_run_dir,
        evidence_path=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
        findings_payload=findings_payload,
        jobs=[
            {
                "frozen_job_index": 1,
                "execution_index": 1,
                "comparison_mode_id": "scope_local",
                "status": "success",
                "job_dir": "jobs/001_scope_local",
            }
        ],
        run_id="assessment_empty",
    )
    report = run_comparison_finding_verification_execution(
        project_root=BACKEND_ROOT,
        assessment_run_dir=assessment_run_dir,
        llm_mode="mock",
        provider=ComparisonFindingVerificationStandaloneMockProvider(),
        output_dir=tmp_path / "verification_empty",
        run_id="verification_empty",
    )
    job_result = report.result.job_results[0]
    assert job_result.status == "success"
    assert job_result.input_finding_count == 0
    assert job_result.finding_verification_count == 0
    validated = load_json(
        report.result.output_dir
        / "jobs"
        / "001_scope_local"
        / VALIDATED_RESPONSE_FILENAME
    )
    assert validated == {"finding_verifications": []}
    findings = load_json(report.result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings)
    assert findings["jobs"][0]["findings"] == []


def test_runtime_reconciliation_applies_revised_and_additional(
    tmp_path: Path,
) -> None:
    assessment_run_dir = _run_assessment_for_verification(tmp_path)
    report = run_comparison_finding_verification_execution(
        project_root=BACKEND_ROOT,
        assessment_run_dir=assessment_run_dir,
        llm_mode="mock",
        provider=_RevisedAndAdditionalProvider(),
        output_dir=tmp_path / "verification_reconcile",
        run_id="verification_reconcile",
    )
    job_result = report.result.job_results[0]
    assert job_result.status == "success"
    assert job_result.revised_finding_count == 1
    assert job_result.rejected_finding_count == 0
    assert job_result.accepted_additional_finding_count == 1
    assert job_result.dropped_additional_finding_count == 0
    assert job_result.adopted_finding_count == 2

    findings = load_json(report.result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings)
    job_findings = findings["jobs"][0]["findings"]
    assert job_findings[0] == {
        "finding_id": "L001",
        "conclusion": "corrected conclusion",
        "label": "fail",
        "source_sentence_aliases": ["T9999"],
    }
    assert job_findings[1]["finding_id"] == "L002"
    assert job_findings[1]["conclusion"] == "new additional"
    assert (
        report.result.output_dir
        / "jobs"
        / "001_scope_local"
        / "debug"
        / "additional_finding_eligibility.json"
    ).is_file()


def test_failed_verification_job_excluded_from_adopted_findings(tmp_path: Path) -> None:
    plan_run_dir = _create_plan_run(
        tmp_path,
        evidence=_INTERNAL_EVIDENCE,
        capability_id="internal_dsur",
        run_id="plan_partial",
    )
    assessment_report = run_comparison_finding_assessment_execution(
        project_root=BACKEND_ROOT,
        plan_run_dir=plan_run_dir,
        llm_mode="mock",
        provider=_RecordingAssessmentProvider(),
        output_dir=tmp_path / "assessment_partial",
        run_id="assessment_partial",
        max_jobs=2,
    )
    assessment_run_dir = assessment_report.result.output_dir

    class _FirstSuccessSecondFailProvider:
        def __init__(self) -> None:
            self._calls = 0

        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            self._calls += 1
            if self._calls == 1:
                return ComparisonFindingVerificationStandaloneMockProvider().generate(
                    messages
                )
            return _InvalidJsonProvider().generate(messages)

    report = run_comparison_finding_verification_execution(
        project_root=BACKEND_ROOT,
        assessment_run_dir=assessment_run_dir,
        llm_mode="mock",
        provider=_FirstSuccessSecondFailProvider(),
        output_dir=tmp_path / "verification_partial",
        run_id="verification_partial",
        max_concurrency=1,
    )
    successful = [
        result for result in report.result.job_results if result.status == "success"
    ]
    failed = [
        result for result in report.result.job_results if result.status == "failed"
    ]
    assert len(successful) == 1
    assert len(failed) == 1
    findings = load_json(report.result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings)
    assert len(findings["jobs"]) == 1
    assert findings["jobs"][0]["frozen_job_index"] == successful[0].frozen_job_index


def test_runner_injects_standalone_mock_provider(tmp_path: Path) -> None:
    assessment_run_dir = _run_assessment_for_verification(tmp_path)

    with patch(
        "scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.comparison_finding_verification_runner."
        "run_comparison_finding_verification_execution"
    ) as mocked:
        mocked.return_value = SimpleNamespace(messages=("ok",))
        comparison_finding_verification_runner.main(
            [
                "--assessment-run-dir",
                str(assessment_run_dir),
                "--llm",
                "mock",
                "--output-dir",
                str(tmp_path / "runner_out"),
            ]
        )
        _, kwargs = mocked.call_args
        provider = kwargs["provider"]
        assert isinstance(provider, ComparisonFindingVerificationStandaloneMockProvider)
