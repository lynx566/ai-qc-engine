"""In-memory execution payloads for aggregate-evidence source preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm.invocation import LLMInvocationRecord
from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationResult,
)


@dataclass(frozen=True)
class AggregateEvidencePrepareExecution:
    assessment_input: dict[str, Any]
    assessment_runtime_context: dict[str, Any]
    assessment_input_preview: dict[str, Any]
    unit_integrity_report: dict[str, Any]
    semantic_result: dict[str, Any]
    aggregate_unit_count: int
    doc_id: str
    zone_key: str


@dataclass(frozen=True)
class AggregateEvidenceAssessmentExecution:
    scope_assessments: dict[str, Any]
    scope_assessment_review: dict[str, Any] | None
    scope_assessments_filename: str
    llm_debug_artifacts: dict[str, Any] | None
    run_status: str
    profile_name: str
    scope_assessment_count: int
    scope_assessment_trace: dict[str, Any] | None
    llm_invocations: tuple[LLMInvocationRecord, ...] = ()


@dataclass(frozen=True)
class AggregateEvidenceEligibilityExecution:
    heading_scope_eligibility: dict[str, Any]
    auto_included_scope_count: int
    excluded_scope_count: int
    review_ambiguous_scope_count: int


@dataclass(frozen=True)
class AggregateEvidenceAssemblyStats:
    input_heading_scope_count: int
    assembled_heading_scope_count: int
    auto_included_count: int
    review_ambiguous_count: int
    excluded_heading_scope_count: int
    excluded_counts_by_status: dict[str, int]


@dataclass(frozen=True)
class AggregateEvidenceAssemblyExecution:
    aggregate_evidence_source_bundle: dict[str, Any]
    stats: AggregateEvidenceAssemblyStats


@dataclass(frozen=True)
class AggregateEvidenceExecution(EvidenceSourcePreparationResult):
    """Unified in-memory result for aggregate prepare → assess → eligibility → assemble."""

    prepare: AggregateEvidencePrepareExecution
    assess: AggregateEvidenceAssessmentExecution
    eligibility: AggregateEvidenceEligibilityExecution
    assemble: AggregateEvidenceAssemblyExecution

    @property
    def aggregate_evidence_source_bundle(self) -> dict[str, Any]:
        return self.assemble.aggregate_evidence_source_bundle
