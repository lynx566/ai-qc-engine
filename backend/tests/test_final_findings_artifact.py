"""Tests for the product-final findings artifact contract."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    FINAL_FINDINGS_ARTIFACT_TYPE,
    FINAL_FINDINGS_COMPARISON_MODE_ORDER,
    FINAL_FINDINGS_FILENAME,
    FINAL_FINDINGS_SCHEMA_VERSION,
    build_final_findings,
    validate_final_findings,
)


def _finding(
    finding_id: str = "L001",
    *,
    source_finding_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "label": "fail",
        "conclusion": "Product-final conclusion",
        "source_sentence_aliases": ["T0001"],
        "comparison_mode_id": "scope_local",
        "source_finding_ids": source_finding_ids or ["L101"],
    }


def test_builds_completed_product_final_artifact_with_empty_findings() -> None:
    payload = build_final_findings(
        finalization_status="completed",
        fallback_comparison_modes=[],
        findings=[],
    )

    assert payload == {
        "artifact_type": "final_findings",
        "schema_version": "0.1.0",
        "finalization_status": "completed",
        "fallback_comparison_modes": [],
        "findings": [],
    }
    assert FINAL_FINDINGS_FILENAME == "final_findings.json"
    assert FINAL_FINDINGS_ARTIFACT_TYPE == "final_findings"
    assert FINAL_FINDINGS_SCHEMA_VERSION == "0.1.0"
    validate_final_findings(payload)


def test_artifact_owns_canonical_comparison_mode_order() -> None:
    assert FINAL_FINDINGS_COMPARISON_MODE_ORDER == (
        "scope_local",
        "focus_comparison",
        "ib_to_dsur",
        "dsur_to_ib",
    )
    payload = build_final_findings(
        finalization_status="completed_with_fallback",
        fallback_comparison_modes=["scope_local", "ib_to_dsur"],
        findings=[_finding()],
    )
    validate_final_findings(payload)


def test_source_sentence_aliases_do_not_gain_an_unfrozen_uniqueness_rule() -> None:
    finding = _finding()
    finding["source_sentence_aliases"] = ["T0001", "T0001"]

    payload = build_final_findings(
        finalization_status="completed",
        fallback_comparison_modes=[],
        findings=[finding],
    )

    validate_final_findings(payload)


@pytest.mark.parametrize(
    ("status", "fallback_modes"),
    [
        ("completed", ["scope_local"]),
        ("completed_with_fallback", []),
    ],
)
def test_status_and_fallback_presence_must_agree(
    status: str,
    fallback_modes: list[str],
) -> None:
    with pytest.raises(ValueError, match="finalization_status"):
        build_final_findings(
            finalization_status=status,
            fallback_comparison_modes=fallback_modes,
            findings=[],
        )


@pytest.mark.parametrize(
    "fallback_modes",
    [
        ["ib_to_dsur", "scope_local"],
        ["scope_local", "scope_local"],
        ["unsupported"],
    ],
)
def test_fallback_modes_must_be_a_canonical_ordered_subsequence(
    fallback_modes: list[str],
) -> None:
    with pytest.raises(ValueError, match="fallback_comparison_modes"):
        build_final_findings(
            finalization_status="completed_with_fallback",
            fallback_comparison_modes=fallback_modes,
            findings=[],
        )


def test_rejects_duplicate_product_final_finding_ids() -> None:
    with pytest.raises(ValueError, match="duplicate finding_id"):
        build_final_findings(
            finalization_status="completed",
            fallback_comparison_modes=[],
            findings=[_finding(), _finding(source_finding_ids=["L102"])],
        )


def test_rejects_source_finding_id_reuse_across_final_findings() -> None:
    with pytest.raises(ValueError, match="source_finding_id.*across"):
        build_final_findings(
            finalization_status="completed",
            fallback_comparison_modes=[],
            findings=[
                _finding("L001", source_finding_ids=["L101"]),
                _finding("L002", source_finding_ids=["L101"]),
            ],
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("finding_id", "finding-1", "Lddd"),
        ("label", "pass", "label"),
        ("conclusion", " ", "conclusion"),
        ("source_sentence_aliases", [], "non-empty array"),
        ("source_sentence_aliases", ["S0001"], "Tdddd"),
        ("comparison_mode_id", "unsupported", "comparison_mode_id"),
        ("source_finding_ids", [], "non-empty array"),
        ("source_finding_ids", ["L101", "L101"], "unique"),
        ("source_finding_ids", ["source-1"], "Lddd"),
    ],
)
def test_rejects_invalid_flat_finding_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    finding = _finding()
    finding[field] = value

    with pytest.raises(ValueError, match=message):
        build_final_findings(
            finalization_status="completed",
            fallback_comparison_modes=[],
            findings=[finding],
        )


def test_rejects_unknown_root_and_finding_keys() -> None:
    payload = build_final_findings(
        finalization_status="completed",
        fallback_comparison_modes=[],
        findings=[_finding()],
    )
    root_with_extra = deepcopy(payload)
    root_with_extra["extra"] = True
    with pytest.raises(ValueError, match="root keys mismatch"):
        validate_final_findings(root_with_extra)

    finding_with_extra = deepcopy(payload)
    finding_with_extra["findings"][0]["extra"] = True
    with pytest.raises(ValueError, match=r"findings\[0\] keys mismatch"):
        validate_final_findings(finding_with_extra)
