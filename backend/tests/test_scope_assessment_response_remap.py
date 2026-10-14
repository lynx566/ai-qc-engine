"""Tests for S-namespace execution and HS response remap (Slice B)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    ScopeAssessmentContractError,
    validate_and_canonicalize_scope_assessment_response,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    ScopeAssessmentLlmInput,
    build_scope_aware_prompt_input,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    build_clinical_safety_aggregate_heading_scope_assessment_zh_messages,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import (
    _remap_model_scope_ids_to_canonical,
    run_scope_assessment_api,
    run_scope_assessment_mock,
)
from tests.test_assessment_llm_input import (
    _assessment_input_with_scopes,
    _scope_task,
)
from tests.test_assessment_input_compact import (
    _aggregate_unit,
    _compact_assessment_input_from_units,
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _heading_scopes() -> list[dict[str, Any]]:
    return [
        {
            "scope_id": "HS0001",
            "heading_path": ["安全性总结"],
            "assessment_evidence": {"candidate_text": "总体安全性可接受。"},
            "units": [
                {
                    "unit_id": "TU0001",
                    "sentences": [{"sentence_id": "S0001", "text": "总体安全性可接受。"}],
                }
            ],
        },
        {
            "scope_id": "HS0002",
            "heading_path": ["个例"],
            "assessment_evidence": {"candidate_text": "一名受试者发生严重皮疹。"},
            "units": [
                {
                    "unit_id": "TU0002",
                    "sentences": [{"sentence_id": "S0002", "text": "一名受试者发生严重皮疹。"}],
                }
            ],
        },
    ]


def _assessment_input() -> dict[str, Any]:
    return {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": "llm_input_test_scope_remap",
        "doc_id": "doc_scope_test",
        "file_hash": LINEAGE_FILE_HASH,
        "document_type": "dsur",
        "zone_key": "dsur_clinical_safety_zh",
        "route": "aggregate",
        "doc_meta": {"study_drug": "StudyDrug_001"},
        "instructions": "classify aggregate evidence",
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_test_scope_remap"},
        "heading_scopes": _heading_scopes(),
    }


def _runtime_context() -> dict[str, Any]:
    return {
        "runtime_context_id": "assessment_runtime_test_scope_remap",
        "llm_input_bundle_id": "llm_input_test_scope_remap",
        "unit_provenance": {
            "TU0001": {
                "source_zone_key": "dsur_clinical_safety_zh",
                "context_block_ids": ["C0010"],
                "source_block_ids": ["B0001"],
                "all_source_block_ids": ["C0010", "B0001"],
                "candidate_text": "总体安全性可接受。",
            },
            "TU0002": {
                "source_zone_key": "dsur_clinical_safety_zh",
                "context_block_ids": ["C0020"],
                "source_block_ids": ["B0002"],
                "all_source_block_ids": ["C0020", "B0002"],
                "candidate_text": "一名受试者发生严重皮疹。",
            },
        },
    }


def _llm_execution_inputs() -> ScopeAssessmentLlmInput:
    return build_scope_aware_prompt_input(_assessment_input(), _runtime_context())


def _raw_assessment(scope_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "scope_id": scope_id,
        "unit_form": "aggregate",
        "safety_role": "primary_safety_finding",
        "product_context_role": "target_study_drug",
        "route_qc": {
            "route_mismatch": False,
            "suggested_route": None,
            "reason": None,
        },
    }
    payload.update(overrides)
    return payload


def _raw_response_for_llm_input(llm_input: ScopeAssessmentLlmInput) -> dict[str, Any]:
    model_scope_ids = [
        scope["scope_id"] for scope in llm_input.prompt_input_bundle["heading_scopes"]
    ]
    assessments = [_raw_assessment(model_scope_ids[0])]
    if len(model_scope_ids) > 1:
        assessments.append(
            _raw_assessment(
                model_scope_ids[1],
                unit_form="case_like",
                route_qc={
                    "route_mismatch": True,
                    "suggested_route": "case",
                    "reason": "individual subject narrative",
                },
            )
        )
    return {"scope_assessments": assessments}


class _FakeProvider:
    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text

    def generate(self, _messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            raw_text=self.raw_text,
            provider_name="fake",
            model="fake-model",
            finish_reason="stop",
            usage={"completion_tokens": 12, "prompt_tokens": 3, "total_tokens": 15},
        )


def test_api_path_uses_s_namespace_and_restores_hs_in_final_output() -> None:
    llm_input = _llm_execution_inputs()
    messages = build_clinical_safety_aggregate_heading_scope_assessment_zh_messages(
        llm_input.prompt_input_bundle
    )
    rendered = "\n".join(message["content"] for message in messages)
    assert '"scope_id": "S0001"' in rendered or '"scope_id":"S0001"' in rendered.replace(" ", "")
    assert "HS0001" not in rendered

    result = run_scope_assessment_api(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        llm_profile="deepseek_v4_flash",
        provider=_FakeProvider(
            json.dumps(_raw_response_for_llm_input(llm_input), ensure_ascii=False)
        ),
    )
    envelope = result["scope_assessments"]
    assert envelope is not None
    scope_ids = [item["scope_id"] for item in envelope["scope_assessments"]]
    assert scope_ids == ["HS0001", "HS0002"]
    assert all(scope_id.startswith("HS") for scope_id in scope_ids)
    assert result["scope_assessment_trace"]["raw_scope_assessments"][0]["scope_id"].startswith(
        "S"
    )


def test_same_s_response_remapped_using_execution_alias_map() -> None:
    llm_input_a = _llm_execution_inputs()
    input_b = copy.deepcopy(_assessment_input())
    input_b["heading_scopes"][0]["scope_id"] = "HS0099"
    input_b["heading_scopes"][1]["scope_id"] = "HS0007"
    llm_input_b = build_scope_aware_prompt_input(input_b, _runtime_context())

    s_response = _raw_response_for_llm_input(llm_input_a)
    assert llm_input_a.alias_to_scope_id != llm_input_b.alias_to_scope_id

    result_a = run_scope_assessment_api(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input_a.prompt_input_bundle,
        alias_to_scope_id=llm_input_a.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        llm_profile="deepseek_v4_flash",
        provider=_FakeProvider(json.dumps(s_response, ensure_ascii=False)),
    )
    result_b = run_scope_assessment_api(
        assessment_input=input_b,
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input_b.prompt_input_bundle,
        alias_to_scope_id=llm_input_b.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        llm_profile="deepseek_v4_flash",
        provider=_FakeProvider(json.dumps(s_response, ensure_ascii=False)),
    )

    ids_a = [item["scope_id"] for item in result_a["scope_assessments"]["scope_assessments"]]
    ids_b = [item["scope_id"] for item in result_b["scope_assessments"]["scope_assessments"]]
    assert ids_a == ["HS0001", "HS0002"]
    assert ids_b == ["HS0099", "HS0007"]


def test_mock_path_uses_s_namespace_and_restores_hs() -> None:
    llm_input = _llm_execution_inputs()
    result = run_scope_assessment_mock(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    envelope = result["scope_assessments"]
    scope_ids = [item["scope_id"] for item in envelope["scope_assessments"]]
    assert scope_ids == ["HS0001", "HS0002"]
    raw_ids = [item["scope_id"] for item in result["scope_assessment_trace"]["raw_scope_assessments"]]
    assert all(scope_id.startswith("S") for scope_id in raw_ids)


def test_unknown_s_alias_fail_fast_at_remap() -> None:
    llm_input = _llm_execution_inputs()
    canonical = validate_and_canonicalize_scope_assessment_response(
        raw_response=_raw_response_for_llm_input(llm_input),
        heading_scopes=llm_input.prompt_input_bundle["heading_scopes"],
    )
    tampered = copy.deepcopy(canonical)
    tampered[0] = dict(tampered[0])
    tampered[0]["scope_id"] = "S9999"
    with pytest.raises(ValueError, match="unknown model-local scope_id 'S9999'"):
        _remap_model_scope_ids_to_canonical(
            tampered,
            alias_to_scope_id=llm_input.alias_to_scope_id,
        )


def test_remap_preserves_assessment_fields_and_postprocess_evidence_lookup() -> None:
    llm_input = _llm_execution_inputs()
    result = run_scope_assessment_mock(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    first = result["scope_assessments"]["scope_assessments"][0]
    processing = result["scope_assessment_trace"]["scope_processing"][0]
    assert first["source_unit_ids"] == ["TU0001"]
    assert first["heading_path"] == ["安全性总结"]
    assert processing["source_unit_ids"] == ["TU0001"]
    assert processing["scope_evidence_view"]["candidate_text"] == "总体安全性可接受。"


def test_final_scope_assessments_contain_no_s_ids() -> None:
    llm_input = _llm_execution_inputs()
    result = run_scope_assessment_mock(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    for item in result["scope_assessments"]["scope_assessments"]:
        assert str(item["scope_id"]).startswith("HS")
        assert not str(item["scope_id"]).startswith("S")


def test_validator_missing_extra_duplicate_scope_behavior_with_s_namespace() -> None:
    llm_input = _llm_execution_inputs()
    prompt_scopes = llm_input.prompt_input_bundle["heading_scopes"]
    model_scope_ids = [scope["scope_id"] for scope in prompt_scopes]

    with pytest.raises(ScopeAssessmentContractError, match="missing_scope_id"):
        validate_and_canonicalize_scope_assessment_response(
            raw_response={"scope_assessments": []},
            heading_scopes=prompt_scopes,
        )

    with pytest.raises(ScopeAssessmentContractError, match="duplicate_scope_id"):
        validate_and_canonicalize_scope_assessment_response(
            raw_response={
                "scope_assessments": [
                    _raw_assessment(model_scope_ids[0]),
                    _raw_assessment(model_scope_ids[0]),
                ]
            },
            heading_scopes=prompt_scopes,
        )

    with pytest.raises(ScopeAssessmentContractError, match="missing_scope_id"):
        validate_and_canonicalize_scope_assessment_response(
            raw_response={
                "scope_assessments": [
                    _raw_assessment(model_scope_ids[0]),
                    _raw_assessment("S9999"),
                ]
            },
            heading_scopes=prompt_scopes,
        )


def test_compact_pipeline_execution_from_aggregate_units() -> None:
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
    result = run_scope_assessment_mock(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    assert result["scope_assessments"]["scope_assessments"][0]["scope_id"] == "HS0001"


def test_formal_assess_output_restores_artifact_order_after_semantic_reorder() -> None:
    scope_exec = _scope_task("HS0001", ["Executive Summary"], "exec evidence")
    scope_alpha = _scope_task("HS0002", ["Alpha Section"], "alpha evidence")
    scope_beta = _scope_task("HS0003", ["Beta Section"], "beta evidence")
    assessment_input, runtime_context = _assessment_input_with_scopes(
        [scope_exec, scope_alpha, scope_beta],
        llm_input_bundle_id="llm_input_scope_order_restore_three",
    )
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)

    artifact_order = [scope["scope_id"] for scope in assessment_input["heading_scopes"]]
    assert artifact_order == ["HS0001", "HS0002", "HS0003"]

    model_hs_order = [
        llm_input.alias_to_scope_id[scope["scope_id"]]
        for scope in llm_input.prompt_input_bundle["heading_scopes"]
    ]
    assert model_hs_order == ["HS0002", "HS0003", "HS0001"]

    result = run_scope_assessment_mock(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    formal_ids = [
        item["scope_id"] for item in result["scope_assessments"]["scope_assessments"]
    ]
    processing_ids = [
        item["scope_id"] for item in result["scope_assessment_trace"]["scope_processing"]
    ]
    assert formal_ids == artifact_order
    assert processing_ids == artifact_order
