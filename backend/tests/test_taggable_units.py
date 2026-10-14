from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.taggable_units import (
    canonicalize_aggregate_text_unit,
    single_component_provenance,
    validate_aggregate_text_unit_contract,
    validate_optional_provenance_metadata,
)


def _valid_coverage_unit() -> dict:
    return {
        "unit_id": "TU0001",
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": "clinical_safety_default_text",
        "source_block_ids": ["C0001"],
        "sentences": [
            {
                "sentence_id": "S0001",
                "text": "block one",
                "source_block_id": "C0001",
            }
        ],
    }


def _valid_overview_unit() -> dict:
    return {
        "unit_id": "TU0005",
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": "overview_decompose_mock",
        "source_block_ids": ["C7001"],
        "source_component_ids": ["OVC_MATCH_001"],
        "source_component_types": ["safety_overview"],
        "source_component_sentences": [
            {
                "sentence_id": "OVC_MATCH_001:S0001",
                "text": "overview safety sentence",
                "source_block_id": "C7001",
            }
        ],
        "sentences": [
            {
                "sentence_id": "OVC_MATCH_001:S0001",
                "text": "overview safety sentence",
                "source_block_id": "C7001",
            }
        ],
    }


def test_canonicalize_accepts_coverage_and_overview_units() -> None:
    coverage = canonicalize_aggregate_text_unit(
        _valid_coverage_unit(),
        source_label="coverage_test",
    )
    overview = canonicalize_aggregate_text_unit(
        _valid_overview_unit(),
        source_label="overview_test",
    )

    assert coverage["route"] == "aggregate"
    assert overview["route"] == "aggregate"
    assert overview["source_component_ids"] == ["OVC_MATCH_001"]
    assert "source_component_ids" not in coverage
    assert coverage["sentences"][0]["sentence_id"] == "S0001"
    assert "candidate_sentences" not in coverage
    assert "candidate_text" not in coverage


def test_canonicalize_rejects_retired_body_duplicate_fields() -> None:
    unit = _valid_coverage_unit()
    unit["candidate_sentences"] = []
    with pytest.raises(ValueError, match="retired routed body field"):
        canonicalize_aggregate_text_unit(unit, source_label="coverage_test")


def test_canonicalize_rejects_empty_sentences() -> None:
    unit = _valid_coverage_unit()
    unit["sentences"] = []
    with pytest.raises(ValueError, match="sentences must be non-empty"):
        canonicalize_aggregate_text_unit(unit, source_label="coverage_test")


def test_single_component_provenance() -> None:
    component_id, component_type = single_component_provenance(_valid_overview_unit())
    assert component_id == "OVC_MATCH_001"
    assert component_type == "safety_overview"


def test_validate_optional_provenance_metadata_flags_multi_component() -> None:
    unit = {
        **_valid_overview_unit(),
        "source_component_ids": ["A", "B"],
    }
    issues = validate_optional_provenance_metadata(unit, unit_id="TU0005")
    assert any(
        issue["code"] == "aggregate_multiple_source_component_ids" for issue in issues
    )


def test_validate_aggregate_text_unit_contract_accepts_valid_unit() -> None:
    issues = validate_aggregate_text_unit_contract(
        _valid_coverage_unit(),
        unit_id="TU0001",
    )
    assert issues == []


def test_validate_aggregate_text_unit_contract_rejects_invalid_route() -> None:
    unit = {**_valid_coverage_unit(), "route": "case"}
    issues = validate_aggregate_text_unit_contract(unit, unit_id="TU0001")
    assert issues == []
