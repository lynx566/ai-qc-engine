"""Process stage schema validation tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
    validate_assessment_input,
    validate_aggregate_evidence_prepare_route_artifacts,
)
from artifacts.routing.schema import ROUTE_SCHEMA_VERSION, ROUTE_STAGE

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _route_bundle(*, route: str, units: list[dict] | None = None) -> dict:
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "stage": ROUTE_STAGE,
        "routed_unit_bundle_id": f"routed_units_{route}_coverage_test",
        "route": route,
        "doc_id": "doc_test",
        "zone_key": "ib_clinical_safety_zh",
        "file_hash": LINEAGE_FILE_HASH,
        "source_refs": {
            "route_input_id": "coverage_test",
            "block_manifest_id": "block_manifest_test",
            "analysis_bundle_id": "prepare_analysis_test",
        },
        "units": units or [],
    }


def _routing_manifest(*, route_counts: dict[str, int] | None = None) -> dict:
    counts = route_counts or {
        "aggregate": 1,
        "table": 0,
        "case": 0,
        "unknown": 0,
    }
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "stage": ROUTE_STAGE,
        "routing_manifest_id": "route_routing_coverage_test",
        "doc_id": "doc_test",
        "zone_key": "ib_clinical_safety_zh",
        "route_counts": counts,
        "route_artifact_files": {
            route: {
                "path": f"routed_units_{route}.json",
                "routed_unit_bundle_id": f"routed_units_{route}_coverage_test",
            }
            for route in ("aggregate", "table", "case", "unknown")
        },
        "units": [],
        "source_refs": {
            "route_input_id": "coverage_test",
            "block_manifest_id": "block_manifest_test",
            "analysis_bundle_id": "prepare_analysis_test",
        },
    }


def _valid_assessment_input() -> dict:
    return {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
        "source_stage": "route",
        "runtime_context_ref": {
            "runtime_context_id": "assessment_runtime_aggregate_coverage_test",
        },
        "llm_input_bundle_id": "llm_input_aggregate_coverage_test",
        "assessment_profile_ref": "clinical_safety_aggregate_heading_scope_assessment_zh",
        "route": "aggregate",
        "doc_id": "doc_test",
        "zone_key": "ib_clinical_safety_zh",
        "file_hash": LINEAGE_FILE_HASH,
        "heading_scopes": [
            {
                "scope_id": "HS0001",
                "heading_path": ["Section"],
                "assessment_evidence": {"candidate_text": "sample"},
                "units": [
                    {
                        "unit_id": "TU0001",
                        "sentences": [
                            {"sentence_id": "S0001", "text": "sample"},
                        ],
                    }
                ],
            }
        ],
    }


def test_valid_assessment_input_passes() -> None:
    validate_assessment_input(_valid_assessment_input())


def test_assessment_input_omits_clinical_program_id() -> None:
    payload = _valid_assessment_input()
    assert "clinical_program_id" not in payload
    validate_assessment_input(payload)


def test_assessment_input_schema_version_is_1_4_0() -> None:
    assert ASSESSMENT_INPUT_SCHEMA_VERSION == "1.4.0"
    payload = _valid_assessment_input()
    assert payload["schema_version"] == "1.4.0"


def test_assessment_input_rejects_wrong_source_stage() -> None:
    payload = _valid_assessment_input()
    payload["source_stage"] = "tag_prepare"
    with pytest.raises(ValueError, match="source_stage"):
        validate_assessment_input(payload)


def test_valid_assessment_input_omits_comparison_type() -> None:
    payload = _valid_assessment_input()
    assert "comparison_type" not in payload
    validate_assessment_input(payload)


def test_assessment_input_rejects_legacy_units_field() -> None:
    payload = _valid_assessment_input()
    payload["units"] = [{"unit_id": "TU0001", "route": "case"}]
    with pytest.raises(ValueError, match="legacy top-level units"):
        validate_assessment_input(payload)


def test_assessment_input_rejects_legacy_tag_profile_ref() -> None:
    payload = _valid_assessment_input()
    payload["tag_profile_ref"] = payload.pop("assessment_profile_ref")
    with pytest.raises(ValueError, match="legacy field tag_profile_ref"):
        validate_assessment_input(payload)


def test_assessment_input_rejects_dual_profile_ref_fields() -> None:
    payload = _valid_assessment_input()
    payload["tag_profile_ref"] = payload["assessment_profile_ref"]
    with pytest.raises(ValueError, match="legacy field tag_profile_ref"):
        validate_assessment_input(payload)


def test_assessment_input_requires_assessment_profile_ref() -> None:
    payload = _valid_assessment_input()
    payload.pop("assessment_profile_ref")
    with pytest.raises(ValueError, match="assessment_profile_ref"):
        validate_assessment_input(payload)


def test_validate_route_artifacts_selected_aggregate_matches_manifest() -> None:
    aggregate = _route_bundle(route="aggregate", units=[{"unit_id": "TU1", "route": "aggregate"}])
    manifest = _routing_manifest()
    validate_aggregate_evidence_prepare_route_artifacts(
        aggregate_bundle=aggregate,
        routing_manifest=manifest,
    )


def test_validate_route_artifacts_rejects_manifest_aggregate_id_mismatch() -> None:
    aggregate = _route_bundle(route="aggregate", units=[{"unit_id": "TU1", "route": "aggregate"}])
    manifest = _routing_manifest()
    manifest["route_artifact_files"]["aggregate"]["routed_unit_bundle_id"] = "other_id"
    with pytest.raises(ValueError, match="routed_unit_bundle_id mismatch"):
        validate_aggregate_evidence_prepare_route_artifacts(
            aggregate_bundle=aggregate,
            routing_manifest=manifest,
        )
