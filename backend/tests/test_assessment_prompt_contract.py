"""Prompt contract and final model-visible message invariance tests (Slice C)."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    build_scope_aware_prompt_input,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.profile import (
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    PROMPT_VERSION,
    _FEW_SHOT_EXAMPLES,
    _SCHEMA_EXAMPLE,
    SYSTEM_PROMPT,
)
from tests.test_assessment_llm_input import (
    _assessment_input_with_scopes,
    _scope_task,
)


def _build_messages(assessment_input: dict, runtime_context: dict) -> list[dict[str, str]]:
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)
    return CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE.build_messages(
        llm_input.prompt_input_bundle
    )


def _messages_byte_payload(messages: list[dict[str, str]]) -> bytes:
    return json.dumps(messages, ensure_ascii=False).encode("utf-8")


def test_prompt_version_bumped_for_model_local_scope_ids() -> None:
    assert PROMPT_VERSION == "0.3.2"


def test_prompt_static_examples_use_s_namespace_only() -> None:
    assert "HS" not in _SCHEMA_EXAMPLE
    assert "HS" not in _FEW_SHOT_EXAMPLES
    assert re.search(r"S\d{4}", _SCHEMA_EXAMPLE)
    assert "model-local identifier" in SYSTEM_PROMPT


def test_final_messages_byte_identical_for_same_semantics_different_hs_and_order() -> None:
    scope_alpha = _scope_task("HS0001", ["Alpha"], "alpha evidence")
    scope_beta = _scope_task("HS0002", ["Beta"], "beta evidence")
    input_one, runtime_one = _assessment_input_with_scopes([scope_alpha, scope_beta])

    shuffled_beta = copy.deepcopy(scope_beta)
    shuffled_beta["scope_id"] = "HS0099"
    shuffled_alpha = copy.deepcopy(scope_alpha)
    shuffled_alpha["scope_id"] = "HS0007"
    input_two, runtime_two = _assessment_input_with_scopes(
        [shuffled_beta, shuffled_alpha],
        llm_input_bundle_id="llm_input_prompt_contract_reordered",
    )

    messages_one = _build_messages(input_one, runtime_one)
    messages_two = _build_messages(input_two, runtime_two)

    assert _messages_byte_payload(messages_one) == _messages_byte_payload(messages_two)


def test_model_visible_messages_contain_s_and_not_hs() -> None:
    scope_alpha = _scope_task("HS0001", ["Alpha"], "alpha evidence")
    scope_beta = _scope_task("HS0002", ["Beta"], "beta evidence")
    assessment_input, runtime_context = _assessment_input_with_scopes([scope_beta, scope_alpha])
    messages = _build_messages(assessment_input, runtime_context)
    rendered = json.dumps(messages, ensure_ascii=False)

    assert re.search(r"S\d{4}", rendered)
    assert "HS0001" not in rendered
    assert "HS0002" not in rendered
    assert "HS0099" not in rendered


def test_message_scope_order_follows_semantic_canonicalization_not_artifact_order() -> None:
    scope_alpha = _scope_task("HS0099", ["Alpha"], "alpha evidence")
    scope_beta = _scope_task("HS0007", ["Beta"], "beta evidence")
    assessment_input, runtime_context = _assessment_input_with_scopes([scope_beta, scope_alpha])
    messages = _build_messages(assessment_input, runtime_context)
    user_content = next(message["content"] for message in messages if message["role"] == "user")
    heading_scopes = json.loads(user_content.split("## Heading scopes\n", 1)[1].strip())

    assert [scope["heading_path"] for scope in heading_scopes] == [["Alpha"], ["Beta"]]
    assert [scope["scope_id"] for scope in heading_scopes] == ["S0001", "S0002"]
    assert [scope["scope_id"] for scope in assessment_input["heading_scopes"]] == [
        "HS0007",
        "HS0099",
    ]
