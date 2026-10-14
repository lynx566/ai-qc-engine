"""Scoped handoff validation report for aggregate_prepare assessment_input artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    collect_scoped_assessment_handoff_issues,
    iter_compact_assessment_units,
)
from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE

UNIT_INTEGRITY_REPORT_FILENAME = "unit_integrity_report.json"

_EMPTY_HANDOFF_SUMMARY: dict[str, int] = {
    "expected_aggregate_unit_count": 0,
    "assessment_input_unit_count": 0,
    "missing_aggregate_unit_count": 0,
    "extra_assessment_unit_count": 0,
    "aggregate_route_unit_order_mismatch_count": 0,
    "route_compact_sentence_id_mismatch_count": 0,
    "route_compact_sentence_text_mismatch_count": 0,
    "runtime_source_sentence_id_mismatch_count": 0,
    "runtime_sentence_source_block_mismatch_count": 0,
    "scope_assessment_evidence_mismatch_count": 0,
    "warning_count": 0,
    "error_count": 0,
}


def _report_status(*, error_count: int, warning_count: int) -> str:
    if error_count:
        return "fail"
    if warning_count:
        return "warning"
    return "pass"


def _count_issues_by_code(issues: Sequence[Mapping[str, Any]], code: str) -> int:
    return sum(1 for issue in issues if issue.get("code") == code)


def _compact_handoff_summary(
    issues: Sequence[Mapping[str, Any]],
    *,
    aggregate_units: Sequence[Mapping[str, Any]],
    assessment_input: Mapping[str, Any],
) -> dict[str, int]:
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    compact_unit_ids = [unit_id for unit_id, _unit in iter_compact_assessment_units(assessment_input)]
    route_unit_ids = [
        str(unit.get("unit_id") or "").strip()
        for unit in aggregate_units
        if isinstance(unit, dict) and str(unit.get("unit_id") or "").strip()
    ]
    route_id_set = set(route_unit_ids)
    compact_id_set = set(compact_unit_ids)
    evidence_codes = {
        "scope_assessment_evidence_missing_unit",
        "scope_assessment_evidence_empty_unit_text",
        "scope_assessment_evidence_unit_text_mismatch",
        "scope_assessment_evidence_candidate_text_mismatch",
        "scope_assessment_evidence_empty_scope_text",
        "scope_assessment_evidence_missing",
    }
    return {
        "expected_aggregate_unit_count": len(route_unit_ids),
        "assessment_input_unit_count": len(compact_unit_ids),
        "missing_aggregate_unit_count": _count_issues_by_code(
            issues,
            "aggregate_route_unit_missing_from_assessment_input",
        ),
        "extra_assessment_unit_count": _count_issues_by_code(
            issues,
            "assessment_input_unit_not_in_aggregate_route",
        ),
        "aggregate_route_unit_order_mismatch_count": _count_issues_by_code(
            issues,
            "aggregate_route_unit_order_mismatch",
        ),
        "route_compact_sentence_id_mismatch_count": _count_issues_by_code(
            issues,
            "route_compact_sentence_id_mismatch",
        ),
        "route_compact_sentence_text_mismatch_count": _count_issues_by_code(
            issues,
            "route_compact_sentence_text_mismatch",
        ),
        "runtime_source_sentence_id_mismatch_count": _count_issues_by_code(
            issues,
            "runtime_source_sentence_id_mismatch",
        ),
        "runtime_sentence_source_block_mismatch_count": _count_issues_by_code(
            issues,
            "runtime_sentence_source_block_mismatch",
        ),
        "scope_assessment_evidence_mismatch_count": sum(
            1 for issue in issues if str(issue.get("code") or "") in evidence_codes
        ),
        "route_unit_count": len(route_unit_ids),
        "compact_unit_count": len(compact_unit_ids),
        "route_unit_id_set_matches_compact": int(route_id_set == compact_id_set),
        "warning_count": warning_count,
        "error_count": error_count,
    }


def _compact_integrity_summary(summary: dict[str, Any]) -> dict[str, int]:
    return {
        "missing_aggregate_unit_count": int(summary.get("missing_aggregate_unit_count") or 0),
        "extra_assessment_unit_count": int(summary.get("extra_assessment_unit_count") or 0),
        "aggregate_route_unit_order_mismatch_count": int(
            summary.get("aggregate_route_unit_order_mismatch_count") or 0
        ),
        "route_compact_sentence_id_mismatch_count": int(
            summary.get("route_compact_sentence_id_mismatch_count") or 0
        ),
        "route_compact_sentence_text_mismatch_count": int(
            summary.get("route_compact_sentence_text_mismatch_count") or 0
        ),
        "runtime_source_sentence_id_mismatch_count": int(
            summary.get("runtime_source_sentence_id_mismatch_count") or 0
        ),
        "runtime_sentence_source_block_mismatch_count": int(
            summary.get("runtime_sentence_source_block_mismatch_count") or 0
        ),
        "scope_assessment_evidence_mismatch_count": int(
            summary.get("scope_assessment_evidence_mismatch_count") or 0
        ),
        "warning_count": int(summary.get("warning_count") or 0),
        "error_count": int(summary.get("error_count") or 0),
    }


def validate_aggregate_prepare_handoff(
    *,
    assessment_input: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    aggregate_units: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate Route→compact→provenance→assessment_evidence handoff and build report."""
    if aggregate_units is None:
        raise ValueError("aggregate_units is required for aggregate_prepare handoff validation")

    issues = collect_scoped_assessment_handoff_issues(
        assessment_input,
        runtime_context,
        aggregate_units=aggregate_units,
    )
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    summary = _compact_handoff_summary(
        issues,
        aggregate_units=aggregate_units,
        assessment_input=assessment_input,
    )
    return {
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "validation_scope": "aggregate_prepare_handoff",
        "status": _report_status(error_count=error_count, warning_count=warning_count),
        "summary": summary,
        "issues": list(issues),
    }


def compact_unit_integrity_summary(report: dict[str, Any]) -> dict[str, int]:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return _compact_integrity_summary(_EMPTY_HANDOFF_SUMMARY)
    return _compact_integrity_summary(summary)
