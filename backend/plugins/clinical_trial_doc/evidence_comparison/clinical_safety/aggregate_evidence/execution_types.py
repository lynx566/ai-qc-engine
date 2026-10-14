"""In-memory execution payloads for clinical-safety aggregate Evidence Comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm.providers.base import LLMProvider
from operations.evidence_comparison.contracts import (
    EvidenceComparisonInvocation,
    EvidenceComparisonResult,
)

from .comparison_finding_assessment.config import (
    ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
)
from .comparison_finding_assessment.execution import (
    ComparisonFindingAssessmentExecution,
)
from .comparison_finding_assessment.jobs import ComparisonFindingAssessmentJob
from .comparison_finding_consolidation.config import (
    ResolvedComparisonFindingConsolidationConfig,
)
from .comparison_finding_consolidation.execution import (
    ComparisonFindingConsolidationExecution,
)
from .comparison_finding_verification.execution import (
    ComparisonFindingVerificationExecution,
)
from .input_types import AggregateEvidenceComparisonInvocation


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonExecutionInput(EvidenceComparisonInvocation):
    """Structured input for one clinical-safety aggregate Comparison execution."""

    invocation: AggregateEvidenceComparisonInvocation
    assessment_config: ResolvedClinicalSafetyComparisonFindingAssessmentConfig
    assessment_provider: LLMProvider
    assessment_second_pass_provider: LLMProvider
    verification_provider: LLMProvider
    consolidation_config: ResolvedComparisonFindingConsolidationConfig = field(
        default_factory=lambda: ResolvedComparisonFindingConsolidationConfig(
            enabled_comparison_modes=()
        )
    )
    consolidation_provider: LLMProvider | None = None
    max_concurrency: int | None = None
    assessment_llm_execution_config: dict[str, Any] | None = None
    assessment_second_pass_llm_execution_config: dict[str, Any] | None = None
    verification_llm_execution_config: dict[str, Any] | None = None
    consolidation_llm_execution_config: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonPreFinalState:
    """Settled aggregate execution state immediately before finalization."""

    aggregate_comparison_evidence: dict[str, Any]
    planned_jobs: tuple[ComparisonFindingAssessmentJob, ...]
    assessment: ComparisonFindingAssessmentExecution
    second_pass_assessment: ComparisonFindingAssessmentExecution | None
    verification: ComparisonFindingVerificationExecution | None
    job_final_findings: dict[str, Any] | None
    consolidation_executions: tuple[
        ComparisonFindingConsolidationExecution, ...
    ] = ()

    @property
    def planned_job_count(self) -> int:
        return len(self.planned_jobs)

    @property
    def assessment_success_count(self) -> int:
        return self.assessment.success_count

    @property
    def assessment_failed_count(self) -> int:
        return self.assessment.failed_count

    @property
    def verification_success_count(self) -> int:
        if self.verification is None:
            return 0
        return self.verification.success_count

    @property
    def verification_failed_count(self) -> int:
        if self.verification is None:
            return 0
        return self.verification.failed_count

    @property
    def second_pass_assessment_success_count(self) -> int:
        if self.second_pass_assessment is None:
            return 0
        return self.second_pass_assessment.success_count

    @property
    def second_pass_assessment_failed_count(self) -> int:
        if self.second_pass_assessment is None:
            return 0
        return self.second_pass_assessment.failed_count

    @property
    def job_final_finding_count(self) -> int:
        if self.job_final_findings is None:
            return 0
        return sum(
            len(job.get("findings", ()))
            for job in self.job_final_findings.get("jobs", ())
        )


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonExecution(EvidenceComparisonResult):
    """Structured result for one clinical-safety aggregate Comparison execution."""

    aggregate_comparison_evidence: dict[str, Any]
    planned_jobs: tuple[ComparisonFindingAssessmentJob, ...]
    assessment: ComparisonFindingAssessmentExecution
    second_pass_assessment: ComparisonFindingAssessmentExecution | None
    verification: ComparisonFindingVerificationExecution | None
    job_final_findings: dict[str, Any] | None
    final_findings: dict[str, Any]
    run_status: str
    consolidation_executions: tuple[
        ComparisonFindingConsolidationExecution, ...
    ] = ()

    @property
    def planned_job_count(self) -> int:
        return len(self.planned_jobs)

    @property
    def assessment_success_count(self) -> int:
        return self.assessment.success_count

    @property
    def assessment_failed_count(self) -> int:
        return self.assessment.failed_count

    @property
    def verification_success_count(self) -> int:
        if self.verification is None:
            return 0
        return self.verification.success_count

    @property
    def verification_failed_count(self) -> int:
        if self.verification is None:
            return 0
        return self.verification.failed_count

    @property
    def second_pass_assessment_success_count(self) -> int:
        if self.second_pass_assessment is None:
            return 0
        return self.second_pass_assessment.success_count

    @property
    def second_pass_assessment_failed_count(self) -> int:
        if self.second_pass_assessment is None:
            return 0
        return self.second_pass_assessment.failed_count

    @property
    def job_final_finding_count(self) -> int:
        if self.job_final_findings is None:
            return 0
        return sum(
            len(job.get("findings", ()))
            for job in self.job_final_findings.get("jobs", ())
        )

    @property
    def final_finding_count(self) -> int:
        return len(self.final_findings.get("findings", ()))


__all__ = [
    "AggregateEvidenceComparisonExecution",
    "AggregateEvidenceComparisonExecutionInput",
    "AggregateEvidenceComparisonPreFinalState",
]
