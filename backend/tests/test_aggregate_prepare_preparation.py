"""Tests for the aggregate-evidence semantic preparation processor."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
    build_aggregate_evidence_assessment_input_envelope,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    attach_assessment_evidence_to_heading_scopes,
    build_heading_scopes_from_aggregate_units,
    prepare_aggregate_evidence_semantic_result,
)
from tests.test_assessment_input_compact import _aggregate_unit


def _minimal_prepare_inputs() -> dict:
    return {
        "aggregate_bundle": {
            "units": [
                _aggregate_unit(
                    unit_id="TU0001",
                    heading_path=["Section A"],
                    context_block_ids=["C0010"],
                ),
                _aggregate_unit(
                    unit_id="TU0002",
                    heading_path=["Section A"],
                    context_block_ids=["C0010"],
                ),
            ]
        },
        "coverage_bundle": {
            "coverage_bundle_id": "coverage_test",
            "doc_id": "doc_test",
            "zone_key": "ib_clinical_safety_zh",
            "file_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "coverage": [],
            "block_manifest_ref": {"block_manifest_id": "block_manifest_test"},
            "analysis_bundle_ref": {"analysis_bundle_id": "analysis_test"},
        },
        "block_manifest": {
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "analysis_bundle_ref": {"analysis_bundle_id": "analysis_test"},
            "blocks": [],
            "table_blocks": [],
        },
        "doc_meta_bundle": {
            "doc_meta_bundle_id": "doc_meta_test",
            "doc_id": "doc_test",
            "summary": {"protocol_ids": ["Protocol_001"]},
        },
        "assessment_profile_ref": CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref,
        "instructions": CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.instructions,
    }


def test_prepare_aggregate_evidence_semantic_result_heading_scopes() -> None:
    inputs = _minimal_prepare_inputs()
    result = prepare_aggregate_evidence_semantic_result(**inputs)
    scopes = result["heading_scopes"]
    assert [scope["scope_id"] for scope in scopes] == ["HS0001"]
    assert [unit["unit_id"] for unit in scopes[0]["units"]] == ["TU0001", "TU0002"]
    assert scopes[0]["units"][0]["sentences"][0]["sentence_id"] == "S0001"
    assert scopes[0]["assessment_evidence"]["candidate_text"]


def test_envelope_builder_preserves_semantic_heading_scopes() -> None:
    inputs = _minimal_prepare_inputs()
    semantic = prepare_aggregate_evidence_semantic_result(**inputs)
    envelope = build_aggregate_evidence_assessment_input_envelope(
        semantic_result=semantic,
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": "routed_test",
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": "route_test",
            "path": "routing_manifest.json",
        },
    )
    assert envelope["assessment_input"]["heading_scopes"] == semantic["heading_scopes"]
    assert envelope["assessment_runtime_context"]["unit_provenance"] == semantic["unit_provenance"]
    assert "llm_input_bundle_id" in envelope["assessment_input"]
    assert "runtime_context_id" in envelope["assessment_runtime_context"]
    assert (
        envelope["assessment_input"]["assessment_profile_ref"]
        == "clinical_safety_aggregate_heading_scope_assessment_zh"
    )
    assert "tag_profile_ref" not in envelope["assessment_input"]


def test_overview_unit_sentence_join_rule() -> None:
    unit = _aggregate_unit(
        unit_id="TU0001",
        heading_path=["Overview"],
        context_block_ids=[],
        source_zone_key="dsur_overview_zh",
    )
    unit["source_stage"] = "overview_decompose"
    unit["sentences"] = [
        {"sentence_id": "S0001", "text": "Line one", "source_block_id": "B1"},
        {"sentence_id": "S0002", "text": "Line two", "source_block_id": "B1"},
    ]
    scopes = build_heading_scopes_from_aggregate_units([unit])
    attach_assessment_evidence_to_heading_scopes(scopes, [unit])
    assert scopes[0]["assessment_evidence"]["candidate_text"] == "Line one\nLine two"
