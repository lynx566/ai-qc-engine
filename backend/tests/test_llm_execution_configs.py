"""Tests for neutral LLM execution configuration registry."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc import execution as execution_module
from application.clinical_trial_doc_consistency_qc import (
    projection_runtime as projection_runtime_module,
)
from application.clinical_trial_doc_consistency_qc.llm_binding_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.projection_runtime import (
    materialize_installed_projection_runtime_dependencies,
)
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
    LLMExecutionConfig,
    UnknownLLMExecutionConfigError,
    materialize_llm_provider,
    resolve_llm_execution_config,
)
from llm.providers.bailian import BailianQwenProvider
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_LLM_SLOT,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.dependencies import (
    OVERVIEW_SEMANTIC_LLM_SLOT,
)

_INSTALLED_FORMAL_FLOW_CONFIG_IDS = (
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
)


def test_consolidation_config_and_slot_use_stable_ec_policy() -> None:
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
    )
    config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
    )
    assert config.profile_id == "qwen3_7_plus_2026_05_26"
    assert config.thinking is None
    assert config.response_format is None
    assert config.seed == 1234


def test_unknown_execution_config_fails_closed() -> None:
    with pytest.raises(
        UnknownLLMExecutionConfigError, match="unknown llm execution config"
    ):
        resolve_llm_execution_config("missing_config")


def test_removed_generic_execution_config_ids_are_unknown() -> None:
    with pytest.raises(UnknownLLMExecutionConfigError):
        resolve_llm_execution_config("qwen_plus_no_thinking")
    with pytest.raises(UnknownLLMExecutionConfigError):
        resolve_llm_execution_config("qwen_plus_thinking")


def test_execution_config_references_profile_id_not_raw_model() -> None:
    config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )

    assert config.profile_id == "qwen3_7_plus_2026_05_26"
    assert not hasattr(config, "model")
    assert not hasattr(config, "provider")


def test_execution_config_field_contract() -> None:
    config = LLMExecutionConfig(
        config_id="custom_policy",
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=None,
        response_format="json_object",
        seed=42,
    )

    assert config.config_id == "custom_policy"
    assert config.profile_id == "qwen3_7_plus_2026_05_26"
    assert config.thinking is None
    assert config.response_format == "json_object"
    assert config.seed == 42


def test_execution_config_defaults_response_format_and_seed_to_none() -> None:
    config = LLMExecutionConfig(
        config_id="minimal_policy",
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=False,
    )

    assert config.response_format is None
    assert config.seed is None


def test_to_provenance_record_is_canonical_provider_neutral_representation() -> None:
    config = LLMExecutionConfig(
        config_id="custom_policy",
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=True,
        response_format="json_object",
        seed=7,
    )

    assert config.to_provenance_record() == {
        "config_id": "custom_policy",
        "profile_id": "qwen3_7_plus_2026_05_26",
        "thinking": True,
        "response_format": "json_object",
        "seed": 7,
    }


@pytest.mark.allow_external_provider_factory
def test_materialize_llm_provider_delegates_to_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = LLMExecutionConfig(
        config_id="forwarding_policy",
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=False,
        response_format="json_object",
        seed=99,
    )
    sentinel = object()
    captured: dict[str, object] = {}

    def _build_api_provider(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "llm.execution_configs.build_api_provider",
        _build_api_provider,
    )

    provider = materialize_llm_provider(config)

    assert provider is sentinel
    assert captured == {
        "llm_profile": "qwen3_7_plus_2026_05_26",
        "thinking": False,
        "response_format": "json_object",
        "seed": 99,
    }


@pytest.mark.allow_external_provider_factory
def test_materialize_llm_provider_forwards_none_provider_neutral_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )
    captured: dict[str, object] = {}

    def _build_api_provider(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "llm.execution_configs.build_api_provider",
        _build_api_provider,
    )

    materialize_llm_provider(config)

    assert captured == {
        "llm_profile": "qwen3_7_plus_2026_05_26",
        "thinking": None,
        "response_format": "json_object",
        "seed": 1234,
    }


@pytest.mark.allow_external_provider_factory
@pytest.mark.parametrize(
    "thinking",
    [None, False, True],
)
def test_materialize_preserves_tri_state_thinking_distinctly(
    monkeypatch: pytest.MonkeyPatch,
    thinking: bool | None,
) -> None:
    config = LLMExecutionConfig(
        config_id="tri_state_policy",
        profile_id="qwen3_7_plus_2026_05_26",
        thinking=thinking,
    )
    captured: dict[str, object] = {}

    def _build_api_provider(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "llm.execution_configs.build_api_provider",
        _build_api_provider,
    )

    materialize_llm_provider(config)

    assert "thinking" in captured
    assert captured["thinking"] is thinking


def test_installed_slot_bindings_use_six_independent_config_ids() -> None:
    bound_config_ids = {
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[OVERVIEW_SEMANTIC_LLM_SLOT],
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_LLM_SLOT
        ],
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT
        ],
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT
        ],
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT
        ],
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT
        ],
    }

    assert bound_config_ids == set(_INSTALLED_FORMAL_FLOW_CONFIG_IDS)
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[OVERVIEW_SEMANTIC_LLM_SLOT]
        == CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
    )


@pytest.mark.parametrize(
    ("config_id", "thinking", "response_format", "seed"),
    [
        (
            CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
            None,
            "json_object",
            1234,
        ),
        (
            CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID,
            None,
            "json_object",
            None,
        ),
        (
            CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
            None,
            None,
            1234,
        ),
        (
            CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
            True,
            None,
            1234,
        ),
        (
            CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
            None,
            None,
            1234,
        ),
    ],
)
def test_installed_configs_preserve_effective_execution_values(
    config_id: str,
    thinking: bool | None,
    response_format: str | None,
    seed: int | None,
) -> None:
    config = resolve_llm_execution_config(config_id)

    assert config.profile_id == "qwen3_7_plus_2026_05_26"
    assert config.thinking is thinking
    assert config.response_format == response_format
    assert config.seed == seed


def test_formal_slots_materialize_independently_from_distinct_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fop_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )
    esp_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID
    )
    assessment_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
    )
    assessment_second_pass_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
    )
    verification_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
    )
    consolidation_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
    )
    materialized: list[LLMExecutionConfig] = []

    def _record_materialize(config: LLMExecutionConfig) -> object:
        materialized.append(config)
        return object()

    monkeypatch.setattr(
        execution_module,
        "materialize_llm_provider",
        _record_materialize,
    )
    monkeypatch.setattr(
        projection_runtime_module,
        "materialize_llm_provider",
        _record_materialize,
    )

    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    materialize_installed_projection_runtime_dependencies(composition=composition)
    esp_deps = (
        execution_module._materialize_installed_evidence_source_preparation_execution_dependencies(
            composition=composition,
        )
    )
    comparison_deps = (
        execution_module.materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id="internal_dsur",
        )
    )

    assert materialized == [
        fop_config,
        esp_config,
        assessment_config,
        assessment_second_pass_config,
        verification_config,
        consolidation_config,
    ]
    assert {config.config_id for config in materialized} == set(
        _INSTALLED_FORMAL_FLOW_CONFIG_IDS
    )
    assert esp_deps.llm_execution_config == esp_config.to_provenance_record()
    assert (
        comparison_deps.assessment_llm_execution_config
        == assessment_config.to_provenance_record()
    )
    assert (
        comparison_deps.assessment_second_pass_llm_execution_config
        == assessment_second_pass_config.to_provenance_record()
    )
    assert (
        comparison_deps.verification_llm_execution_config
        == verification_config.to_provenance_record()
    )
    assert (
        comparison_deps.consolidation_llm_execution_config
        == consolidation_config.to_provenance_record()
    )
    assert (
        fop_config.config_id
        != esp_config.config_id
        != assessment_config.config_id
        != assessment_second_pass_config.config_id
        != verification_config.config_id
        != consolidation_config.config_id
    )


def _fake_openai_client(captured: dict[str, Any]) -> Any:
    class _FakeChoice:
        finish_reason = "stop"

        class message:
            content = "{}"

    class _FakeResponse:
        id = "fake-id"
        choices: ClassVar[list[_FakeChoice]] = [_FakeChoice()]
        usage = None
        system_fingerprint = None

    class _FakeCompletions:
        def create(self, **kwargs: Any) -> _FakeResponse:
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    return _FakeClient()


@pytest.mark.allow_external_provider_factory
@pytest.mark.parametrize(
    ("config_id", "expected_extra_body", "expected_seed"),
    [
        (CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID, None, 1234),
        (CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID, None, None),
        (CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID, None, 1234),
        (
            CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
            {"enable_thinking": True},
            1234,
        ),
        (CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID, None, 1234),
    ],
)
def test_installed_qwen_policies_preserve_request_behavior(
    monkeypatch: pytest.MonkeyPatch,
    config_id: str,
    expected_extra_body: dict[str, bool] | None,
    expected_seed: int | None,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_BASE_URL", "https://example.invalid/compatible-mode/v1")
    monkeypatch.setattr("llm.providers.factory.load_env", lambda: None)

    config = resolve_llm_execution_config(config_id)
    provider = materialize_llm_provider(config)
    assert isinstance(provider, BailianQwenProvider)
    provider._client = _fake_openai_client(captured)  # type: ignore[assignment]

    provider.generate([{"role": "user", "content": "hi"}])

    if expected_extra_body is None:
        assert "extra_body" not in captured
    else:
        assert captured["extra_body"] == expected_extra_body
    if expected_seed is None:
        assert "seed" not in captured
    else:
        assert captured["seed"] == expected_seed
    assert "response_format" not in captured
