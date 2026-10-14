"""Scheduler robustness for pipelined aggregate Evidence Comparison execution."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.execution import (
    AggregateEvidenceComparisonSchedulerFatalError,
    _PipelineWorkScheduler,
    run_aggregate_evidence_comparison_execution,
)
from runtime.io import load_json
from tests.test_aggregate_evidence_comparison_pipelining import (
    _PipelineMockProvider,
    _execution_input,
    _planned_subset,
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


def _scheduler_from_planned(
    *,
    job_count: int,
    provider: _PipelineMockProvider,
    max_concurrency: int,
) -> _PipelineWorkScheduler:
    evidence = load_json(_FIXTURE_EVIDENCE)
    planned = _planned_subset(job_count)
    selected_jobs = tuple(enumerate(planned, start=1))
    return _PipelineWorkScheduler(
        selected_jobs=selected_jobs,
        aggregate_comparison_evidence=evidence,
        assessment_provider=provider,
        assessment_second_pass_provider=provider,
        verification_provider=provider,
        max_concurrency=max_concurrency,
    )


def test_scheduler_successful_run_drains_in_flight_and_queues() -> None:
    provider = _PipelineMockProvider()
    scheduler = _scheduler_from_planned(
        job_count=2,
        provider=provider,
        max_concurrency=2,
    )
    scheduler.run()
    assert scheduler.in_flight == 0
    assert scheduler._fatal_error is None
    assert len(scheduler.assessment_executions) == 2


def test_scheduler_unexpected_worker_exception_decrements_in_flight_and_raises() -> None:
    boom = RuntimeError("scheduler worker boom")
    original_execute = _PipelineWorkScheduler._execute_assessment

    def _execute_assessment_raises_on_second(
        self: _PipelineWorkScheduler,
        work,
    ):
        if work.frozen_job_index == 2:
            raise boom
        return original_execute(self, work)

    scheduler = _scheduler_from_planned(
        job_count=2,
        provider=_PipelineMockProvider(),
        max_concurrency=1,
    )

    started = time.perf_counter()
    with patch.object(
        _PipelineWorkScheduler,
        "_execute_assessment",
        _execute_assessment_raises_on_second,
    ):
        with pytest.raises(AggregateEvidenceComparisonSchedulerFatalError) as exc_info:
            scheduler.run()
    assert exc_info.value.__cause__ is boom
    assert scheduler.in_flight == 0
    assert time.perf_counter() - started < 5.0


def test_scheduler_fatal_error_stops_scheduling_new_work() -> None:
    boom = RuntimeError("fatal on job 1")
    assessment_calls: list[int] = []
    original_execute = _PipelineWorkScheduler._execute_assessment

    def _execute_assessment_fail_first(
        self: _PipelineWorkScheduler,
        work,
    ):
        assessment_calls.append(work.frozen_job_index)
        if work.frozen_job_index == 1:
            raise boom
        return original_execute(self, work)

    scheduler = _scheduler_from_planned(
        job_count=4,
        provider=_PipelineMockProvider(),
        max_concurrency=1,
    )

    with patch.object(
        _PipelineWorkScheduler,
        "_execute_assessment",
        _execute_assessment_fail_first,
    ):
        with pytest.raises(AggregateEvidenceComparisonSchedulerFatalError):
            scheduler.run()

    assert assessment_calls == [1]
    assert scheduler.in_flight == 0


def test_run_aggregate_evidence_comparison_execution_propagates_scheduler_fatal_error() -> (
    None
):
    execution_input = _execution_input(
        assessment_provider=_PipelineMockProvider(),
        verification_provider=_PipelineMockProvider(),
        max_concurrency=2,
    )

    with patch(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.execution._build_findings_job_envelope",
        side_effect=RuntimeError("unexpected envelope failure"),
    ):
        with pytest.raises(AggregateEvidenceComparisonSchedulerFatalError):
            run_aggregate_evidence_comparison_execution(
                execution_input=execution_input,
            )
