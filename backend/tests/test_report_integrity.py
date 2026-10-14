"""Pure integrity composition rules for Task-owned qc_report composition."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from task.clinical_trial_doc_qc.report_integrity import (
    contribution_flow_execution_adjustments,
    is_lossless_consolidation_fallback,
    result_domain_integrity,
)


@dataclass(frozen=True)
class _Scope:
    execution_status: str


@dataclass(frozen=True)
class _Result:
    scope_results: tuple[_Scope, ...]
    comparison_run_status: str | None
    finalization_status: str
    fallback_comparison_modes: tuple[str, ...]


def _result(**kwargs) -> _Result:
    defaults = {
        "scope_results": (_Scope("complete"),),
        "comparison_run_status": "success",
        "finalization_status": "completed",
        "fallback_comparison_modes": (),
    }
    defaults.update(kwargs)
    return _Result(**defaults)


def test_lossless_fallback_detection():
    assert is_lossless_consolidation_fallback(
        _result(
            finalization_status="completed_with_fallback",
            fallback_comparison_modes=("scope_local",),
        )
    )
    assert not is_lossless_consolidation_fallback(
        _result(finalization_status="completed_with_fallback")
    )


def test_partial_failure_without_lossless_fallback_downgrades_integrity():
    integrity = result_domain_integrity(
        _result(comparison_run_status="partial_failure")
    )
    assert integrity["status"] == "partial"
    assert integrity["limitations"]


def test_partial_failure_with_lossless_fallback_keeps_complete_integrity():
    integrity = result_domain_integrity(
        _result(
            comparison_run_status="partial_failure",
            finalization_status="completed_with_fallback",
            fallback_comparison_modes=("scope_local",),
        )
    )
    assert integrity["status"] == "complete"
    assert any("未合并" in text for text in integrity["limitations"])


def test_flow_partial_does_not_force_contribution_partial_for_lossless_fallback():
    domain = result_domain_integrity(
        _result(
            comparison_run_status="partial_failure",
            finalization_status="completed_with_fallback",
            fallback_comparison_modes=("scope_local",),
        )
    )
    forced, limitations = contribution_flow_execution_adjustments(
        "partial", domain, _result()
    )
    assert forced is None
    assert limitations == []
