"""Tests for pipelined canonical aggregate Evidence Comparison execution."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from threading import Condition, Event, Lock
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from application.clinical_trial_doc_consistency_qc.comparison_finding_consolidation_installation import (
    resolve_installed_comparison_finding_consolidation_config,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.final_findings import (
    validate_final_findings,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    validate_findings,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import (
    AggregateEvidenceComparisonExecutionInput,
    AggregateEvidenceComparisonFinalizationFailure,
    AggregateEvidenceComparisonFinalizationError,
    AggregateEvidenceComparisonPreFinalState,
    execute_clinical_trial_aggregate_evidence_comparison,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.execution import (
    ComparisonFindingAssessmentJobExecution,
    execute_comparison_finding_assessment_job,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.planner import (
    plan_comparison_finding_assessment_jobs,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification.execution import (
    execute_comparison_finding_verification_job,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution import (
    run_aggregate_evidence_comparison_execution,
)
from runtime.io import load_json
from tests.test_aggregate_evidence_comparison_execution import (
    _FailingProvider,
    _invocation_from_evidence,
)

_FIXTURE_EVIDENCE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
    / "internal_dsur"
    / "aggregate_comparison_evidence.json"
)


def _first_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in prompt")
    return match.group(1)


def _planned_subset(job_count: int = 4) -> tuple[ComparisonFindingAssessmentJob, ...]:
    evidence = load_json(_FIXTURE_EVIDENCE)
    config = resolve_installed_comparison_finding_assessment_config("internal_dsur")
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    return tuple(jobs[:job_count])


def _execution_input(
    *,
    assessment_provider,
    assessment_second_pass_provider=None,
    verification_provider,
    consolidation_config=None,
    consolidation_provider=None,
    max_concurrency: int | None = 2,
) -> AggregateEvidenceComparisonExecutionInput:
    evidence_payload = load_json(_FIXTURE_EVIDENCE)
    return AggregateEvidenceComparisonExecutionInput(
        invocation=_invocation_from_evidence(evidence_payload),
        assessment_config=resolve_installed_comparison_finding_assessment_config(
            "internal_dsur"
        ),
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=(
            assessment_provider
            if assessment_second_pass_provider is None
            else assessment_second_pass_provider
        ),
        verification_provider=verification_provider,
        consolidation_config=(
            resolve_installed_comparison_finding_consolidation_config(
                "dsur_updated_ib"
            )
            if consolidation_config is None
            else consolidation_config
        ),
        consolidation_provider=(
            _FailingProvider()
            if consolidation_provider is None
            else consolidation_provider
        ),
        max_concurrency=max_concurrency,
    )


def _valid_assessment_response(messages: list[dict[str, str]]) -> LLMRawResult:
    alias = _first_alias(messages)
    return LLMRawResult(
        provider_name="pipeline-mock",
        model="pipeline-mock",
        raw_text=json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": f"candidate for {alias}",
                        "label": "fail",
                        "trigger_sentence_aliases": [alias],
                    }
                ]
            }
        ),
    )


def _valid_focus_assessment_response(
    messages: list[dict[str, str]],
) -> LLMRawResult:
    aliases = tuple(dict.fromkeys(re.findall(r"\[(T\d{4})\]", messages[-1]["content"])))
    return LLMRawResult(
        provider_name="pipeline-mock",
        model="pipeline-mock",
        raw_text=json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": "candidate spanning both focus sides",
                        "label": "fail",
                        "trigger_sentence_aliases": list(aliases),
                    }
                ]
            }
        ),
    )


def _valid_verification_response(messages: list[dict[str, str]]) -> LLMRawResult:
    user_content = messages[-1]["content"]
    finding_ids: list[str] = []
    if "## Findings" in user_content:
        marker = "## Findings\n"
        findings_section = user_content.split(marker, 1)[1]
        for line in findings_section.splitlines():
            stripped = line.strip()
            if (
                stripped.startswith("L")
                and len(stripped) == 4
                and stripped[1:].isdigit()
            ):
                finding_ids.append(stripped)
    return LLMRawResult(
        provider_name="pipeline-mock",
        model="pipeline-mock",
        raw_text=json.dumps(
            {
                "finding_verifications": [
                    {
                        "finding_id": finding_id,
                        "verification_result": "confirmed",
                    }
                    for finding_id in finding_ids
                ],
                "additional_findings": [],
            }
        ),
    )


def _valid_consolidation_response(
    _messages: list[dict[str, str]],
) -> LLMRawResult:
    return LLMRawResult(
        provider_name="pipeline-consolidation-mock",
        model="pipeline-consolidation-mock",
        raw_text=json.dumps({"consolidated_groups": []}),
    )


def _alias_mismatch_consolidation_response(
    _messages: list[dict[str, str]],
) -> LLMRawResult:
    return LLMRawResult(
        provider_name="pipeline-consolidation-mock",
        model="pipeline-consolidation-mock",
        raw_text=json.dumps(
            {
                "consolidated_groups": [
                    {
                        "conclusion_aliases": ["C001", "C002"],
                        "unified_conclusion": "Unified",
                        "combined_sentence_aliases": ["T9999"],
                    }
                ]
            }
        ),
    )


def _invalid_consolidation_response(
    _messages: list[dict[str, str]],
) -> LLMRawResult:
    return LLMRawResult(
        provider_name="pipeline-consolidation-mock",
        model="pipeline-consolidation-mock",
        raw_text=json.dumps(
            {
                "consolidated_groups": [
                    {
                        "conclusion_aliases": ["C001"],
                        "unified_conclusion": "Invalid singleton",
                        "combined_sentence_aliases": ["T0001"],
                    }
                ]
            }
        ),
    )


def _unparseable_consolidation_response(
    _messages: list[dict[str, str]],
) -> LLMRawResult:
    return LLMRawResult(
        provider_name="pipeline-consolidation-mock",
        model="pipeline-consolidation-mock",
        raw_text="not json",
    )


def _focus_planned_subset(job_count: int) -> tuple[ComparisonFindingAssessmentJob, ...]:
    return tuple(
        job
        for job in _planned_subset(20)
        if job.comparison_mode_id == "focus_comparison"
    )[:job_count]


class _PipelineMockProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        if "## Findings" in messages[-1]["content"]:
            return _valid_verification_response(messages)
        return _valid_assessment_response(messages)


class _BlockingConcurrencyProvider:
    def __init__(self) -> None:
        self._condition = Condition()
        self._release = Event()
        self.active_call_count = 0
        self.peak_active_call_count = 0

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        with self._condition:
            self.active_call_count += 1
            self.peak_active_call_count = max(
                self.peak_active_call_count,
                self.active_call_count,
            )
            self._condition.notify_all()
        try:
            if not self._release.wait(timeout=10):
                raise AssertionError("test did not release blocked provider calls")
            if "## Findings" in messages[-1]["content"]:
                return _valid_verification_response(messages)
            return _valid_assessment_response(messages)
        finally:
            with self._condition:
                self.active_call_count -= 1
                self._condition.notify_all()

    def wait_for_peak(self, expected: int) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self.peak_active_call_count >= expected,
                timeout=5,
            )

    def release(self) -> None:
        self._release.set()


class _OverlapObservationProvider:
    """No-op provider; overlap is observed via execution-layer hooks."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        if "## Findings" in messages[-1]["content"]:
            return _valid_verification_response(messages)
        return _valid_assessment_response(messages)


class _BlockingAssessmentJobTwoGate:
    def __init__(self) -> None:
        self._release = Event()

    def wait(self) -> None:
        if not self._release.wait(timeout=10):
            raise AssertionError("job 2 assessment gate was not released")

    def release(self) -> None:
        self._release.set()


class _EmptyCandidatesAssessmentProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        if "## Findings" in messages[-1]["content"]:
            return LLMRawResult(
                provider_name="empty-assessment",
                model="empty-assessment",
                raw_text=json.dumps(
                    {"finding_verifications": [], "additional_findings": []}
                ),
            )
        return LLMRawResult(
            provider_name="empty-assessment",
            model="empty-assessment",
            raw_text=json.dumps({"candidates": []}),
        )


class _RecordingProvider:
    def __init__(self, response_factory) -> None:
        self.response_factory = response_factory
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        return self.response_factory(messages)


def _empty_assessment_response(_messages: list[dict[str, str]]) -> LLMRawResult:
    return LLMRawResult(
        provider_name="empty-assessment",
        model="empty-assessment",
        raw_text=json.dumps({"candidates": []}),
    )


def _ineligible_assessment_response(
    _messages: list[dict[str, str]],
) -> LLMRawResult:
    return LLMRawResult(
        provider_name="ineligible-assessment",
        model="ineligible-assessment",
        raw_text=json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": "candidate outside the job",
                        "label": "fail",
                        "trigger_sentence_aliases": ["T9999"],
                    }
                ]
            }
        ),
    )


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(2),
)
def test_verification_can_start_before_later_assessments_finish(_mock_plan) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Condition

    provider = _OverlapObservationProvider()
    gate = _BlockingAssessmentJobTwoGate()
    pending_assessments = {1, 2}
    overlap_observed = False
    overlap_condition = Condition()
    original_assessment = execute_comparison_finding_assessment_job
    original_verification = execute_comparison_finding_verification_job

    def _tracked_assessment(**kwargs):
        if kwargs["frozen_job_index"] == 2:
            gate.wait()
        result = original_assessment(**kwargs)
        with overlap_condition:
            pending_assessments.discard(kwargs["frozen_job_index"])
            overlap_condition.notify_all()
        return result

    def _tracked_verification(**kwargs):
        nonlocal overlap_observed
        with overlap_condition:
            if pending_assessments:
                overlap_observed = True
                overlap_condition.notify_all()
        return original_verification(**kwargs)

    with (
        patch(
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
            "aggregate_evidence.execution.execute_comparison_finding_assessment_job",
            side_effect=_tracked_assessment,
        ),
        patch(
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
            "aggregate_evidence.execution.execute_comparison_finding_verification_job",
            side_effect=_tracked_verification,
        ),
        ThreadPoolExecutor(max_workers=1) as harness,
    ):
        future = harness.submit(
            run_aggregate_evidence_comparison_execution,
            execution_input=_execution_input(
                assessment_provider=provider,
                verification_provider=provider,
                max_concurrency=2,
            ),
        )
        with overlap_condition:
            assert overlap_condition.wait_for(lambda: overlap_observed, timeout=5)
        gate.release()
        result = future.result(timeout=15)

    assert overlap_observed
    assert result.run_status == "success"
    assert result.verification_success_count == 2


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(4),
)
def test_verification_not_starved_by_queued_later_assessments(_mock_plan) -> None:
    """V1 must start before A3/A4 when A2 blocks and max_concurrency=2."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Condition

    provider = _OverlapObservationProvider()
    gate = _BlockingAssessmentJobTwoGate()
    assessment_started: set[int] = set()
    verification_started: set[int] = set()
    observation = Condition()
    original_assessment = execute_comparison_finding_assessment_job
    original_verification = execute_comparison_finding_verification_job

    def _tracked_assessment(**kwargs):
        frozen_job_index = kwargs["frozen_job_index"]
        with observation:
            assessment_started.add(frozen_job_index)
            observation.notify_all()
        if frozen_job_index == 2:
            gate.wait()
        return original_assessment(**kwargs)

    def _tracked_verification(**kwargs):
        frozen_job_index = kwargs["verification_input"].frozen_job_index
        with observation:
            verification_started.add(frozen_job_index)
            observation.notify_all()
        return original_verification(**kwargs)

    with (
        patch(
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
            "aggregate_evidence.execution.execute_comparison_finding_assessment_job",
            side_effect=_tracked_assessment,
        ),
        patch(
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
            "aggregate_evidence.execution.execute_comparison_finding_verification_job",
            side_effect=_tracked_verification,
        ),
        ThreadPoolExecutor(max_workers=1) as harness,
    ):
        future = harness.submit(
            run_aggregate_evidence_comparison_execution,
            execution_input=_execution_input(
                assessment_provider=provider,
                verification_provider=provider,
                max_concurrency=2,
            ),
        )
        with observation:
            assert observation.wait_for(lambda: 1 in verification_started, timeout=5)
            assert 3 not in assessment_started
            assert 4 not in assessment_started
            assert 2 in assessment_started
        gate.release()
        result = future.result(timeout=15)

    assert result.run_status == "success"
    assert result.verification_success_count == 4


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(4),
)
def test_assessment_jobs_remain_concurrent_under_pipeline(_mock_plan) -> None:
    from concurrent.futures import ThreadPoolExecutor

    provider = _BlockingConcurrencyProvider()
    with ThreadPoolExecutor(max_workers=1) as harness:
        future = harness.submit(
            run_aggregate_evidence_comparison_execution,
            execution_input=_execution_input(
                assessment_provider=provider,
                verification_provider=provider,
                max_concurrency=2,
            ),
        )
        try:
            assert provider.wait_for_peak(2)
        finally:
            provider.release()
        result = future.result(timeout=15)

    assert provider.peak_active_call_count >= 2
    assert result.assessment_success_count == 4


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(3),
)
def test_finding_ids_ignore_assessment_completion_order(_mock_plan) -> None:
    from concurrent.futures import ThreadPoolExecutor

    provider = _PipelineMockProvider()
    ready = {index: Event() for index in (1, 2, 3)}
    release = {index: Event() for index in (1, 2, 3)}
    completed = {index: Event() for index in (1, 2, 3)}
    completion_order: list[int] = []
    completion_lock = Lock()
    original_assessment = execute_comparison_finding_assessment_job

    def _controlled_assessment(**kwargs):
        result = original_assessment(**kwargs)
        frozen_job_index = kwargs["frozen_job_index"]
        ready[frozen_job_index].set()
        if not release[frozen_job_index].wait(timeout=10):
            raise AssertionError(
                f"assessment job {frozen_job_index} delivery was not released"
            )
        with completion_lock:
            completion_order.append(frozen_job_index)
        completed[frozen_job_index].set()
        return result

    with (
        patch(
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
            "aggregate_evidence.execution.execute_comparison_finding_assessment_job",
            side_effect=_controlled_assessment,
        ),
        ThreadPoolExecutor(max_workers=1) as harness,
    ):
        future = harness.submit(
            run_aggregate_evidence_comparison_execution,
            execution_input=_execution_input(
                assessment_provider=provider,
                verification_provider=provider,
                max_concurrency=3,
            ),
        )
        for frozen_job_index in (1, 2, 3):
            assert ready[frozen_job_index].wait(timeout=5), (
                f"assessment job {frozen_job_index} did not reach the delivery gate"
            )
        for frozen_job_index in (3, 2, 1):
            release[frozen_job_index].set()
            assert completed[frozen_job_index].wait(timeout=5), (
                f"assessment job {frozen_job_index} did not complete delivery"
            )
        result = future.result(timeout=15)

    assert completion_order == [3, 2, 1]
    assert result.job_final_findings is not None
    findings_by_job = [
        (
            job["frozen_job_index"],
            [finding["finding_id"] for finding in job["findings"]],
        )
        for job in result.job_final_findings["jobs"]
    ]
    assert findings_by_job == [
        (1, ["L001"]),
        (2, ["L002"]),
        (3, ["L003"]),
    ]
    finding_ids = [
        finding["finding_id"]
        for job in result.job_final_findings["jobs"]
        for finding in job["findings"]
    ]
    assert finding_ids == ["L001", "L002", "L003"]


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(3),
)
def test_failed_assessment_skips_verification(_mock_plan) -> None:
    provider = _PipelineMockProvider()
    original_execute = execute_comparison_finding_assessment_job

    def _execute_with_job_two_failure(**kwargs):
        if kwargs["frozen_job_index"] == 2:
            return ComparisonFindingAssessmentJobExecution(
                frozen_job_index=2,
                execution_index=kwargs["execution_index"],
                job=kwargs["job"],
                status="failed",
                prompt_id="comparison_finding_assessment.scope_local",
                prompt_version="0.1.0",
                parse_status="not_attempted",
                validation_status="not_attempted",
                error_message="forced assessment failure",
            )
        return original_execute(**kwargs)

    with patch(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.execution.execute_comparison_finding_assessment_job",
        side_effect=_execute_with_job_two_failure,
    ):
        result = run_aggregate_evidence_comparison_execution(
            execution_input=_execution_input(
                assessment_provider=provider,
                verification_provider=provider,
            ),
        )
    assert result.assessment_failed_count == 1
    assert result.verification is not None
    assert result.verification_success_count == 2
    assert {
        execution.frozen_job_index for execution in result.verification.job_executions
    } == {
        1,
        3,
    }
    assert result.run_status == "partial_failure"
    assert result.final_findings["finalization_status"] == "completed"
    assert result.final_findings["fallback_comparison_modes"] == []


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: (
        ComparisonFindingAssessmentJob(
            comparison_mode_id="scope_local",
            groups=(
                ComparisonFindingAssessmentGroup(
                    group_role="scope",
                    scope_aliases=("H0001",),
                ),
            ),
        ),
    ),
)
def test_empty_primary_runs_second_pass_and_skips_verification(_mock_plan) -> None:
    primary_provider = _RecordingProvider(_empty_assessment_response)
    second_pass_provider = _RecordingProvider(_valid_assessment_response)
    verification_provider = _RecordingProvider(_valid_verification_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=primary_provider,
            assessment_second_pass_provider=second_pass_provider,
            verification_provider=verification_provider,
        ),
    )
    assert result.assessment_success_count == 1
    assert result.second_pass_assessment is not None
    assert result.second_pass_assessment.success_count == 1
    assert result.verification is None
    assert len(primary_provider.calls) == 1
    assert len(second_pass_provider.calls) == 1
    assert verification_provider.calls == []
    second_pass_finding = result.job_final_findings["jobs"][0]["findings"][0]
    assert set(second_pass_finding) == {
        "finding_id",
        "conclusion",
        "label",
        "source_sentence_aliases",
    }
    assert second_pass_finding["finding_id"] == "L001"
    assert second_pass_finding["conclusion"].startswith("candidate for T")
    assert second_pass_finding["label"] == "fail"
    assert second_pass_finding["source_sentence_aliases"]


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(1),
)
def test_normal_branch_skips_second_pass_and_runs_verification(_mock_plan) -> None:
    primary_provider = _RecordingProvider(_valid_assessment_response)
    second_pass_provider = _RecordingProvider(_valid_assessment_response)
    verification_provider = _RecordingProvider(_valid_verification_response)

    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=primary_provider,
            assessment_second_pass_provider=second_pass_provider,
            verification_provider=verification_provider,
        ),
    )

    assert len(primary_provider.calls) == 1
    assert second_pass_provider.calls == []
    assert len(verification_provider.calls) == 1
    assert result.second_pass_assessment is None
    assert result.verification is not None
    assert result.job_final_findings == result.verification.findings_artifact


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(2),
)
def test_mixed_branches_share_global_finding_id_allocation(_mock_plan) -> None:
    primary_call_count = 0

    def _primary_response(messages: list[dict[str, str]]) -> LLMRawResult:
        nonlocal primary_call_count
        primary_call_count += 1
        if primary_call_count == 1:
            return _empty_assessment_response(messages)
        return _valid_assessment_response(messages)

    second_pass_provider = _RecordingProvider(_valid_assessment_response)
    verification_provider = _RecordingProvider(_valid_verification_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_primary_response),
            assessment_second_pass_provider=second_pass_provider,
            verification_provider=verification_provider,
            max_concurrency=1,
        ),
    )

    assert len(second_pass_provider.calls) == 1
    assert len(verification_provider.calls) == 1
    assert [
        finding["finding_id"]
        for job in result.job_final_findings["jobs"]
        for finding in job["findings"]
    ] == ["L001", "L002"]


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(1),
)
def test_all_primary_candidates_filtered_runs_second_pass(_mock_plan) -> None:
    primary_provider = _RecordingProvider(_ineligible_assessment_response)
    second_pass_provider = _RecordingProvider(_valid_assessment_response)
    verification_provider = _RecordingProvider(_valid_verification_response)

    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=primary_provider,
            assessment_second_pass_provider=second_pass_provider,
            verification_provider=verification_provider,
        ),
    )

    assert result.assessment.job_executions[0].candidate_count == 1
    assert result.assessment.job_executions[0].accepted_candidate_count == 0
    assert len(second_pass_provider.calls) == 1
    assert verification_provider.calls == []
    assert result.job_final_finding_count == 1


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(1),
)
def test_empty_second_pass_is_successful_final_empty_result(_mock_plan) -> None:
    primary_provider = _RecordingProvider(_empty_assessment_response)
    second_pass_provider = _RecordingProvider(_empty_assessment_response)
    verification_provider = _RecordingProvider(_valid_verification_response)

    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=primary_provider,
            assessment_second_pass_provider=second_pass_provider,
            verification_provider=verification_provider,
        ),
    )

    assert result.run_status == "success"
    assert result.verification is None
    assert len(primary_provider.calls) == 1
    assert len(second_pass_provider.calls) == 1
    assert verification_provider.calls == []
    assert result.job_final_findings["jobs"][0]["findings"] == []


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(1),
)
def test_second_pass_finalization_uses_accepted_findings_not_raw_candidates(
    _mock_plan,
) -> None:
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_empty_assessment_response),
            assessment_second_pass_provider=_RecordingProvider(
                _ineligible_assessment_response
            ),
            verification_provider=_RecordingProvider(_valid_verification_response),
        ),
    )

    second_pass_job = result.second_pass_assessment.job_executions[0]
    assert second_pass_job.candidate_count == 1
    assert second_pass_job.accepted_candidate_count == 0
    assert second_pass_job.finding_count == 0
    assert result.job_final_findings["jobs"][0]["findings"] == []


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(1),
)
def test_second_pass_failure_preserves_failure_semantics(_mock_plan) -> None:
    primary_provider = _RecordingProvider(_empty_assessment_response)
    verification_provider = _RecordingProvider(_valid_verification_response)

    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=primary_provider,
            assessment_second_pass_provider=_FailingProvider(),
            verification_provider=verification_provider,
        ),
    )

    assert result.run_status == "failed"
    assert result.second_pass_assessment is not None
    assert result.second_pass_assessment.failed_count == 1
    assert result.verification is None
    assert result.job_final_findings is None
    assert verification_provider.calls == []


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(2),
)
def test_public_execution_contract_exposes_job_final_findings(_mock_plan) -> None:
    provider = _PipelineMockProvider()
    result = execute_clinical_trial_aggregate_evidence_comparison(
        invocation=_execution_input(
            assessment_provider=provider,
            verification_provider=provider,
        ),
    )
    assert hasattr(result, "assessment")
    assert hasattr(result, "verification")
    assert hasattr(result, "second_pass_assessment")
    assert hasattr(result, "job_final_findings")
    assert hasattr(result, "final_findings")
    assert hasattr(result, "final_finding_count")
    assert hasattr(result, "run_status")
    assert result.assessment.job_executions
    assert result.verification is not None
    assert result.verification.job_executions
    validate_findings(result.job_final_findings)
    validate_final_findings(result.final_findings)
    assert result.final_finding_count == len(result.final_findings["findings"])


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(4),
)
def test_installed_concurrency_cap_holds_with_assessment_verification_overlap(
    _mock_plan,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    provider = _BlockingConcurrencyProvider()
    with ThreadPoolExecutor(max_workers=1) as harness:
        future = harness.submit(
            run_aggregate_evidence_comparison_execution,
            execution_input=_execution_input(
                assessment_provider=provider,
                verification_provider=provider,
                max_concurrency=2,
            ),
        )
        try:
            assert provider.wait_for_peak(2)
            peak_during_run = provider.peak_active_call_count
        finally:
            provider.release()
        result = future.result(timeout=15)

    assert peak_during_run <= 2
    assert provider.peak_active_call_count <= 2
    assert result.run_status == "success"


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _planned_subset(4),
)
def test_all_assessment_failed_skips_verification(_mock_plan) -> None:
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_FailingProvider(),
            verification_provider=_FailingProvider(),
        ),
    )
    assert result.run_status == "failed"
    assert result.verification is None


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(2),
)
def test_consolidation_runs_once_after_final_focus_rows_are_available(
    _mock_plan,
) -> None:
    events: list[str] = []

    def assessment_response(messages: list[dict[str, str]]) -> LLMRawResult:
        events.append("assessment")
        return _valid_focus_assessment_response(messages)

    def verification_response(messages: list[dict[str, str]]) -> LLMRawResult:
        events.append("verification")
        return _valid_verification_response(messages)

    def consolidation_response(messages: list[dict[str, str]]) -> LLMRawResult:
        events.append("consolidation")
        assert "Conclusion C001" in messages[-1]["content"]
        assert "Conclusion C002" in messages[-1]["content"]
        return _valid_consolidation_response(messages)

    consolidation_provider = _RecordingProvider(consolidation_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(assessment_response),
            verification_provider=_RecordingProvider(verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        )
    )

    assert events[-1] == "consolidation"
    assert len(consolidation_provider.calls) == 1
    assert len(result.consolidation_executions) == 1
    assert result.consolidation_executions[0].comparison_mode_id == "focus_comparison"
    assert result.consolidation_executions[0].finding_count == 2
    assert result.run_status == "success"
    assert result.job_final_finding_count == 2
    assert result.final_finding_count == 2
    assert result.final_findings["finalization_status"] == "completed"


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(2),
)
def test_disabled_consolidation_modes_are_identity(_mock_plan) -> None:
    consolidation_provider = _RecordingProvider(_valid_consolidation_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_valid_focus_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        )
    )

    assert result.consolidation_executions == ()
    assert consolidation_provider.calls == []
    assert result.run_status == "success"
    assert result.final_finding_count == result.job_final_finding_count
    assert [
        finding["source_finding_ids"]
        for finding in result.final_findings["findings"]
    ] == [["L001"], ["L002"]]


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(1),
)
def test_one_final_finding_produces_aggregate_noop(_mock_plan) -> None:
    consolidation_provider = _RecordingProvider(_valid_consolidation_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_valid_focus_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        )
    )

    assert len(result.consolidation_executions) == 1
    execution = result.consolidation_executions[0]
    assert execution.status == "success"
    assert execution.finding_count == 1
    assert execution.provider_called is False
    assert execution.validated_response is not None
    assert execution.validated_response.consolidated_groups == ()
    assert consolidation_provider.calls == []
    assert result.final_finding_count == result.job_final_finding_count == 1
    assert result.final_findings["finalization_status"] == "completed"


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(1),
)
def test_zero_job_final_findings_produces_aggregate_noop(_mock_plan) -> None:
    consolidation_provider = _RecordingProvider(_valid_consolidation_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_empty_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        )
    )

    assert len(result.consolidation_executions) == 1
    execution = result.consolidation_executions[0]
    assert execution.status == "success"
    assert execution.finding_count == 0
    assert execution.provider_called is False
    assert execution.validated_response is not None
    assert execution.validated_response.consolidated_groups == ()
    assert consolidation_provider.calls == []
    assert result.final_findings == {
        "artifact_type": "final_findings",
        "schema_version": "0.1.0",
        "finalization_status": "completed",
        "fallback_comparison_modes": [],
        "findings": [],
    }
    assert result.final_finding_count == 0


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(2),
)
def test_alias_qc_mismatch_remains_aggregate_success(_mock_plan) -> None:
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_valid_focus_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=_RecordingProvider(
                _alias_mismatch_consolidation_response
            ),
            max_concurrency=1,
        )
    )

    execution = result.consolidation_executions[0]
    assert execution.status == "success"
    assert execution.alias_qc is not None
    assert execution.alias_qc.all_groups_match is False
    assert result.run_status == "success"
    assert result.job_final_finding_count == 2
    assert result.final_finding_count == 1
    assert result.final_findings["fallback_comparison_modes"] == []


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(2),
)
def test_hard_consolidation_failure_preserves_findings_and_marks_partial_failure(
    _mock_plan,
) -> None:
    successful = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_valid_focus_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=_RecordingProvider(
                _valid_consolidation_response
            ),
            max_concurrency=1,
        )
    )
    failed = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_valid_focus_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=_RecordingProvider(
                _invalid_consolidation_response
            ),
            max_concurrency=1,
        )
    )

    assert failed.consolidation_executions[0].status == "failed"
    assert successful.job_final_findings == failed.job_final_findings
    assert successful.run_status == "success"
    assert failed.run_status == "partial_failure"
    assert failed.final_findings["finalization_status"] == (
        "completed_with_fallback"
    )
    assert failed.final_findings["fallback_comparison_modes"] == [
        "focus_comparison"
    ]
    assert failed.final_finding_count == failed.job_final_finding_count


@pytest.mark.parametrize("failure_kind", ["provider", "parse"])
@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(2),
)
def test_consolidation_operational_failure_returns_product_fallback(
    _mock_plan,
    failure_kind: str,
) -> None:
    consolidation_provider = (
        _FailingProvider()
        if failure_kind == "provider"
        else _RecordingProvider(_unparseable_consolidation_response)
    )

    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(_valid_focus_assessment_response),
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        )
    )

    assert result.consolidation_executions[0].status == "failed"
    assert result.run_status == "partial_failure"
    assert result.final_findings["finalization_status"] == (
        "completed_with_fallback"
    )
    assert result.final_findings["fallback_comparison_modes"] == [
        "focus_comparison"
    ]


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(1),
)
def test_deterministic_finalization_failure_propagates_without_fallback(
    _mock_plan,
) -> None:
    with patch(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.execution.finalize_aggregate_evidence_comparison",
        side_effect=AggregateEvidenceComparisonFinalizationError(
            "deterministic finalization failure"
        ),
    ), pytest.raises(
        AggregateEvidenceComparisonFinalizationFailure,
        match="deterministic finalization failure",
    ) as exc_info:
        run_aggregate_evidence_comparison_execution(
            execution_input=_execution_input(
                assessment_provider=_RecordingProvider(
                    _valid_focus_assessment_response
                ),
                verification_provider=_RecordingProvider(
                    _valid_verification_response
                ),
                max_concurrency=1,
            )
        )

    failure = exc_info.value
    assert isinstance(
        failure.pre_final_state,
        AggregateEvidenceComparisonPreFinalState,
    )
    assert failure.pre_final_state.job_final_findings is not None
    assert failure.pre_final_state.consolidation_executions == ()
    assert isinstance(
        failure.finalization_error,
        AggregateEvidenceComparisonFinalizationError,
    )
    assert failure.__cause__ is failure.finalization_error


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(1),
)
def test_second_pass_only_focus_finding_reaches_consolidation_input(
    _mock_plan,
) -> None:
    primary_provider = _RecordingProvider(_empty_assessment_response)
    second_pass_provider = _RecordingProvider(_valid_focus_assessment_response)
    consolidation_provider = _RecordingProvider(_valid_consolidation_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=primary_provider,
            assessment_second_pass_provider=second_pass_provider,
            verification_provider=_RecordingProvider(_valid_verification_response),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        ),
    )

    assert result.verification is None
    assert result.second_pass_assessment is not None
    second_pass_conclusion = result.job_final_findings["jobs"][0]["findings"][0][
        "conclusion"
    ]
    assert len(result.consolidation_executions) == 1
    execution = result.consolidation_executions[0]
    assert execution.provider_called is False
    assert execution.finding_count == 1
    assert consolidation_provider.calls == []
    assert second_pass_conclusion in execution.consolidation_input.user_input_text
    assert "candidate spanning both focus sides" in (
        execution.consolidation_input.user_input_text
    )


_REVISED_CONSOLIDATION_CONCLUSION = (
    "REVISED reconciled conclusion for consolidation input"
)
_ADDITIONAL_CONSOLIDATION_CONCLUSION = (
    "ADDITIONAL accepted conclusion for consolidation input"
)
_ASSESSMENT_PRE_REVISION_CONCLUSION = (
    "ASSESSMENT conclusion before revision must not reach consolidation"
)


def _focus_assessment_with_conclusion(
    messages: list[dict[str, str]],
    conclusion: str,
) -> LLMRawResult:
    aliases = tuple(dict.fromkeys(re.findall(r"\[(T\d{4})\]", messages[-1]["content"])))
    return LLMRawResult(
        provider_name="pipeline-mock",
        model="pipeline-mock",
        raw_text=json.dumps(
            {
                "candidates": [
                    {
                        "candidate_focus": conclusion,
                        "label": "fail",
                        "trigger_sentence_aliases": list(aliases),
                    }
                ]
            }
        ),
    )


def _reconciled_verification_for_consolidation(
    messages: list[dict[str, str]],
) -> LLMRawResult:
    user_content = messages[-1]["content"]
    finding_ids: list[str] = []
    if "## Findings" in user_content:
        marker = "## Findings\n"
        findings_section = user_content.split(marker, 1)[1]
        for line in findings_section.splitlines():
            stripped = line.strip()
            if (
                stripped.startswith("L")
                and len(stripped) == 4
                and stripped[1:].isdigit()
            ):
                finding_ids.append(stripped)
    scope_aliases = tuple(
        dict.fromkeys(
            re.findall(
                r"\[(T\d{4})\]",
                user_content.split("## Findings", 1)[0],
            )
        )
    )
    if not finding_ids or not scope_aliases:
        return _valid_verification_response(messages)
    finding_id = finding_ids[0]
    payload = {
        "finding_verifications": [
            {
                "finding_id": finding_id,
                "verification_result": "revised",
                "conclusion": _REVISED_CONSOLIDATION_CONCLUSION,
                "label": "fail",
                "source_sentence_aliases": [scope_aliases[0]],
            }
        ],
        "additional_findings": [
            {
                "conclusion": _ADDITIONAL_CONSOLIDATION_CONCLUSION,
                "label": "fail",
                "source_sentence_aliases": list(scope_aliases),
            }
        ],
    }
    return LLMRawResult(
        provider_name="pipeline-mock",
        model="pipeline-mock",
        raw_text=json.dumps(payload),
    )


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=lambda **kwargs: _focus_planned_subset(1),
)
def test_reconciled_verification_findings_reach_consolidation_input(
    _mock_plan,
) -> None:
    consolidation_provider = _RecordingProvider(_valid_consolidation_response)
    result = run_aggregate_evidence_comparison_execution(
        execution_input=_execution_input(
            assessment_provider=_RecordingProvider(
                lambda messages: _focus_assessment_with_conclusion(
                    messages,
                    _ASSESSMENT_PRE_REVISION_CONCLUSION,
                )
            ),
            verification_provider=_RecordingProvider(
                _reconciled_verification_for_consolidation
            ),
            consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                "internal_dsur"
            ),
            consolidation_provider=consolidation_provider,
            max_concurrency=1,
        ),
    )

    assert len(consolidation_provider.calls) == 1
    consolidation_input = consolidation_provider.calls[0][-1]["content"]
    assert _REVISED_CONSOLIDATION_CONCLUSION in consolidation_input
    assert _ADDITIONAL_CONSOLIDATION_CONCLUSION in consolidation_input
    assert _ASSESSMENT_PRE_REVISION_CONCLUSION not in consolidation_input
    verified_findings = result.verification.findings_artifact["jobs"][0]["findings"]
    assert verified_findings[0]["conclusion"] == _REVISED_CONSOLIDATION_CONCLUSION
    assert verified_findings[1]["conclusion"] == _ADDITIONAL_CONSOLIDATION_CONCLUSION
