"""In-memory orchestration for clinical-safety aggregate Evidence Comparison."""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    build_findings,
)

from .comparison_evidence import materialize_aggregate_comparison_evidence
from .comparison_finding_assessment.execution import (
    ComparisonFindingAssessmentExecution,
    ComparisonFindingAssessmentJobExecution,
    execute_comparison_finding_assessment_job,
)
from .comparison_finding_assessment.finding_assembly import (
    JobFindingsBundle,
    assemble_findings_for_job,
    assemble_findings_for_jobs,
    build_findings_artifact_from_bundles,
    job_findings_bundle_to_artifact_row,
)
from .comparison_finding_assessment.jobs import ComparisonFindingAssessmentJob
from .comparison_finding_assessment.planner import (
    plan_comparison_finding_assessment_jobs,
)
from .comparison_finding_consolidation.execution import (
    ComparisonFindingConsolidationExecution,
    execute_comparison_finding_consolidation,
)
from .comparison_finding_consolidation.input_materialization import (
    materialize_comparison_finding_consolidation_input,
)
from .comparison_finding_verification.execution import (
    ComparisonFindingVerificationExecution,
    ComparisonFindingVerificationJobExecution,
    execute_comparison_finding_verification_job,
)
from .comparison_finding_verification.finding_reconciliation import (
    assemble_verified_findings_artifact,
)
from .comparison_finding_verification.input_materialization import (
    materialize_comparison_finding_verification_input,
)
from .execution_types import (
    AggregateEvidenceComparisonExecution,
    AggregateEvidenceComparisonExecutionInput,
    AggregateEvidenceComparisonPreFinalState,
)
from .finalization import (
    AggregateEvidenceComparisonFinalizationError,
    finalize_aggregate_evidence_comparison,
)
from .job_final_selection import select_job_final_rows_for_mode

logger = logging.getLogger(__name__)


class AggregateEvidenceComparisonSchedulerFatalError(RuntimeError):
    """Abort aggregate comparison after an unexpected scheduler worker failure."""


class AggregateEvidenceComparisonFinalizationFailure(RuntimeError):
    """Fatal execution failure retaining settled state from before finalization."""

    def __init__(
        self,
        *,
        pre_final_state: AggregateEvidenceComparisonPreFinalState,
        finalization_error: AggregateEvidenceComparisonFinalizationError,
    ) -> None:
        if not isinstance(
            pre_final_state,
            AggregateEvidenceComparisonPreFinalState,
        ):
            raise TypeError(
                "pre_final_state must be an "
                "AggregateEvidenceComparisonPreFinalState"
            )
        if not isinstance(
            finalization_error,
            AggregateEvidenceComparisonFinalizationError,
        ):
            raise TypeError(
                "finalization_error must be an "
                "AggregateEvidenceComparisonFinalizationError"
            )
        self.pre_final_state = pre_final_state
        self.finalization_error = finalization_error
        super().__init__(str(finalization_error))


def _log_pipeline_phase_started(
    *,
    phase: str,
    frozen_job_index: int,
    comparison_mode_id: str,
) -> None:
    logger.info(
        "aggregate evidence comparison %s started "
        "frozen_job_index=%s comparison_mode_id=%s",
        phase,
        frozen_job_index,
        comparison_mode_id,
    )


def _log_pipeline_phase_finished(
    *,
    phase: str,
    frozen_job_index: int,
    comparison_mode_id: str,
    status: str,
) -> None:
    logger.info(
        "aggregate evidence comparison %s finished "
        "frozen_job_index=%s comparison_mode_id=%s status=%s",
        phase,
        frozen_job_index,
        comparison_mode_id,
        status,
    )


def _log_pipeline_phase_failed(
    *,
    phase: str,
    frozen_job_index: int,
    comparison_mode_id: str,
) -> None:
    logger.exception(
        "aggregate evidence comparison %s failed "
        "frozen_job_index=%s comparison_mode_id=%s",
        phase,
        frozen_job_index,
        comparison_mode_id,
    )


def resolve_aggregate_evidence_comparison_run_status(
    *,
    finalized_success_count: int,
    total_job_count: int,
) -> str:
    """Resolve overall Comparison run status from phase outcomes."""

    if finalized_success_count == 0:
        return "failed"
    if finalized_success_count == total_job_count:
        return "success"
    return "partial_failure"


def _resolve_batch_run_status(*, success_count: int, total_count: int) -> str:
    if success_count == total_count:
        return "success"
    if success_count == 0:
        return "failed"
    return "partial_failure"


def _assessment_route_settled(
    *,
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
    second_pass_assessment_executions: Mapping[
        int, ComparisonFindingAssessmentJobExecution
    ],
    frozen_job_index: int,
) -> bool:
    primary = assessment_executions.get(frozen_job_index)
    if primary is None:
        return False
    if primary.status != "success" or primary.finding_count > 0:
        return True
    return frozen_job_index in second_pass_assessment_executions


def _routed_assessment_execution(
    *,
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
    second_pass_assessment_executions: Mapping[
        int, ComparisonFindingAssessmentJobExecution
    ],
    frozen_job_index: int,
) -> ComparisonFindingAssessmentJobExecution | None:
    primary = assessment_executions.get(frozen_job_index)
    if primary is None:
        return None
    if primary.status == "success" and primary.finding_count == 0:
        return second_pass_assessment_executions.get(frozen_job_index)
    return primary


def _prefix_settled(
    *,
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
    second_pass_assessment_executions: Mapping[
        int, ComparisonFindingAssessmentJobExecution
    ],
    frozen_job_index: int,
) -> bool:
    return all(
        _assessment_route_settled(
            assessment_executions=assessment_executions,
            second_pass_assessment_executions=second_pass_assessment_executions,
            frozen_job_index=index,
        )
        for index in range(1, frozen_job_index)
    )


def _starting_finding_sequence(
    *,
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
    second_pass_assessment_executions: Mapping[
        int, ComparisonFindingAssessmentJobExecution
    ],
    frozen_job_index: int,
) -> int:
    sequence = 1
    for index in range(1, frozen_job_index):
        execution = _routed_assessment_execution(
            assessment_executions=assessment_executions,
            second_pass_assessment_executions=second_pass_assessment_executions,
            frozen_job_index=index,
        )
        if execution is None or execution.status != "success":
            continue
        sequence += execution.finding_count
    return sequence


def _verification_execution_index(
    *,
    selected_jobs: Sequence[tuple[int, ComparisonFindingAssessmentJob]],
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
    frozen_job_index: int,
) -> int:
    return (
        sum(
            1
            for index, _job in selected_jobs
            if index < frozen_job_index
            and assessment_executions.get(index) is not None
            and assessment_executions[index].status == "success"
        )
        + 1
    )


def _build_findings_job_envelope(
    *,
    frozen_job_index: int,
    job: ComparisonFindingAssessmentJob,
    assessment_execution: ComparisonFindingAssessmentJobExecution,
    starting_finding_sequence: int,
) -> dict[str, Any]:
    if assessment_execution.accepted_response is None:
        raise ValueError(
            "successful assessment execution must include accepted_response"
        )
    findings = assemble_findings_for_job(
        assessment_execution.accepted_response,
        job=job,
        starting_finding_sequence=starting_finding_sequence,
    )
    bundle = JobFindingsBundle(
        frozen_job_index=frozen_job_index,
        job=job,
        findings=findings,
    )
    return job_findings_bundle_to_artifact_row(bundle)


def _build_assessment_execution(
    *,
    selected_jobs: Sequence[tuple[int, ComparisonFindingAssessmentJob]],
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
) -> ComparisonFindingAssessmentExecution:
    job_executions = tuple(
        assessment_executions[frozen_job_index]
        for frozen_job_index, _job in selected_jobs
    )
    assembly_inputs = [
        (
            frozen_job_index,
            job,
            assessment_executions[frozen_job_index].accepted_response,
        )
        for frozen_job_index, job in selected_jobs
        if assessment_executions[frozen_job_index].status == "success"
        and assessment_executions[frozen_job_index].accepted_response is not None
    ]
    findings_artifact: dict[str, Any] | None = None
    finding_count = 0
    if assembly_inputs:
        bundles = assemble_findings_for_jobs(assembly_inputs)
        findings_artifact = build_findings_artifact_from_bundles(bundles)
        finding_count = sum(len(bundle.findings) for bundle in bundles)

    success_count = sum(1 for execution in job_executions if execution.status == "success")
    return ComparisonFindingAssessmentExecution(
        job_executions=job_executions,
        run_status=_resolve_batch_run_status(
            success_count=success_count,
            total_count=len(job_executions),
        ),
        success_count=success_count,
        failed_count=len(job_executions) - success_count,
        findings_artifact=findings_artifact,
        finding_count=finding_count,
    )


def _build_verification_execution(
    *,
    selected_jobs: Sequence[tuple[int, ComparisonFindingAssessmentJob]],
    assessment_executions: Mapping[int, ComparisonFindingAssessmentJobExecution],
    verification_executions: Mapping[int, ComparisonFindingVerificationJobExecution],
    assessment_findings_artifact: Mapping[str, Any],
) -> ComparisonFindingVerificationExecution:
    verification_job_indexes = [
        frozen_job_index
        for frozen_job_index, _job in selected_jobs
        if frozen_job_index in verification_executions
    ]
    job_executions = tuple(
        verification_executions[frozen_job_index]
        for frozen_job_index in verification_job_indexes
    )

    reconciliation_pairs = [
        (execution.job_reconciliation, execution.additional_eligibility)
        for execution in job_executions
        if execution.status == "success"
        and execution.job_reconciliation is not None
        and execution.additional_eligibility is not None
    ]

    findings_artifact: dict[str, Any] | None = None
    adopted_finding_count = 0
    if reconciliation_pairs:
        assembly = assemble_verified_findings_artifact(
            assessment_findings_artifact=assessment_findings_artifact,
            job_reconciliations=reconciliation_pairs,
        )
        findings_artifact = assembly.findings_artifact
        adopted_finding_count = assembly.adopted_finding_count
        adopted_count_by_index = {
            job_result.frozen_job_index: len(job_result.findings)
            for job_result in assembly.job_results
        }
        job_executions = tuple(
            ComparisonFindingVerificationJobExecution(
                frozen_job_index=execution.frozen_job_index,
                execution_index=execution.execution_index,
                comparison_mode_id=execution.comparison_mode_id,
                status=execution.status,
                prompt_id=execution.prompt_id,
                prompt_version=execution.prompt_version,
                parse_status=execution.parse_status,
                validation_status=execution.validation_status,
                verification_input=execution.verification_input,
                validated_response=execution.validated_response,
                job_reconciliation=execution.job_reconciliation,
                additional_eligibility=execution.additional_eligibility,
                input_finding_count=execution.input_finding_count,
                finding_verification_count=execution.finding_verification_count,
                additional_finding_count=execution.additional_finding_count,
                confirmed_finding_count=execution.confirmed_finding_count,
                revised_finding_count=execution.revised_finding_count,
                rejected_finding_count=execution.rejected_finding_count,
                received_additional_finding_count=(
                    execution.received_additional_finding_count
                ),
                accepted_additional_finding_count=(
                    execution.accepted_additional_finding_count
                ),
                dropped_additional_finding_count=(
                    execution.dropped_additional_finding_count
                ),
                adopted_finding_count=adopted_count_by_index.get(
                    execution.frozen_job_index,
                    0,
                ),
                error_message=execution.error_message,
                messages=execution.messages,
                raw_response_text=execution.raw_response_text,
                llm_invocations=execution.llm_invocations,
            )
            for execution in job_executions
        )

    success_count = sum(1 for execution in job_executions if execution.status == "success")
    return ComparisonFindingVerificationExecution(
        job_executions=job_executions,
        run_status=_resolve_batch_run_status(
            success_count=success_count,
            total_count=len(job_executions),
        ),
        success_count=success_count,
        failed_count=len(job_executions) - success_count,
        findings_artifact=findings_artifact,
        adopted_finding_count=adopted_finding_count,
    )


@dataclass(frozen=True, slots=True)
class _AssessmentWork:
    frozen_job_index: int
    execution_index: int
    job: ComparisonFindingAssessmentJob


@dataclass(frozen=True, slots=True)
class _VerificationWork:
    frozen_job_index: int
    job: ComparisonFindingAssessmentJob
    assessment_execution: ComparisonFindingAssessmentJobExecution


@dataclass(frozen=True, slots=True)
class _SecondPassAssessmentWork:
    frozen_job_index: int
    execution_index: int
    job: ComparisonFindingAssessmentJob


@dataclass
class _PipelineWorkScheduler:
    """Explicit A/V work queues with verification-first slot dispatch."""

    selected_jobs: tuple[tuple[int, ComparisonFindingAssessmentJob], ...]
    aggregate_comparison_evidence: Mapping[str, Any]
    assessment_provider: Any
    assessment_second_pass_provider: Any
    verification_provider: Any
    max_concurrency: int
    assessment_llm_execution_config: Mapping[str, Any] | None = None
    assessment_second_pass_llm_execution_config: Mapping[str, Any] | None = None
    verification_llm_execution_config: Mapping[str, Any] | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    condition: threading.Condition = field(init=False)
    assessment_executions: dict[int, ComparisonFindingAssessmentJobExecution] = field(
        default_factory=dict,
    )
    second_pass_assessment_executions: dict[
        int, ComparisonFindingAssessmentJobExecution
    ] = field(default_factory=dict)
    verification_executions: dict[int, ComparisonFindingVerificationJobExecution] = (
        field(default_factory=dict)
    )
    pending_assessments: deque[_AssessmentWork] = field(init=False)
    ready_verifications: deque[_VerificationWork] = field(
        default_factory=deque,
    )
    ready_second_pass_assessments: deque[_SecondPassAssessmentWork] = field(
        default_factory=deque,
    )
    second_pass_handled: set[int] = field(default_factory=set)
    verification_handled: set[int] = field(default_factory=set)
    in_flight: int = 0
    _fatal_error: BaseException | None = field(default=None, init=False, repr=False)
    _executor: ThreadPoolExecutor | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.condition = threading.Condition(self.lock)
        self.pending_assessments = deque(
            _AssessmentWork(
                frozen_job_index=frozen_job_index,
                execution_index=execution_index,
                job=job,
            )
            for execution_index, (frozen_job_index, job) in enumerate(
                self.selected_jobs,
                start=1,
            )
        )

    def run(self) -> None:
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            self._executor = executor
            self._try_schedule()
            with self.condition:
                while not self._should_exit_run_wait():
                    self.condition.wait()
            self._executor = None
        if self._fatal_error is not None:
            raise AggregateEvidenceComparisonSchedulerFatalError(
                "aggregate evidence comparison scheduler aborted after "
                "unexpected worker failure"
            ) from self._fatal_error

    def _is_finished(self) -> bool:
        return (
            self.in_flight == 0
            and not self.pending_assessments
            and not self.ready_second_pass_assessments
            and not self.ready_verifications
        )

    def _should_exit_run_wait(self) -> bool:
        if self._fatal_error is not None:
            return self.in_flight == 0
        return self._is_finished()

    def _try_schedule(self) -> None:
        with self.lock:
            if self._fatal_error is not None:
                return
            executor = self._executor
            if executor is None:
                return
            while self.in_flight < self.max_concurrency:
                if self._fatal_error is not None:
                    break
                work = self._dequeue_work()
                if work is None:
                    break
                self.in_flight += 1
                if isinstance(work, _AssessmentWork):
                    future = executor.submit(self._execute_assessment, work)
                elif isinstance(work, _SecondPassAssessmentWork):
                    future = executor.submit(self._execute_second_pass_assessment, work)
                else:
                    future = executor.submit(self._execute_verification, work)
                future.add_done_callback(self._on_work_done)

    def _dequeue_work(
        self,
    ) -> _AssessmentWork | _SecondPassAssessmentWork | _VerificationWork | None:
        if self.ready_verifications:
            return self.ready_verifications.popleft()
        if self.ready_second_pass_assessments:
            return self.ready_second_pass_assessments.popleft()
        if self.pending_assessments:
            return self.pending_assessments.popleft()
        return None

    def _on_work_done(self, future: Future[Any]) -> None:
        worker_error: BaseException | None = None
        try:
            future.result()
        except Exception as exc:
            worker_error = exc
        with self.lock:
            self.in_flight -= 1
            if worker_error is not None and self._fatal_error is None:
                self._fatal_error = worker_error
            self.condition.notify_all()
        self._try_schedule()

    def _enqueue_ready_branch_work(self) -> None:
        for frozen_job_index, job in self.selected_jobs:
            primary = self.assessment_executions.get(frozen_job_index)
            if primary is None:
                continue
            if (
                primary.status == "success"
                and primary.finding_count == 0
                and frozen_job_index not in self.second_pass_handled
            ):
                self.second_pass_handled.add(frozen_job_index)
                self.ready_second_pass_assessments.append(
                    _SecondPassAssessmentWork(
                        frozen_job_index=frozen_job_index,
                        execution_index=frozen_job_index,
                        job=job,
                    )
                )

            if frozen_job_index in self.verification_handled:
                continue
            if not _assessment_route_settled(
                assessment_executions=self.assessment_executions,
                second_pass_assessment_executions=(
                    self.second_pass_assessment_executions
                ),
                frozen_job_index=frozen_job_index,
            ):
                continue
            if not _prefix_settled(
                assessment_executions=self.assessment_executions,
                second_pass_assessment_executions=(
                    self.second_pass_assessment_executions
                ),
                frozen_job_index=frozen_job_index,
            ):
                continue
            self.verification_handled.add(frozen_job_index)
            assessment_execution = _routed_assessment_execution(
                assessment_executions=self.assessment_executions,
                second_pass_assessment_executions=(
                    self.second_pass_assessment_executions
                ),
                frozen_job_index=frozen_job_index,
            )
            if (
                assessment_execution is None
                or assessment_execution.status != "success"
                or primary.finding_count == 0
            ):
                continue
            self.ready_verifications.append(
                _VerificationWork(
                    frozen_job_index=frozen_job_index,
                    job=job,
                    assessment_execution=assessment_execution,
                )
            )

    def _execute_assessment(
        self,
        work: _AssessmentWork,
    ) -> ComparisonFindingAssessmentJobExecution:
        phase = "assessment"
        comparison_mode_id = work.job.comparison_mode_id
        _log_pipeline_phase_started(
            phase=phase,
            frozen_job_index=work.frozen_job_index,
            comparison_mode_id=comparison_mode_id,
        )
        try:
            execution = execute_comparison_finding_assessment_job(
                frozen_job_index=work.frozen_job_index,
                execution_index=work.execution_index,
                job=work.job,
                aggregate_comparison_evidence=self.aggregate_comparison_evidence,
                provider=self.assessment_provider,
                llm_execution_config=self.assessment_llm_execution_config,
            )
        except Exception:
            _log_pipeline_phase_failed(
                phase=phase,
                frozen_job_index=work.frozen_job_index,
                comparison_mode_id=comparison_mode_id,
            )
            raise
        _log_pipeline_phase_finished(
            phase=phase,
            frozen_job_index=work.frozen_job_index,
            comparison_mode_id=comparison_mode_id,
            status=execution.status,
        )
        with self.lock:
            self.assessment_executions[work.frozen_job_index] = execution
            self._enqueue_ready_branch_work()
        return execution

    def _execute_second_pass_assessment(
        self,
        work: _SecondPassAssessmentWork,
    ) -> ComparisonFindingAssessmentJobExecution:
        phase = "assessment_second_pass"
        comparison_mode_id = work.job.comparison_mode_id
        _log_pipeline_phase_started(
            phase=phase,
            frozen_job_index=work.frozen_job_index,
            comparison_mode_id=comparison_mode_id,
        )
        try:
            execution = execute_comparison_finding_assessment_job(
                frozen_job_index=work.frozen_job_index,
                execution_index=work.execution_index,
                job=work.job,
                aggregate_comparison_evidence=self.aggregate_comparison_evidence,
                provider=self.assessment_second_pass_provider,
                llm_execution_config=(
                    self.assessment_second_pass_llm_execution_config
                ),
            )
        except Exception:
            _log_pipeline_phase_failed(
                phase=phase,
                frozen_job_index=work.frozen_job_index,
                comparison_mode_id=comparison_mode_id,
            )
            raise
        _log_pipeline_phase_finished(
            phase=phase,
            frozen_job_index=work.frozen_job_index,
            comparison_mode_id=comparison_mode_id,
            status=execution.status,
        )
        with self.lock:
            self.second_pass_assessment_executions[work.frozen_job_index] = execution
            self._enqueue_ready_branch_work()
        return execution

    def _execute_verification(
        self,
        work: _VerificationWork,
    ) -> ComparisonFindingVerificationJobExecution:
        phase = "verification"
        comparison_mode_id = work.job.comparison_mode_id
        _log_pipeline_phase_started(
            phase=phase,
            frozen_job_index=work.frozen_job_index,
            comparison_mode_id=comparison_mode_id,
        )
        try:
            starting_sequence = _starting_finding_sequence(
                assessment_executions=self.assessment_executions,
                second_pass_assessment_executions=(
                    self.second_pass_assessment_executions
                ),
                frozen_job_index=work.frozen_job_index,
            )
            execution_index = _verification_execution_index(
                selected_jobs=self.selected_jobs,
                assessment_executions=self.assessment_executions,
                frozen_job_index=work.frozen_job_index,
            )
            findings_job_envelope = _build_findings_job_envelope(
                frozen_job_index=work.frozen_job_index,
                job=work.job,
                assessment_execution=work.assessment_execution,
                starting_finding_sequence=starting_sequence,
            )
            verification_input = materialize_comparison_finding_verification_input(
                job=work.job,
                aggregate_comparison_evidence=self.aggregate_comparison_evidence,
                findings_job_envelope=findings_job_envelope,
                frozen_job_index=work.frozen_job_index,
            )
            execution = execute_comparison_finding_verification_job(
                verification_input=verification_input,
                frozen_job=work.job,
                aggregate_comparison_evidence=self.aggregate_comparison_evidence,
                execution_index=execution_index,
                provider=self.verification_provider,
                llm_execution_config=self.verification_llm_execution_config,
            )
        except Exception:
            _log_pipeline_phase_failed(
                phase=phase,
                frozen_job_index=work.frozen_job_index,
                comparison_mode_id=comparison_mode_id,
            )
            raise
        _log_pipeline_phase_finished(
            phase=phase,
            frozen_job_index=work.frozen_job_index,
            comparison_mode_id=comparison_mode_id,
            status=execution.status,
        )
        with self.lock:
            self.verification_executions[work.frozen_job_index] = execution
        return execution


def _run_pipelined_aggregate_evidence_comparison_execution(
    *,
    selected_jobs: Sequence[tuple[int, ComparisonFindingAssessmentJob]],
    aggregate_comparison_evidence: Mapping[str, Any],
    execution_input: AggregateEvidenceComparisonExecutionInput,
) -> tuple[
    ComparisonFindingAssessmentExecution,
    ComparisonFindingAssessmentExecution | None,
    ComparisonFindingVerificationExecution | None,
    dict[str, Any] | None,
    tuple[ComparisonFindingConsolidationExecution, ...],
]:
    if not selected_jobs:
        raise ValueError("selected_jobs must contain at least one job")

    effective_concurrency = (
        len(selected_jobs)
        if execution_input.max_concurrency is None
        else min(execution_input.max_concurrency, len(selected_jobs))
    )
    scheduler = _PipelineWorkScheduler(
        selected_jobs=tuple(selected_jobs),
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        assessment_provider=execution_input.assessment_provider,
        assessment_second_pass_provider=(
            execution_input.assessment_second_pass_provider
        ),
        verification_provider=execution_input.verification_provider,
        assessment_llm_execution_config=(
            execution_input.assessment_llm_execution_config
        ),
        assessment_second_pass_llm_execution_config=(
            execution_input.assessment_second_pass_llm_execution_config
        ),
        verification_llm_execution_config=(
            execution_input.verification_llm_execution_config
        ),
        max_concurrency=effective_concurrency,
    )
    scheduler.run()

    assessment = _build_assessment_execution(
        selected_jobs=selected_jobs,
        assessment_executions=scheduler.assessment_executions,
    )

    second_pass_selected_jobs = tuple(
        (frozen_job_index, job)
        for frozen_job_index, job in selected_jobs
        if frozen_job_index in scheduler.second_pass_assessment_executions
    )
    second_pass_assessment: ComparisonFindingAssessmentExecution | None = None
    if second_pass_selected_jobs:
        second_pass_assessment = _build_assessment_execution(
            selected_jobs=second_pass_selected_jobs,
            assessment_executions=scheduler.second_pass_assessment_executions,
        )

    routed_assessment_executions = {
        frozen_job_index: routed
        for frozen_job_index, _job in selected_jobs
        if (
            routed := _routed_assessment_execution(
                assessment_executions=scheduler.assessment_executions,
                second_pass_assessment_executions=(
                    scheduler.second_pass_assessment_executions
                ),
                frozen_job_index=frozen_job_index,
            )
        )
        is not None
    }
    routed_assessment = _build_assessment_execution(
        selected_jobs=selected_jobs,
        assessment_executions=routed_assessment_executions,
    )
    verification: ComparisonFindingVerificationExecution | None = None
    job_final_findings: dict[str, Any] | None = None
    job_final_rows: list[dict[str, Any]] = []
    if scheduler.verification_executions and routed_assessment.findings_artifact is not None:
        verification = _build_verification_execution(
            selected_jobs=selected_jobs,
            assessment_executions=routed_assessment_executions,
            verification_executions=scheduler.verification_executions,
            assessment_findings_artifact=routed_assessment.findings_artifact,
        )
    if routed_assessment.findings_artifact is not None:
        verification_jobs_by_index = {
            job["frozen_job_index"]: job
            for job in (verification.findings_artifact or {}).get("jobs", ())
        } if verification is not None else {}
        for job_row in routed_assessment.findings_artifact.get("jobs", ()):
            frozen_job_index = job_row["frozen_job_index"]
            routed_execution = routed_assessment_executions[frozen_job_index]
            if routed_execution.status != "success":
                continue
            if frozen_job_index in scheduler.second_pass_assessment_executions:
                job_final_rows.append(job_row)
                continue
            verified_job = verification_jobs_by_index.get(frozen_job_index)
            if verified_job is not None:
                job_final_rows.append(verified_job)
    consolidation_executions: list[ComparisonFindingConsolidationExecution] = []
    if execution_input.consolidation_config.enabled_comparison_modes:
        if execution_input.consolidation_provider is None:
            raise ValueError(
                "consolidation_provider is required when consolidation is enabled"
            )
        for comparison_mode_id in (
            execution_input.consolidation_config.enabled_comparison_modes
        ):
            selected_job_final_rows = select_job_final_rows_for_mode(
                job_final_rows=job_final_rows,
                comparison_mode_id=comparison_mode_id,
            )
            consolidation_input = (
                materialize_comparison_finding_consolidation_input(
                    comparison_mode_id=comparison_mode_id,
                    aggregate_comparison_evidence=aggregate_comparison_evidence,
                    selected_job_final_rows=selected_job_final_rows,
                )
            )
            consolidation_executions.append(
                execute_comparison_finding_consolidation(
                    consolidation_input=consolidation_input,
                    provider=execution_input.consolidation_provider,
                    llm_execution_config=(
                        execution_input.consolidation_llm_execution_config
                    ),
                )
            )

    if job_final_rows:
        job_final_findings = build_findings(jobs=job_final_rows)

    return (
        assessment,
        second_pass_assessment,
        verification,
        job_final_findings,
        tuple(consolidation_executions),
    )


def run_aggregate_evidence_comparison_execution(
    *,
    execution_input: AggregateEvidenceComparisonExecutionInput,
) -> AggregateEvidenceComparisonExecution:
    """Run materialize → plan → assess → verify using plugin execution cores."""

    if not isinstance(execution_input, AggregateEvidenceComparisonExecutionInput):
        raise TypeError(
            "execution_input must be an AggregateEvidenceComparisonExecutionInput; "
            f"got {type(execution_input)!r}"
        )

    aggregate_comparison_evidence = materialize_aggregate_comparison_evidence(
        invocation=execution_input.invocation,
    )
    planned_jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        config=execution_input.assessment_config,
    )
    selected_jobs = tuple(enumerate(planned_jobs, start=1))

    (
        assessment,
        second_pass_assessment,
        verification,
        job_final_findings,
        consolidation_executions,
    ) = (
        _run_pipelined_aggregate_evidence_comparison_execution(
            selected_jobs=selected_jobs,
            aggregate_comparison_evidence=aggregate_comparison_evidence,
            execution_input=execution_input,
        )
    )
    pre_final_state = AggregateEvidenceComparisonPreFinalState(
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        planned_jobs=planned_jobs,
        assessment=assessment,
        second_pass_assessment=second_pass_assessment,
        verification=verification,
        job_final_findings=job_final_findings,
        consolidation_executions=consolidation_executions,
    )
    try:
        final_findings = finalize_aggregate_evidence_comparison(
            job_final_rows=tuple((job_final_findings or {}).get("jobs", ())),
            consolidation_executions=consolidation_executions,
            consolidation_config=execution_input.consolidation_config,
        )
    except AggregateEvidenceComparisonFinalizationError as exc:
        raise AggregateEvidenceComparisonFinalizationFailure(
            pre_final_state=pre_final_state,
            finalization_error=exc,
        ) from exc

    finalized_success_count = (
        (verification.success_count if verification is not None else 0)
        + (
            second_pass_assessment.success_count
            if second_pass_assessment is not None
            else 0
        )
    )
    run_status = resolve_aggregate_evidence_comparison_run_status(
        finalized_success_count=finalized_success_count,
        total_job_count=len(selected_jobs),
    )
    if run_status == "success" and any(
        execution.status != "success" for execution in consolidation_executions
    ):
        run_status = "partial_failure"
    return AggregateEvidenceComparisonExecution(
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        planned_jobs=planned_jobs,
        assessment=assessment,
        second_pass_assessment=second_pass_assessment,
        verification=verification,
        consolidation_executions=consolidation_executions,
        job_final_findings=job_final_findings,
        final_findings=final_findings,
        run_status=run_status,
    )


__all__ = [
    "AggregateEvidenceComparisonFinalizationFailure",
    "AggregateEvidenceComparisonSchedulerFatalError",
    "resolve_aggregate_evidence_comparison_run_status",
    "run_aggregate_evidence_comparison_execution",
]
