from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.filter_test_helpers import resolved_filter_job

from tests.clinical_program_fixtures import canonical_clinical_program_fields
from steps.filter import extract_zones_from_bundle
from privacy.document_transform import run
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from privacy.config import PrivacyConfig


def _registry_regex_config() -> PrivacyConfig:
    return PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": []},
            }
        }
    )


def _minimal_bundle(*, text: str, block_id: str = "B1") -> dict:
    return {
        "doc_id": "doc_privacy_detectors",
        "file_name": "sample.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": block_id,
                "kind": "paragraph",
                "text": text,
                "meta": {"heading_stack": ["H0001"]},
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_registry_regex_transform_existing_behavior() -> None:
    text = "药物 VT-8802 由申办方某某生物医药有限公司支持。"
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
        apply_replacement=True,
    )
    block = result.masked_blocks[0]

    assert result.privacy_mode == "transform"
    assert block.mask_hits
    assert "VT-8802" not in block.masked_text
    assert "某某生物医药有限公司" not in block.masked_text


def test_default_config_identity_passthrough() -> None:
    text = "VT-8802治疗试验参与者001"
    bundle = _minimal_bundle(text=text)
    result = prepare_analysis_bundle(bundle, language="zh", **canonical_clinical_program_fields())

    analysis_block = result.analysis_bundle["content_blocks"][0]
    assert analysis_block["analysis_text"] == text
    assert "span_map" not in analysis_block
    assert analysis_block["block_id"] == "B1"
    assert analysis_block["meta"]["heading_stack"] == ["H0001"]
    assert "text" not in analysis_block

    assert result.mask_result is None
    assert result.analysis_bundle["privacy_enabled"] is False
    assert result.analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is False
    assert "privacy_preset" not in result.analysis_bundle
    assert "privacy_mode" not in result.analysis_bundle


def _extract_shaped_ib_bundle() -> dict:
    """Extract-stage bundle (``text`` fields) with IB clinical-safety headings."""
    return {
        "doc_id": "ib_safety_tag_integration_001",
        "file_name": "ib_safety_tag_integration_001.docx",
        "source_type": "docx",
        "document_meta": {
            "parser_type": "docx_handlers",
            "parser_version": "0.1.3",
            "bundle_schema_version": "0.1.2",
            "language": "zh",
        },
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": "h_safety",
                "kind": "heading",
                "text": "2 临床安全性",
                "meta": {
                    "heading_level": 1,
                    "heading_text_stripped": "临床安全性",
                },
            },
            {
                "block_id": "h_ae",
                "kind": "heading",
                "text": "2.1 不良事件汇总",
                "meta": {
                    "heading_level": 2,
                    "heading_text_stripped": "不良事件汇总",
                },
            },
            {
                "block_id": "p_safety",
                "kind": "paragraph",
                "text": "safety body",
            },
        ],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_default_config_filter_smoke() -> None:
    bundle_dict = _extract_shaped_ib_bundle()
    mask_result = prepare_analysis_bundle(bundle_dict, language="zh", **canonical_clinical_program_fields())

    zones = extract_zones_from_bundle(
        mask_result.analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert mask_result.analysis_bundle["privacy_enabled"] is False
    assert zones["matched_zone_count"] >= 1
    zone_blocks = zones["matched_zones"][0]["blocks"]
    assert zone_blocks[0]["analysis_text"] == "2 临床安全性"


def test_explicit_registry_regex_prepare_analysis_bundle() -> None:
    text = "药物 VT-8802 由申办方某某生物医药有限公司支持。"
    bundle = _minimal_bundle(text=text)
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    analysis_block = result.analysis_bundle["content_blocks"][0]
    assert "VT-8802" not in analysis_block["analysis_text"]
    assert result.analysis_bundle["privacy_enabled"] is True
    assert result.analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is True
