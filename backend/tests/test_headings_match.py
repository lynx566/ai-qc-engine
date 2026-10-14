from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.structure.headings import get_heading_text_for_match
from core.normalization.matching import match_text
from steps.filter import extract_zones_from_bundle
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.filter_test_helpers import resolved_filter_job


def test_match_text_contains_prefers_longest_normalized_term() -> None:
    matched, term = match_text(
        "七、数据概要和研究者指南",
        ("摘要", "概要", "数据概要和研究者指南"),
        "contains",
    )
    assert matched is True
    assert term == "数据概要和研究者指南"


def test_match_text_contains_tie_breaks_by_heading_terms_order() -> None:
    matched, term = match_text(
        "严重不良事件和重要不良事件",
        ("重要不良事件", "严重不良事件"),
        "contains",
    )
    assert matched is True
    assert term == "重要不良事件"


def test_match_text_exact_does_not_match_substring() -> None:
    matched, term = match_text(
        "七、数据概要和研究者指南",
        ("概要", "数据概要和研究者指南"),
        "exact",
    )
    assert matched is False
    assert term is None


def test_get_heading_text_for_match_extract_bundle() -> None:
    block = {
        "kind": "heading",
        "text": "六、临床安全性",
        "meta": {},
    }
    assert get_heading_text_for_match(block) == "六、临床安全性"


def test_get_heading_text_for_match_analysis_bundle() -> None:
    block = {
        "kind": "heading",
        "analysis_text": "六、临床安全性",
        "normalized_text": "六、临床安全性",
        "meta": {"heading_level": 1},
    }
    assert get_heading_text_for_match(block) == "六、临床安全性"


def test_get_heading_text_for_match_prefers_analysis_text_over_normalized() -> None:
    block = {
        "kind": "heading",
        "analysis_text": "6.1 StudyDrug_001（GenericName_001）",
        "normalized_text": "6.1 VT-8802（艾美妥珠单抗）",
        "meta": {"heading_level": 2},
    }
    assert get_heading_text_for_match(block) == "6.1 StudyDrug_001（GenericName_001）"


def test_get_heading_text_for_match_prefers_stripped_over_analysis_text() -> None:
    block = {
        "kind": "heading",
        "analysis_text": "<<SPONSOR>> 5.2.1 临床安全性",
        "normalized_text": "5.2.1 临床安全性",
        "meta": {
            "heading_level": 3,
            "heading_text_stripped": "临床安全性",
        },
    }
    assert get_heading_text_for_match(block) == "临床安全性"


def test_filter_ib_clinical_safety_matches_analysis_bundle_fixture() -> None:
    bundle = {
        "analysis_bundle_id": "prepare_analysis_heading_match_test",
        "doc_id": "doc_heading_match_test",
        "file_hash": (
            "sha256:0123456789abcdef0123456789abcdef"
            "0123456789abcdef0123456789abcdef"
        ),
        "file_name": "minimal-ib.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "heading",
                "order": 1,
                "analysis_text": "六、研究结果",
                "normalized_text": "六、研究结果",
                "heading_path": [],
                "meta": {"heading_level": 1},
            },
            {
                "block_id": "C0002",
                "kind": "heading",
                "order": 2,
                "analysis_text": "6.1 临床安全性",
                "normalized_text": "6.1 临床安全性",
                "heading_path": ["六、研究结果"],
                "meta": {"heading_level": 2},
            },
            {
                "block_id": "C0003",
                "kind": "paragraph",
                "order": 3,
                "analysis_text": "本节汇总不良事件。",
                "normalized_text": "本节汇总不良事件。",
                "heading_path": ["六、研究结果", "6.1 临床安全性"],
                "meta": {},
            },
        ],
        "table_blocks": [],
        "front_matter_blocks": [],
        "format_blocks": [],
    }
    result = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] > 0
    anchor = result["matched_zones"][0]
    assert anchor["match"]["matched_term"] in "临床安全性"
    assert anchor["match"]["matched_heading_block_id"] == "C0002"
    assert "临床安全性" in anchor["match"]["matched_heading_text"]
