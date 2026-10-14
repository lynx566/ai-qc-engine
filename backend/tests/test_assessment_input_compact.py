"""Tests for compact heading-scoped assessment_input (PR2A)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    ASSESSMENT_RUNTIME_CONTEXT_SCHEMA_VERSION,
    build_assessment_runtime_context_envelope,
    build_assessment_runtime_context_id,
    collect_scoped_assessment_handoff_issues,
    compact_assessment_units_for_integrity,
    validate_assessment_runtime_context,
    validate_compact_assessment_input_shape,
    validate_scoped_assessment_cross_artifacts,
    validate_scoped_assessment_identity,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    build_scope_aware_prompt_input,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
    validate_assessment_input,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    attach_assessment_evidence_to_heading_scopes,
    build_heading_scopes_from_aggregate_units,
    build_unit_provenance_map,
    heading_scope_signature,
)


def _aggregate_unit(
    *,
    unit_id: str,
    heading_path: list[str],
    context_block_ids: list[str],
    source_zone_key: str = "dsur_clinical_safety_zh",
    candidate_text: str | None = None,
    sentences: list[dict[str, str]] | None = None,
) -> dict:
    del candidate_text
    sentence_list = sentences or [
        {
            "sentence_id": "S0001",
            "text": f"text for {unit_id}",
            "source_block_id": f"C{unit_id[-4:]}",
        }
    ]
    return {
        "unit_id": unit_id,
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": "clinical_safety_default_text",
        "heading_path": heading_path,
        "sentences": sentence_list,
        "source_block_ids": [f"C{unit_id[-4:]}"],
        "context_block_ids": context_block_ids,
        "all_source_block_ids": list(context_block_ids) + [f"C{unit_id[-4:]}"],
        "candidate_block_kinds": ["paragraph"],
        "text_refs": [],
        "source_stage": "filter",
        "source_zone_key": source_zone_key,
        "route_matched_terms": [],
        "source_component_ids": [],
        "overview_decompose_bundle_id": None,
    }


def _runtime_context_for_units(
    *,
    units: list[dict],
    assessment_input: dict,
) -> dict:
    llm_input_bundle_id = str(assessment_input["llm_input_bundle_id"])
    runtime_context_id = build_assessment_runtime_context_id(
        llm_input_bundle_id=llm_input_bundle_id,
    )
    return build_assessment_runtime_context_envelope(
        llm_input_bundle_id=llm_input_bundle_id,
        runtime_context_id=runtime_context_id,
        doc_id=str(assessment_input["doc_id"]),
        file_hash=str(assessment_input["file_hash"]),
        route_stats={"unit_count": len(units)},
        unit_provenance=build_unit_provenance_map(units),
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": "routed_test",
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": "route_test",
            "path": "routing_manifest.json",
        },
    )


def _compact_assessment_input_from_units(units: list[dict]) -> tuple[dict, dict]:
    heading_scopes = build_heading_scopes_from_aggregate_units(units)
    attach_assessment_evidence_to_heading_scopes(heading_scopes, units)
    assessment_input = {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": "llm_input_aggregate_test",
        "route": "aggregate",
        "doc_id": "doc_test",
        "zone_key": "dsur_clinical_safety_zh",
        "file_hash": "sha256:test",
        "doc_meta": {"doc_type": "DSUR"},
        "instructions": "test",
        "assessment_profile_ref": "clinical_safety_aggregate_heading_scope_assessment_zh",
        "heading_scopes": heading_scopes,
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_aggregate_test"},
    }
    runtime_context = _runtime_context_for_units(units=units, assessment_input=assessment_input)
    assessment_input["runtime_context_ref"]["runtime_context_id"] = runtime_context[
        "runtime_context_id"
    ]
    return assessment_input, runtime_context


def test_consecutive_same_scope_aggregation() -> None:
    units = [
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
        _aggregate_unit(
            unit_id="TU0003",
            heading_path=["Section B"],
            context_block_ids=["C0011"],
        ),
    ]
    scopes = build_heading_scopes_from_aggregate_units(units)
    assert [scope["scope_id"] for scope in scopes] == ["HS0001", "HS0002"]
    assert [unit["unit_id"] for unit in scopes[0]["units"]] == ["TU0001", "TU0002"]
    assert [unit["unit_id"] for unit in scopes[1]["units"]] == ["TU0003"]


def test_same_heading_non_consecutive_not_merged() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["Section A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["Section B"], context_block_ids=["C0011"]),
        _aggregate_unit(unit_id="TU0003", heading_path=["Section A"], context_block_ids=["C0012"]),
    ]
    scopes = build_heading_scopes_from_aggregate_units(units)
    assert len(scopes) == 3


def test_same_heading_different_lineage_not_merged() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["Section A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["Section A"], context_block_ids=["C0011"]),
    ]
    scopes = build_heading_scopes_from_aggregate_units(units)
    assert len(scopes) == 2


def test_overview_fallback_scope_groups_by_zone_and_heading() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Overview A"],
            context_block_ids=[],
            source_zone_key="dsur_overview_zh",
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["Overview A"],
            context_block_ids=[],
            source_zone_key="dsur_overview_zh",
        ),
        _aggregate_unit(
            unit_id="TU0003",
            heading_path=["Overview B"],
            context_block_ids=[],
            source_zone_key="dsur_overview_zh",
        ),
    ]
    scopes = build_heading_scopes_from_aggregate_units(units)
    assert [scope["scope_id"] for scope in scopes] == ["HS0001", "HS0002"]
    assert [unit["unit_id"] for unit in scopes[0]["units"]] == ["TU0001", "TU0002"]


def test_compact_unit_field_contract() -> None:
    units = [_aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"])]
    scopes = build_heading_scopes_from_aggregate_units(units)
    unit = scopes[0]["units"][0]
    assert set(unit) == {"unit_id", "sentences"}
    assert set(unit["sentences"][0]) == {"sentence_id", "text"}


def test_runtime_provenance_completeness_and_identity_mismatch() -> None:
    units = [_aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"])]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    validate_assessment_runtime_context(runtime_context)
    validate_scoped_assessment_cross_artifacts(assessment_input, runtime_context)
    bad_runtime = copy.deepcopy(runtime_context)
    bad_runtime["runtime_context_id"] = "assessment_runtime_wrong"
    with pytest.raises(ValueError, match="runtime_context_id mismatch"):
        validate_scoped_assessment_identity(assessment_input, bad_runtime)


def _heading_scopes_user_payload(messages: list[dict[str, str]]) -> list[dict]:
    user = next(message for message in messages if message["role"] == "user")
    payload = json.loads(user["content"].split("## Heading scopes and units\n", 1)[1])
    return payload


def test_scope_aware_prompt_input_builder() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "安全句子。",
                    "source_block_id": "C0001",
                }
            ],
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)
    prompt_input = llm_input.prompt_input_bundle
    scope = prompt_input["heading_scopes"][0]
    assert scope["candidate_text"] == "安全句子。"
    assert set(scope.keys()) == {"scope_id", "heading_path", "candidate_text"}
    assert scope["scope_id"] == "S0001"
    assert "units" not in prompt_input
    assert "clinical_program_id" not in prompt_input


def test_prompt_scope_aware_smaller_than_legacy_expanded() -> None:
    units = [
        _aggregate_unit(
            unit_id=f"TU{index:04d}",
            heading_path=["Shared Heading"],
            context_block_ids=["C0010"],
            candidate_text=f"text {index}",
        )
        for index in range(1, 6)
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)
    prompt_input = llm_input.prompt_input_bundle
    fat_units = [
        {
            "unit_id": unit["unit_id"],
            "sentences": unit["sentences"],
            "provenance": runtime_context["unit_provenance"][unit["unit_id"]],
        }
        for scope in assessment_input["heading_scopes"]
        for unit in scope["units"]
    ]
    legacy_chars = len(json.dumps(fat_units, ensure_ascii=False))
    new_chars = len(json.dumps(prompt_input["heading_scopes"], ensure_ascii=False))
    assert new_chars < legacy_chars
    assert len(prompt_input["heading_scopes"]) == 1
    assert "\n\n" in prompt_input["heading_scopes"][0]["candidate_text"]


def test_handoff_identity_mismatch_fail_fast() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["A"], context_block_ids=["C0010"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)

    missing = copy.deepcopy(assessment_input)
    missing["heading_scopes"][0]["units"] = missing["heading_scopes"][0]["units"][:1]
    issues = collect_scoped_assessment_handoff_issues(
        missing,
        runtime_context,
        aggregate_units=units,
    )
    assert any(
        issue["code"] == "aggregate_route_unit_missing_from_assessment_input"
        for issue in issues
    )

    extra = copy.deepcopy(assessment_input)
    extra["heading_scopes"][0]["units"].append(
        {
            "unit_id": "TU9999",
            "sentences": [{"sentence_id": "S9999", "text": "extra"}],
        }
    )
    issues = collect_scoped_assessment_handoff_issues(
        extra,
        runtime_context,
        aggregate_units=units,
    )
    assert any(
        issue["code"] == "assessment_input_unit_not_in_aggregate_route"
        for issue in issues
    )

    duplicate = copy.deepcopy(assessment_input)
    duplicate["heading_scopes"][0]["units"].append(
        duplicate["heading_scopes"][0]["units"][0]
    )
    issues = collect_scoped_assessment_handoff_issues(
        duplicate,
        runtime_context,
        aggregate_units=units,
    )
    assert any(issue["code"] == "assessment_input_duplicate_unit_id" for issue in issues)

    reordered = copy.deepcopy(assessment_input)
    reordered["heading_scopes"][0]["units"] = list(
        reversed(reordered["heading_scopes"][0]["units"])
    )
    issues = collect_scoped_assessment_handoff_issues(
        reordered,
        runtime_context,
        aggregate_units=units,
    )
    assert any(issue["code"] == "aggregate_route_unit_order_mismatch" for issue in issues)


def test_schema_rejects_legacy_units_field() -> None:
    payload = {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": "llm_input_aggregate_test",
        "route": "aggregate",
        "clinical_program_id": "clinical_program_001",
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_test"},
        "units": [{"unit_id": "TU0001", "route": "aggregate"}],
    }
    with pytest.raises(ValueError, match="legacy top-level units"):
        validate_compact_assessment_input_shape(payload)


def test_integrity_flatten_helper() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["B"], context_block_ids=["C0011"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    flattened = compact_assessment_units_for_integrity(assessment_input, runtime_context)
    assert flattened == [
        {"unit_id": "TU0001", "source_block_ids": ["C0001"]},
        {"unit_id": "TU0002", "source_block_ids": ["C0002"]},
    ]


def test_heading_scope_signature_overview_uses_zone_and_heading_only() -> None:
    unit = _aggregate_unit(
        unit_id="TU0001",
        heading_path=["Overview"],
        context_block_ids=[],
        source_zone_key="dsur_overview_zh",
    )
    assert heading_scope_signature(unit) == ("dsur_overview_zh", ("Overview",))


def test_validate_assessment_input_accepts_compact_shape() -> None:
    units = [_aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"])]
    assessment_input, _runtime = _compact_assessment_input_from_units(units)
    validate_assessment_input(assessment_input)


def test_runtime_context_schema_version_required() -> None:
    units = [_aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"])]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    runtime_context["schema_version"] = "9.9.9"
    with pytest.raises(ValueError, match="unsupported assessment_runtime_context"):
        validate_assessment_runtime_context(runtime_context)
    validate_scoped_assessment_cross_artifacts(assessment_input, runtime_context)
    assert ASSESSMENT_RUNTIME_CONTEXT_SCHEMA_VERSION == "0.3.0"
