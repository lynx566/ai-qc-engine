"""Heading-scope eligibility policy tests."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_STATUSES,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy import (
    build_heading_scope_eligibility_entries,
    evaluate_heading_scope_eligibility,
)


def _scope(**overrides: object) -> dict:
    base = {
        "scope_id": "HS0001",
        "heading_path": ["安全性"],
        "source_unit_ids": ["TU0001"],
        "unit_form": "aggregate",
        "route_qc": {
            "route_mismatch": False,
            "suggested_route": "aggregate",
            "reason": None,
        },
        "safety_role": "primary_safety_finding",
        "product_context_role": "target_study_drug",
    }
    base.update(overrides)
    return base


def test_auto_included_target_study_drug() -> None:
    result = evaluate_heading_scope_eligibility(scope_assessment=_scope())
    assert result["status"] == "auto_included"


def test_review_ambiguous_unknown_safety_role() -> None:
    result = evaluate_heading_scope_eligibility(scope_assessment=_scope(safety_role="unknown"))
    assert result["status"] == "review_ambiguous"


def test_build_entries_preserves_order() -> None:
    scopes = [_scope(scope_id="HS0001"), _scope(scope_id="HS0002")]
    entries = build_heading_scope_eligibility_entries(scope_assessments=scopes)
    assert [entry["scope_id"] for entry in entries] == ["HS0001", "HS0002"]
    assert all("eligibility_decision" in entry for entry in entries)


def test_deterministic_for_same_input() -> None:
    base = _scope()
    changed = copy.deepcopy(base)
    changed["heading_path"] = ["different heading"]
    assert evaluate_heading_scope_eligibility(scope_assessment=base) == (
        evaluate_heading_scope_eligibility(scope_assessment=changed)
    )


def test_retiring_context_semantics_does_not_change_eligibility() -> None:
    base = _scope()
    changed = copy.deepcopy(base)
    changed["study_context"] = {
        "context_level": "program_level",
        "protocol_ids": ["Protocol_999"],
        "raw_text": "different study context",
    }
    changed["time_anchor"] = {
        "type": "data_cutoff",
        "value": "2025-01-01",
        "start_date": None,
        "end_date": None,
        "raw_text": "different time anchor",
    }
    changed["population_context"] = {
        "population_basis": "safety_population",
        "population_scope": "subgroup",
        "subgroup_context": {
            "type": "age",
            "value": "older_adults",
            "raw_text": "different population",
        },
    }

    assert evaluate_heading_scope_eligibility(scope_assessment=base) == (
        evaluate_heading_scope_eligibility(scope_assessment=changed)
    )


def test_all_statuses_are_declared() -> None:
    assert "auto_included" in HEADING_SCOPE_ELIGIBILITY_STATUSES
