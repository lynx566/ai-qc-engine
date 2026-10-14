"""Runtime result contracts for Aggregate Evidence operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PrepareResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    assessment_input_path: Path
    unit_integrity_report_path: Path
    run_summary_path: Path
    aggregate_unit_count: int


@dataclass(frozen=True)
class AssessResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    scope_assessments_path: Path
    scope_assessment_review_path: Path | None
    scope_assessment_trace_path: Path | None
    run_summary_path: Path
    scope_assessment_count: int
    run_status: str
    llm_debug_artifacts: dict[str, Any] | None = None


@dataclass(frozen=True)
class EligibilityResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    heading_scope_eligibility_path: Path
    run_summary_path: Path
    source_scope_assessments_path: Path
    auto_included_scope_count: int
    excluded_scope_count: int
    review_ambiguous_scope_count: int
    run_status: str = "success"


@dataclass(frozen=True)
class AssembleResult:
    output_dir: Path
    run_id: str
    doc_id: str
    zone_key: str
    aggregate_evidence_source_bundle_path: Path
    run_summary_path: Path
    input_heading_scope_count: int
    assembled_heading_scope_count: int
    auto_included_count: int
    review_ambiguous_count: int
    excluded_heading_scope_count: int
    run_status: str = "success"
