"""Regression guards for the Prepare Analysis privacy-off execution fast path."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest

BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW,
    validate_prepare_analysis_result,
)
from operations.prepare_analysis import (
    PrepareAnalysisConfigId,
    PrepareAnalysisRequestOptions,
    ResolvedPrepareAnalysisPlan,
)
from steps.prepare_analysis import prepare_analysis_bundle
from plugins.clinical_trial_doc.prepare_analysis import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
    ClinicalPreparePrivacyConfig,
)
from plugins.clinical_trial_doc.prepare_analysis import resolver as clinical_resolver
from privacy.detectors.composite import CompositeDetector
from privacy.mapping_store import MappingStore
from privacy.profile import PrivacyProfile, default_privacy_profile


def _bundle(text: str = "Protocol ACME-101 dated 2024-01-02.") -> dict[str, Any]:
    return {
        "doc_id": "fast_path_doc",
        "file_hash": "sha256:" + "a" * 64,
        "file_name": "fast_path.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": "0.2.1"},
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "normalized_text": text,
                "order": 1,
                "doc_order_index": 0,
                "source_ref": {
                    "source_type": "docx",
                    "locator_type": "paragraph",
                    "locator_payload": {"para_index": 0},
                },
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "normalized_text": text,
                    }
                ],
            }
        ],
        "table_blocks": [],
        "format_blocks": [],
    }


@dataclass(frozen=True)
class _FailingFactoryPlan:
    """Neutral resolved plan whose privacy execution factories must not be used."""

    prepare_analysis_config_id: PrepareAnalysisConfigId
    privacy_enabled: bool = False
    requested_detector_ids: tuple[str, ...] = ()
    effective_detector_ids: tuple[str, ...] = ()
    date_shift_enabled: bool = False
    date_shift_offset_days: int = 0

    @property
    def result_extension_values(self) -> Mapping[str, str]:
        return {}

    @property
    def provenance_descriptor(self) -> Mapping[str, Any]:
        return {}

    @property
    def privacy_provenance_stats(self) -> Mapping[str, str]:
        return {}

    def build_detector(self) -> CompositeDetector:
        raise AssertionError("privacy-off prepare must not invoke build_detector")

    def build_privacy_profile(self) -> PrivacyProfile:
        raise AssertionError(
            "privacy-off prepare must not invoke build_privacy_profile"
        )

    def new_mapping_store(self) -> MappingStore:
        raise AssertionError("privacy-off prepare must not invoke new_mapping_store")

    def validate_result_extension(self, payload: Mapping[str, Any]) -> None:
        del payload


@dataclass(frozen=True)
class _SpyPlan:
    """Neutral resolved plan that records masked-privacy factory invocations."""

    prepare_analysis_config_id: PrepareAnalysisConfigId
    privacy_enabled: bool
    requested_detector_ids: tuple[str, ...] = ()
    effective_detector_ids: tuple[str, ...] = ()
    date_shift_enabled: bool = False
    date_shift_offset_days: int = 0
    build_detector_calls: int = 0
    build_privacy_profile_calls: int = 0
    new_mapping_store_calls: int = 0

    @property
    def result_extension_values(self) -> Mapping[str, str]:
        return {}

    @property
    def provenance_descriptor(self) -> Mapping[str, Any]:
        return {}

    @property
    def privacy_provenance_stats(self) -> Mapping[str, str]:
        return {}

    def build_detector(self) -> CompositeDetector:
        object.__setattr__(self, "build_detector_calls", self.build_detector_calls + 1)
        return CompositeDetector(detectors=[])

    def build_privacy_profile(self) -> PrivacyProfile:
        object.__setattr__(
            self,
            "build_privacy_profile_calls",
            self.build_privacy_profile_calls + 1,
        )
        return default_privacy_profile()

    def new_mapping_store(self) -> MappingStore:
        object.__setattr__(
            self,
            "new_mapping_store_calls",
            self.new_mapping_store_calls + 1,
        )
        return MappingStore()

    def validate_result_extension(self, payload: Mapping[str, Any]) -> None:
        del payload


def _clinical_identity_plan() -> clinical_resolver.ClinicalResolvedPrepareAnalysisPlan:
    return CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain.resolve(
        config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
        request_options=PrepareAnalysisRequestOptions(
            ClinicalPreparePrivacyConfig.identity()
        ),
    )


def _clinical_enabled_plan(
    detectors: tuple[str, ...],
    *,
    program_id: str = "clinical_program_001",
) -> clinical_resolver.ClinicalResolvedPrepareAnalysisPlan:
    registry_enabled = "registry" in detectors
    return CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain.resolve(
        config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
        request_options=PrepareAnalysisRequestOptions(
            ClinicalPreparePrivacyConfig(
                enabled=True,
                registry_enabled=registry_enabled,
                regex_rule_set_ref=(
                    CLINICAL_REGEX_RULE_SET_ZH if "regex" in detectors else None
                ),
                uie_config_ref=(
                    CLINICAL_UIE_CONFIG_ZH if "uie" in detectors else None
                ),
                date_shift_enabled=False,
                clinical_program_id=program_id if registry_enabled else None,
            )
        ),
    )


def test_privacy_off_succeeds_without_privacy_execution_factories() -> None:
    plan = _FailingFactoryPlan(
        prepare_analysis_config_id=PrepareAnalysisConfigId("pacfg_no_privacy_exec"),
        privacy_enabled=False,
    )
    assert isinstance(plan, ResolvedPrepareAnalysisPlan)

    result = prepare_analysis_bundle(_bundle(), resolved_plan=plan)

    validate_prepare_analysis_result(result)
    assert result.mask_result is None
    assert result.analysis_bundle["privacy_enabled"] is False
    assert not result.block_audit_surfaces


def test_privacy_off_does_not_construct_privacy_audit_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import privacy.schemas as privacy_schemas

    def _forbidden_mask_result(*args: object, **kwargs: object) -> object:
        raise AssertionError("privacy-off prepare must not construct MaskResult")

    def _forbidden_masked_block(*args: object, **kwargs: object) -> object:
        raise AssertionError("privacy-off prepare must not construct MaskedBlock")

    monkeypatch.setattr(privacy_schemas, "MaskResult", _forbidden_mask_result)
    monkeypatch.setattr(privacy_schemas, "MaskedBlock", _forbidden_masked_block)

    result = prepare_analysis_bundle(
        _bundle(),
        resolved_plan=_FailingFactoryPlan(
            prepare_analysis_config_id=PrepareAnalysisConfigId(
                "pacfg_no_privacy_audit_objects"
            ),
            privacy_enabled=False,
        ),
    )

    validate_prepare_analysis_result(result)
    assert result.mask_result is None


def test_privacy_off_does_not_invoke_mask_bundle_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import privacy.document_transform as document_transform

    def _forbidden_noop(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "privacy-off prepare must not call privacy.document_transform._mask_bundle_noop"
        )

    monkeypatch.setattr(document_transform, "_mask_bundle_noop", _forbidden_noop)

    result = prepare_analysis_bundle(
        _bundle(),
        resolved_plan=_FailingFactoryPlan(
            prepare_analysis_config_id=PrepareAnalysisConfigId(
                "pacfg_no_mask_bundle_noop"
            ),
            privacy_enabled=False,
        ),
    )

    validate_prepare_analysis_result(result)
    assert result.mask_result is None
    assert result.analysis_bundle["privacy_enabled"] is False
    assert not result.block_audit_surfaces


def test_privacy_off_does_not_invoke_masked_privacy_factories() -> None:
    spy = _SpyPlan(
        prepare_analysis_config_id=PrepareAnalysisConfigId("pacfg_fast_path_off"),
        privacy_enabled=False,
    )
    assert isinstance(spy, ResolvedPrepareAnalysisPlan)

    result = prepare_analysis_bundle(_bundle(), resolved_plan=spy)

    assert spy.build_detector_calls == 0
    assert spy.build_privacy_profile_calls == 0
    assert spy.new_mapping_store_calls == 0
    validate_prepare_analysis_result(result)
    assert result.mask_result is None
    assert result.analysis_bundle["privacy_enabled"] is False
    assert not result.block_audit_surfaces


def test_privacy_enabled_invokes_masked_privacy_factories() -> None:
    spy = _SpyPlan(
        prepare_analysis_config_id=PrepareAnalysisConfigId("pacfg_fast_path_on"),
        privacy_enabled=True,
        requested_detector_ids=("regex",),
        effective_detector_ids=("regex",),
    )

    prepare_analysis_bundle(_bundle(), resolved_plan=spy)

    assert spy.build_detector_calls == 1
    assert spy.build_privacy_profile_calls == 1
    assert spy.new_mapping_store_calls == 1


def test_privacy_off_clinical_identity_matches_prior_identity_contract() -> None:
    bundle = _bundle()
    plan = _clinical_identity_plan()
    assert plan.privacy_enabled is False

    result = prepare_analysis_bundle(
        bundle,
        resolved_plan=plan,
        analysis_bundle_id="prepare_analysis_fast_path_ref",
    )

    block = result.analysis_bundle["content_blocks"][0]
    assert block["analysis_text"] == bundle["content_blocks"][0]["normalized_text"]
    assert block["normalized_text"] == bundle["content_blocks"][0]["normalized_text"]
    assert "span_map" not in block
    assert result.analysis_bundle["privacy_enabled"] is False
    assert result.analysis_bundle["analysis_bundle_contract"] == (
        ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW
    )
    assert result.analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is False
    assert result.analysis_bundle["analysis_bundle_id"] == (
        "prepare_analysis_fast_path_ref"
    )
    assert result.mask_result is None
    assert result.heading_projection is not None
    assert len(result.heading_projection.content) == 1
    assert not result.block_audit_surfaces


def test_privacy_enabled_clinical_regex_still_masks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _clinical_enabled_plan(("regex",))
    assert plan.privacy_enabled is True
    assert plan.detector_specs

    result = prepare_analysis_bundle(
        _bundle("Contact sponsor@example.com for details."),
        resolved_plan=plan,
        analysis_bundle_id="prepare_analysis_fast_path_masked",
    )

    block = result.analysis_bundle["content_blocks"][0]
    assert block["analysis_text"] != "Contact sponsor@example.com for details."
    assert result.mask_result is not None
    assert result.analysis_bundle["privacy_enabled"] is True
    assert result.analysis_bundle["analysis_bundle_contract"] == "public_masked_v0.4"
    assert result.block_audit_surfaces
