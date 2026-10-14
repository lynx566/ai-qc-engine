"""Aggregate heading-scope assessment contract tests."""

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

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    ScopeAssessmentLlmInput,
    build_scope_aware_prompt_input,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import ASSESSMENT_INPUT_SCHEMA_VERSION
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENT_TRACE_SCHEMA_VERSION,
    SCOPE_ASSESSMENTS_SCHEMA_VERSION,
    ScopeAssessmentContractError,
    build_mock_scope_assessment,
    validate_and_canonicalize_scope_assessment_response,
    validate_scope_assessments_envelope,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    _FEW_SHOT_EXAMPLES,
    _SCHEMA_EXAMPLE,
    PROMPT_NAME,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_clinical_safety_aggregate_heading_scope_assessment_zh_messages,
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
RAW_FIELDS = {
    "scope_id",
    "product_context_role",
    "unit_form",
    "safety_role",
    "route_qc",
}
FORMAL_FIELDS = RAW_FIELDS | {
    "heading_path",
    "source_unit_ids",
    "post_llm_validation_flags",
}
RETIRED_FIELDS = {"study_context", "time_anchor", "population_context"}


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
        "llm_input_bundle_id": "llm_input_test_scope",
        "doc_id": "doc_scope_test",
        "file_hash": LINEAGE_FILE_HASH,
        "document_type": "dsur",
        "zone_key": "dsur_clinical_safety_zh",
        "route": "aggregate",
        "doc_meta": {
            "study_drug": "StudyDrug_001",
            "protocol_ids": ["Protocol_001"],
            "reporting_period": "2024-01-01/2024-12-31",
            "cutoff_date": "2024-12-31",
        },
        "instructions": "classify aggregate evidence",
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_test_scope"},
        "heading_scopes": _heading_scopes(),
    }


def _llm_input(assessment_input: dict[str, Any]) -> ScopeAssessmentLlmInput:
    return build_scope_aware_prompt_input(assessment_input, _runtime_context())


def _prompt_input_bundle(assessment_input: dict[str, Any]) -> dict[str, Any]:
    return _llm_input(assessment_input).prompt_input_bundle


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


def _runtime_context() -> dict[str, Any]:
    return {
        "runtime_context_id": "assessment_runtime_test_scope",
        "llm_input_bundle_id": "llm_input_test_scope",
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


def _raw_assessment(scope_id: str = "HS0001", **overrides: Any) -> dict[str, Any]:
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


def _raw_response() -> dict[str, Any]:
    return {
        "scope_assessments": [
            _raw_assessment("HS0001"),
            _raw_assessment(
                "HS0002",
                unit_form="case_like",
                route_qc={
                    "route_mismatch": True,
                    "suggested_route": "case",
                    "reason": "individual subject narrative",
                },
            ),
        ]
    }


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


def test_prompt_identity_and_minimal_output_contract() -> None:
    assert PROMPT_NAME == "clinical_safety_aggregate_heading_scope_assessment_zh"
    assert PROMPT_VERSION == "0.3.2"
    rendered = "\n".join(
        message["content"]
        for message in build_clinical_safety_aggregate_heading_scope_assessment_zh_messages(
            _prompt_input_bundle(_assessment_input())
        )
    )
    assert "scope_id" in SYSTEM_PROMPT
    assert "candidate_text" in SYSTEM_PROMPT
    assert "Current route: aggregate evidence" in rendered
    assert "StudyDrug_001" in rendered
    assert not any(field in rendered for field in RETIRED_FIELDS)
    assert "zone_key" not in rendered
    assert "protocol_ids" not in rendered
    assert "reporting_period" not in rendered
    assert "cutoff_date" not in rendered


def test_prompt_examples_use_only_new_raw_fields() -> None:
    assert not any(field in _SCHEMA_EXAMPLE for field in RETIRED_FIELDS)
    assert not any(field in _FEW_SHOT_EXAMPLES for field in RETIRED_FIELDS)
    for output_text in _FEW_SHOT_EXAMPLES.split("Output:\n")[1:]:
        payload = json.loads(output_text.split("\n\n", 1)[0])
        assert set(payload) == {"scope_assessments"}
        assert all(set(item) == RAW_FIELDS for item in payload["scope_assessments"])


def test_prompt_projection_contains_only_required_model_context() -> None:
    prompt_input = _prompt_input_bundle(_assessment_input())
    assert set(prompt_input) == {
        "llm_input_bundle_id",
        "doc_meta",
        "instructions",
        "heading_scopes",
    }
    assert prompt_input["doc_meta"] == {"study_drug": "StudyDrug_001"}
    assert set(prompt_input["heading_scopes"][0]) == {
        "scope_id",
        "heading_path",
        "candidate_text",
    }
    assert prompt_input["heading_scopes"][0]["scope_id"] == "S0001"


def test_new_raw_contract_canonicalizes_and_preserves_scope_order() -> None:
    response = _raw_response()
    response["scope_assessments"].reverse()
    canonical = validate_and_canonicalize_scope_assessment_response(
        raw_response=response,
        heading_scopes=_heading_scopes(),
    )
    assert [item["scope_id"] for item in canonical] == ["HS0001", "HS0002"]
    assert set(canonical[0]) == RAW_FIELDS | {"heading_path", "source_unit_ids"}
    assert canonical[0]["source_unit_ids"] == ["TU0001"]


@pytest.mark.parametrize("retired_field", sorted(RETIRED_FIELDS))
def test_old_zombie_keys_are_rejected(retired_field: str) -> None:
    entry = _raw_assessment()
    entry[retired_field] = None
    with pytest.raises(ScopeAssessmentContractError, match="extra_scope_assessment_field"):
        validate_and_canonicalize_scope_assessment_response(
            raw_response={"scope_assessments": [entry]},
            heading_scopes=[_heading_scopes()[0]],
        )


@pytest.mark.parametrize(
    ("mutator", "error"),
    [
        (lambda payload: payload.pop("unit_form"), "missing_scope_assessment_field"),
        (lambda payload: payload.update(unit_form="bad"), "invalid_enum"),
        (lambda payload: payload.update(safety_role="bad"), "invalid_enum"),
        (lambda payload: payload.update(product_context_role="bad"), "invalid_enum"),
        (
            lambda payload: payload["route_qc"].update(route_mismatch="false"),
            "invalid_route_qc_field",
        ),
        (
            lambda payload: payload["route_qc"].update(suggested_route="bad"),
            "invalid_enum",
        ),
        (
            lambda payload: payload["route_qc"].update(reason=[]),
            "invalid_route_qc_field",
        ),
    ],
)
def test_raw_field_validation(mutator: Any, error: str) -> None:
    entry = _raw_assessment()
    mutator(entry)
    with pytest.raises(ScopeAssessmentContractError, match=error):
        validate_and_canonicalize_scope_assessment_response(
            raw_response={"scope_assessments": [entry]},
            heading_scopes=[_heading_scopes()[0]],
        )


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"scope_assessments": []}, "missing_scope_id"),
        (
            {"scope_assessments": [_raw_assessment(), _raw_assessment()]},
            "duplicate_scope_id",
        ),
        (
            {"scope_assessments": [_raw_assessment(), _raw_assessment("HS9999")]},
            "missing_scope_id",
        ),
        ({"scope_assessments": [_raw_assessment()], "extra": True}, "extra_top_level_field"),
    ],
)
def test_scope_coverage_contract(response: dict[str, Any], error: str) -> None:
    with pytest.raises(ScopeAssessmentContractError, match=error):
        validate_and_canonicalize_scope_assessment_response(
            raw_response=response,
            heading_scopes=_heading_scopes(),
        )


def test_mock_contract_and_formal_schema_versions() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import (
        run_scope_assessment_mock,
    )

    assert set(build_mock_scope_assessment("S0001")) == RAW_FIELDS
    llm_input = _llm_input(_assessment_input())
    result = run_scope_assessment_mock(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    envelope = result["scope_assessments"]
    validate_scope_assessments_envelope(envelope)
    assert envelope["schema_version"] == SCOPE_ASSESSMENTS_SCHEMA_VERSION
    assert SCOPE_ASSESSMENT_TRACE_SCHEMA_VERSION == "0.4.0"
    assert result["scope_assessment_trace"]["schema_version"] == "0.4.0"
    assert all(set(item) == FORMAL_FIELDS for item in envelope["scope_assessments"])
    assert all(not (set(item) & RETIRED_FIELDS) for item in envelope["scope_assessments"])
    processing = result["scope_assessment_trace"]["scope_processing"]
    assert all("resolved_classification_fields" in item for item in processing)
    assert all("resolved_semantic_fields" not in item for item in processing)


def test_formal_schema_rejects_retired_and_missing_fields() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import (
        run_scope_assessment_mock,
    )

    llm_input = _llm_input(_assessment_input())
    result = run_scope_assessment_mock(
        assessment_input=_assessment_input(),
        assessment_runtime_context=_runtime_context(),
        prompt_input_bundle=llm_input.prompt_input_bundle,
        alias_to_scope_id=llm_input.alias_to_scope_id,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    envelope = result["scope_assessments"]
    with_retired = copy.deepcopy(envelope)
    with_retired["scope_assessments"][0]["time_anchor"] = None
    with pytest.raises(ValueError, match="invalid fields"):
        validate_scope_assessments_envelope(with_retired)
    missing_flags = copy.deepcopy(envelope)
    del missing_flags["scope_assessments"][0]["post_llm_validation_flags"]
    with pytest.raises(ValueError, match="invalid fields"):
        validate_scope_assessments_envelope(missing_flags)


def test_api_and_mock_converge_on_formal_shape() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess import (
        run_scope_assessment_api,
    )

    llm_input = _llm_input(_assessment_input())
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
    validate_scope_assessments_envelope(envelope)
    assert all(set(item) == FORMAL_FIELDS for item in envelope["scope_assessments"])
    assert envelope["scope_assessments"][1]["route_qc"]["suggested_route"] == "case"
    assert envelope["scope_assessments"][1]["route_qc"]["reason"]


def test_scope_assessments_artifact_does_not_import_tag_output_schema() -> None:
    import ast

    path = (
        BACKEND_ROOT
        / "artifacts"
        / "evidence_source_preparation"
        / "clinical_trial_doc"
        / "clinical_safety"
        / "aggregate_evidence"
        / "scope_assessments.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "core.tagging.schema.tag_output" not in imported
