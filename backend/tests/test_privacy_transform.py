from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from privacy.config import (
    PrivacyConfig,
    parse_detector_csv,
    validate_detector_name,
)
from privacy.mapping_store import MappingStore
from privacy.schemas import SensitiveEntityCandidate
from privacy.transform import apply_privacy_transform
from runtime.run_summaries import build_prepare_analysis_run_summary
from tests.clinical_program_fixtures import canonical_clinical_program_fields


class _StaticDetector:
    def __init__(self, candidates: list[SensitiveEntityCandidate]) -> None:
        self._candidates = candidates

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        return [
            c
            for c in self._candidates
            if text[c.start : c.end] == c.original_text
        ]


def _candidate(
    text: str,
    term: str,
    entity_type: str,
    *,
    canonical_id: str | None = None,
    predefined_token: str | None = None,
) -> SensitiveEntityCandidate:
    start = text.index(term)
    return SensitiveEntityCandidate(
        original_text=term,
        entity_type=entity_type,  # type: ignore[arg-type]
        start=start,
        end=start + len(term),
        source="mock",
        confidence=1.0,
        canonical_id=canonical_id,
        predefined_token=predefined_token,
    )


def _single_block_bundle(*, text: str, block_id: str = "C0001") -> dict:
    return {
        "doc_id": "doc_privacy_transform",
        "file_name": "sample.docx",
        "display_name": "sample",
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": "0.2.1"},
        "content_blocks": [
            {
                "block_id": block_id,
                "kind": "paragraph",
                "normalized_text": text,
                "loc": "BODY:P1",
                "sentences": [
                    {
                        "sentence_id": f"{block_id}:S001",
                        "normalized_text": text,
                    }
                ],
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def _registry_regex_config() -> PrivacyConfig:
    return PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": []},
            }
        }
    )


def test_privacy_config_default_empty_detectors() -> None:
    config = PrivacyConfig.default()
    assert config.transform_detectors("after_extract") == []
    assert config.transform_detectors("after_filter") == []
    assert config.privacy_enabled() is False


def test_parse_detector_csv() -> None:
    assert parse_detector_csv(None) == []
    assert parse_detector_csv("") == []
    assert parse_detector_csv("registry,regex") == ["registry", "regex"]


def test_privacy_config_from_cli() -> None:
    config = PrivacyConfig.from_cli(after_extract="registry,regex", after_filter="")
    assert config.transform_detectors("after_extract") == ["registry", "regex"]
    assert config.transform_detectors("after_filter") == []


def test_transforms_only_config() -> None:
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": []},
            }
        }
    )
    assert config.transform_detectors("after_extract") == ["registry", "regex"]


@pytest.mark.parametrize(
    "detectors",
    [
        ["registry", "regex"],
        ["uie"],
        ["registry", "regex", "uie"],
    ],
)
def test_after_extract_accepts_any_detector_combination(detectors: list[str]) -> None:
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": detectors},
                "after_filter": {"detectors": []},
            }
        }
    )
    assert config.transform_detectors("after_extract") == detectors


@pytest.mark.parametrize(
    "detectors",
    [
        ["registry", "regex"],
        ["uie"],
        ["registry", "regex", "uie"],
        [],
    ],
)
def test_after_filter_accepts_any_detector_combination(detectors: list[str]) -> None:
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": []},
                "after_filter": {"detectors": detectors},
            }
        }
    )
    assert config.transform_detectors("after_filter") == detectors


def test_empty_after_extract_detectors_identity_transform() -> None:
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": []},
                "after_filter": {"detectors": ["uie"]},
            }
        }
    )
    assert config.transform_detectors("after_extract") == []
    assert config.transform_detectors("after_filter") == ["uie"]

    bundle = _single_block_bundle(text="药物 VT8802 测试。")
    result = apply_privacy_transform(
        bundle,
        "after_extract",
        config,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    block = result.analysis_bundle["content_blocks"][0]
    assert block["analysis_text"] == block["normalized_text"]
    assert result.slot_applied is False


def test_apply_privacy_transform_after_extract_masks_sentences() -> None:
    text = "药物 VT8802 由申办方某某生物医药有限公司支持。"
    bundle = _single_block_bundle(text=text)
    config = _registry_regex_config()

    result = apply_privacy_transform(
        bundle,
        "after_extract",
        config,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )

    block = result.analysis_bundle["content_blocks"][0]
    assert "normalized_text" not in block
    assert block["analysis_text"] != text
    assert "VT8802" not in block["analysis_text"]
    assert result.slot_applied is True
    assert result.block_audit_surfaces
    audit_block = result.block_audit_surfaces[0]
    assert audit_block["normalized_text"] == text
    assert "span_map" not in audit_block
    assert result.analysis_bundle["privacy_enabled"] is True
    assert result.analysis_bundle["analysis_bundle_contract"] == "public_masked_v0.4"
    assert result.analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is True
    assert "privacy_stages" not in result.analysis_bundle
    assert "post_extract" not in result.analysis_bundle
    assert "pre_llm" not in result.analysis_bundle

    sentence = block["sentences"][0]
    assert sentence["sentence_id"] == "C0001:S001"
    assert "VT8802" not in sentence["analysis_text"]


def test_apply_privacy_transform_mapping_store_stable_across_calls() -> None:
    text = "药物 VT8802 由申办方某某生物医药有限公司支持。"
    bundle = _single_block_bundle(text=text)
    config = _registry_regex_config()
    store = MappingStore()

    first = apply_privacy_transform(
        bundle,
        "after_extract",
        config,
        mapping_store=store,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    second = apply_privacy_transform(
        bundle,
        "after_extract",
        config,
        mapping_store=store,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )

    assert first.analysis_bundle["content_blocks"][0]["analysis_text"] == (
        second.analysis_bundle["content_blocks"][0]["analysis_text"]
    )
    assert first.mask_result.mapping == second.mask_result.mapping


def test_empty_detector_list_identity_transform() -> None:
    text = "plain text without entities"
    bundle = _single_block_bundle(text=text)

    empty_config = PrivacyConfig.default()
    result = apply_privacy_transform(
        bundle,
        "after_extract",
        empty_config,
        language="zh",
    )
    block = result.analysis_bundle["content_blocks"][0]
    assert block["analysis_text"] == text
    assert "span_map" not in block
    sentence = block["sentences"][0]
    assert sentence["analysis_text"] == text
    assert "span_map" not in sentence
    assert result.analysis_bundle["privacy_enabled"] is False
    assert result.analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is False


def test_no_privacy_workflow_produces_analysis_bundle() -> None:
    bundle = _single_block_bundle(text="local llm path")
    config = PrivacyConfig.default()
    result = apply_privacy_transform(bundle, "after_extract", config, language="zh")
    assert "content_blocks" in result.analysis_bundle
    assert result.analysis_bundle["privacy_transforms"]["after_filter"]["detectors"] == []


def test_run_summary_flat_privacy_fields() -> None:
    bundle = _single_block_bundle(text="hello")
    config = _registry_regex_config()
    result = apply_privacy_transform(
        bundle,
        "after_extract",
        config,
        language="zh",
    )

    summary = build_prepare_analysis_run_summary(
        run_id="run_test",
        bundle_dict=bundle,
        language="zh",
        input_bundle=None,
        output_bundle_path=None,
        analysis_bundle_path=Path("analysis_bundle.json"),
        privacy_audit_path=Path("privacy_audit.json"),
        mapping_path=Path("mapping.json"),
        privacy_transform_applied=result.slot_applied,
        privacy_detectors_configured=config.transform_detectors("after_extract"),
        privacy_detectors_used=list(result.detectors_used),
        date_shift_offset_days=0,
        analysis_block_count=1,
    )

    assert summary["analysis_transform"] == "privacy_transform"
    assert summary["privacy_transform_applied"] is True
    assert summary["privacy_detectors_configured"] == ["registry", "regex"]
    assert summary["privacy_detectors_used"] == list(result.detectors_used)
    assert summary["audit_outputs"] == ["privacy_audit", "mapping"]
    assert summary["privacy_transform"] == {
        "slot": "after_extract",
        "settings": {"date_shift_offset_days": 0},
    }
    assert "privacy_transforms" not in summary
    assert "privacy_transform_slot" not in summary
    assert "detectors" not in summary
    assert "privacy_stages" not in summary
    assert summary["outputs"]["analysis_bundle"] == "analysis_bundle.json"


def test_run_summary_identity_workflow_same_schema() -> None:
    summary = build_prepare_analysis_run_summary(
        run_id="run_identity",
        bundle_dict={"doc_id": "d1", "source_type": "docx", "document_meta": {}},
        language="zh",
        input_bundle=None,
        output_bundle_path=None,
        analysis_bundle_path=Path("analysis_bundle.json"),
        privacy_transform_applied=False,
        analysis_block_count=1,
    )

    assert summary["analysis_transform"] == "identity"
    assert summary["privacy_transform_applied"] is False
    assert summary["privacy_detectors_configured"] == []
    assert summary["privacy_detectors_used"] == []
    assert summary["audit_outputs"] == []
    assert summary["outputs"] == {
        "analysis_bundle": "analysis_bundle.json",
        "block_manifest": "block_manifest.json",
    }
    assert "privacy_transform" not in summary
    assert "privacy_transforms" not in summary
    assert "privacy_profile_ref" not in summary
    assert "plugin" not in summary


def test_run_summary_plugin_components_only_for_used_detectors() -> None:
    from plugins.clinical_trial_doc.VERSION import CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS

    registry_regex = build_prepare_analysis_run_summary(
        run_id="run_rr",
        bundle_dict={"doc_id": "d1", "source_type": "docx", "document_meta": {}},
        language="zh",
        input_bundle=None,
        output_bundle_path=None,
        analysis_bundle_path=Path("analysis_bundle.json"),
        privacy_transform_applied=True,
        privacy_detectors_configured=["registry", "regex"],
        privacy_detectors_used=["registry", "regex"],
        privacy_profile_ref="clinical_trial_doc",
        session_segment="clinical_trial_doc",
        analysis_block_count=1,
        plugin_provenance={
            "name": "clinical_trial_doc",
            "version": "test",
            "components": {
                "privacy_profile": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "privacy_profile"
                ],
                "registry": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["registry"],
                "regex_rules_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "regex_rules_zh"
                ],
            },
        },
    )
    assert registry_regex["plugin"]["components"] == {
        "privacy_profile": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["privacy_profile"],
        "registry": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["registry"],
        "regex_rules_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["regex_rules_zh"],
    }
    assert "uie_schema_zh" not in registry_regex["plugin"]["components"]

    uie_only = build_prepare_analysis_run_summary(
        run_id="run_uie",
        bundle_dict={"doc_id": "d1", "source_type": "docx", "document_meta": {}},
        language="zh",
        input_bundle=None,
        output_bundle_path=None,
        analysis_bundle_path=Path("analysis_bundle.json"),
        privacy_transform_applied=True,
        privacy_detectors_configured=["uie"],
        privacy_detectors_used=["uie"],
        privacy_profile_ref="clinical_trial_doc",
        session_segment="clinical_trial_doc",
        analysis_block_count=1,
        plugin_provenance={
            "name": "clinical_trial_doc",
            "version": "test",
            "components": {
                "privacy_profile": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "privacy_profile"
                ],
                "uie_schema_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "uie_schema_zh"
                ],
            },
        },
    )
    assert uie_only["plugin"]["components"] == {
        "privacy_profile": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["privacy_profile"],
        "uie_schema_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["uie_schema_zh"],
    }


def test_dictionary_detector_rejected_in_config() -> None:
    with pytest.raises(ValueError, match="dictionary"):
        validate_detector_name("dictionary")

    with pytest.raises(ValueError, match="dictionary"):
        PrivacyConfig.from_dict(
            {
                "transforms": {
                    "after_extract": {"detectors": ["dictionary"]},
                    "after_filter": {"detectors": []},
                }
            }
        )


def test_after_filter_with_detectors_raises_not_implemented() -> None:
    bundle = _single_block_bundle(text="hello")
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": ["uie"]},
            }
        }
    )
    assert config.transform_detectors("after_filter") == ["uie"]

    with pytest.raises(NotImplementedError, match="span_map composition"):
        apply_privacy_transform(
            bundle,
            "after_filter",
            config,
            language="zh",
        )


def test_mask_bundle_uses_after_extract_detectors() -> None:
    text = "药物 VT8802 由申办方某某生物医药有限公司支持。"
    bundle = _single_block_bundle(text=text)
    config = _registry_regex_config()
    result = prepare_analysis_bundle(bundle, language="zh", privacy_config=config, **canonical_clinical_program_fields())
    block = result.analysis_bundle["content_blocks"][0]
    assert "VT8802" not in block["analysis_text"]
    assert "privacy_transforms" in result.analysis_bundle
    assert "privacy_stages" not in result.analysis_bundle


def test_static_detector_override_still_works() -> None:
    text = "患者张三参加研究。"
    bundle = _single_block_bundle(text=text)
    detector = _StaticDetector(
        [_candidate(text, "张三", "SUBJECT", predefined_token="Subject_001")]
    )
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry"]},
                "after_filter": {"detectors": []},
            }
        }
    )
    result = apply_privacy_transform(
        bundle,
        "after_extract",
        config,
        detector=detector,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    block = result.analysis_bundle["content_blocks"][0]
    assert "张三" not in block["analysis_text"]
    assert "Subject_001" in block["analysis_text"]
