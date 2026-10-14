"""Tests for plugin-owned aggregate scope assessment LLM-input preparation."""

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
    build_scope_assessment_task_manifest,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    build_scope_aware_prompt_input,
    scope_semantic_sort_key,
)
from tests.test_assessment_input_compact import (
    _aggregate_unit,
    _compact_assessment_input_from_units,
)


def _scope_task(scope_id: str, heading_path: list[str], candidate_text: str) -> dict:
    return {
        "scope_id": scope_id,
        "heading_path": heading_path,
        "units": [
            {
                "unit_id": f"TU_{scope_id}",
                "sentences": [{"sentence_id": "S0001", "text": candidate_text}],
            }
        ],
        "assessment_evidence": {"candidate_text": candidate_text},
    }


def _assessment_input_with_scopes(
    heading_scopes: list[dict],
    *,
    llm_input_bundle_id: str = "llm_input_llm_input_test",
) -> tuple[dict, dict]:
    assessment_input = {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": llm_input_bundle_id,
        "route": "aggregate",
        "doc_id": "doc_test",
        "zone_key": "dsur_clinical_safety_zh",
        "file_hash": "sha256:test",
        "doc_meta": {"doc_type": "DSUR"},
        "instructions": "test",
        "assessment_profile_ref": "clinical_safety_aggregate_heading_scope_assessment_zh",
        "heading_scopes": heading_scopes,
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_llm_input_test"},
    }
    unit_provenance: dict[str, dict] = {}
    for scope in heading_scopes:
        for unit in scope.get("units") or []:
            unit_id = str(unit.get("unit_id") or "")
            if not unit_id:
                continue
            unit_provenance[unit_id] = {
                "source_zone_key": "dsur_clinical_safety_zh",
                "context_block_ids": ["C0010"],
                "source_block_ids": [f"B_{unit_id}"],
                "all_source_block_ids": ["C0010", f"B_{unit_id}"],
                "candidate_text": scope["assessment_evidence"]["candidate_text"],
            }
    runtime_context = {
        "runtime_context_id": "assessment_runtime_llm_input_test",
        "llm_input_bundle_id": llm_input_bundle_id,
        "unit_provenance": unit_provenance,
    }
    return assessment_input, runtime_context


def _model_visible_payload(llm_input: object) -> str:
    return json.dumps(llm_input.prompt_input_bundle["heading_scopes"], ensure_ascii=False)


def test_same_semantic_scopes_different_hs_and_order_produce_equivalent_model_tasks() -> None:
    scope_alpha = _scope_task("HS0001", ["Alpha"], "alpha evidence")
    scope_beta = _scope_task("HS0002", ["Beta"], "beta evidence")
    input_one, runtime_one = _assessment_input_with_scopes([scope_alpha, scope_beta])

    shuffled_beta = copy.deepcopy(scope_beta)
    shuffled_beta["scope_id"] = "HS0099"
    shuffled_alpha = copy.deepcopy(scope_alpha)
    shuffled_alpha["scope_id"] = "HS0007"
    input_two, runtime_two = _assessment_input_with_scopes(
        [shuffled_beta, shuffled_alpha],
        llm_input_bundle_id="llm_input_llm_input_test_reordered",
    )

    llm_input_one = build_scope_aware_prompt_input(input_one, runtime_one)
    llm_input_two = build_scope_aware_prompt_input(input_two, runtime_two)

    assert _model_visible_payload(llm_input_one) == _model_visible_payload(llm_input_two)
    assert llm_input_one.prompt_input_bundle["heading_scopes"][0]["heading_path"] == ["Alpha"]
    assert llm_input_one.prompt_input_bundle["heading_scopes"][1]["heading_path"] == ["Beta"]


def test_model_visible_tasks_do_not_expose_hs_scope_ids() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
            candidate_text="安全句子。",
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)

    for scope in llm_input.prompt_input_bundle["heading_scopes"]:
        scope_id = scope["scope_id"]
        assert scope_id.startswith("S")
        assert not scope_id.startswith("HS")
        assert set(scope) == {"scope_id", "heading_path", "candidate_text"}


def test_s_alias_assignment_is_deterministic() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
            candidate_text="first",
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["Section B"],
            context_block_ids=["C0020"],
            candidate_text="second",
        ),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    first = build_scope_aware_prompt_input(assessment_input, runtime_context)
    second = build_scope_aware_prompt_input(assessment_input, runtime_context)

    assert first.alias_to_scope_id == second.alias_to_scope_id
    assert first.alias_to_scope_id == {"S0001": "HS0001", "S0002": "HS0002"}
    assert [scope["scope_id"] for scope in first.prompt_input_bundle["heading_scopes"]] == [
        "S0001",
        "S0002",
    ]


def test_artifact_task_manifest_remains_artifact_faithful() -> None:
    scope_alpha = _scope_task("HS0002", ["Beta"], "beta evidence")
    scope_beta = _scope_task("HS0001", ["Alpha"], "alpha evidence")
    assessment_input, runtime_context = _assessment_input_with_scopes([scope_alpha, scope_beta])

    manifest = build_scope_assessment_task_manifest(assessment_input)
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)

    assert [task["scope_id"] for task in manifest] == ["HS0002", "HS0001"]
    assert manifest[0]["candidate_text"] == "beta evidence"
    assert manifest[1]["candidate_text"] == "alpha evidence"
    assert llm_input.prompt_input_bundle["heading_scopes"][0]["scope_id"] == "S0001"
    assert llm_input.prompt_input_bundle["heading_scopes"][0]["heading_path"] == ["Alpha"]


def test_semantic_sort_key_ignores_hs_and_tu_order() -> None:
    scope_one = _scope_task("HS9999", ["Shared"], "shared text")
    scope_two = _scope_task("HS0001", ["Shared"], "shared text")
    scope_one["units"] = [
        {"unit_id": "TU9999", "sentences": [{"sentence_id": "S0001", "text": "shared text"}]}
    ]
    scope_two["units"] = [
        {"unit_id": "TU0001", "sentences": [{"sentence_id": "S0001", "text": "shared text"}]}
    ]
    assessment_input, runtime_context = _assessment_input_with_scopes([scope_one, scope_two])
    provenance = runtime_context["unit_provenance"]
    zone_key = str(assessment_input["zone_key"])

    key_one = scope_semantic_sort_key(scope_one, unit_provenance=provenance, zone_key=zone_key)
    key_two = scope_semantic_sort_key(scope_two, unit_provenance=provenance, zone_key=zone_key)
    assert key_one == key_two

    swapped_units_scope = copy.deepcopy(scope_one)
    swapped_units_scope["units"] = list(reversed(swapped_units_scope["units"]))
    key_swapped = scope_semantic_sort_key(
        swapped_units_scope,
        unit_provenance=provenance,
        zone_key=zone_key,
    )
    assert key_one == key_swapped


def test_semantic_sort_uses_heading_scope_signature_and_candidate_text() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section B"],
            context_block_ids=["C0020"],
            candidate_text="later heading",
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
            candidate_text="earlier heading",
        ),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)

    rendered_paths = [
        scope["heading_path"] for scope in llm_input.prompt_input_bundle["heading_scopes"]
    ]
    assert rendered_paths == [["Section A"], ["Section B"]]
