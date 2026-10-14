from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.filter_test_helpers import resolved_filter_job

from steps.filter import (
    extract_zones_from_bundle,
    to_debug_filter_payload,
    to_public_filter_payload,
)
from plugins.clinical_trial_doc.filter_profiles.csr.clinical_safety_zh import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.csr.overview_zh import (
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.clinical_safety_zh import (
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.dsur_overview_zh import (
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)


def _heading(
    block_id: str,
    text: str,
    *,
    level: int,
    stripped: str | None = None,
    doc_order_index: int | None = None,
) -> dict:
    block = {
        "block_id": block_id,
        "kind": "heading",
        "text": text,
        "meta": {
            "heading_level": level,
            "heading_text_stripped": stripped or text,
        },
    }
    if doc_order_index is not None:
        block["doc_order_index"] = doc_order_index
    return block


def _paragraph(
    block_id: str,
    text: str,
    *,
    doc_order_index: int | None = None,
) -> dict:
    block = {"block_id": block_id, "kind": "paragraph", "text": text}
    if doc_order_index is not None:
        block["doc_order_index"] = doc_order_index
    return block


def _table(
    block_id: str,
    text: str,
    *,
    doc_order_index: int,
    heading_path: list[str] | None = None,
) -> dict:
    return {
        "block_id": block_id,
        "kind": "table",
        "text": text,
        "analysis_text": text,
        "doc_order_index": doc_order_index,
        "heading_path": heading_path or [],
        "meta": {"row_count": 2, "column_count": 3},
    }


def _bundle(*blocks: dict, table_blocks: list[dict] | None = None) -> dict:
    return {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "content_blocks": list(blocks),
        "table_blocks": list(table_blocks or []),
    }


def test_ib_overview_profile_requires_level_one() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "1 摘要", level=1, stripped="摘要"),
            _paragraph("p1", "summary body"),
            _heading("h2", "5.2.1 摘要", level=3, stripped="摘要"),
            _paragraph("p2", "nested summary"),
        ),
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] == 1
    zone = result["matched_zones"][0]
    assert zone["zone_config_name"] == "ib_overview_zh"
    assert zone["match"]["matched_heading_level"] == 1


@pytest.mark.parametrize(
    ("overview_config", "h1_text", "h1_stripped", "subheading_text", "sub_stripped"),
    [
        (
            IB_OVERVIEW_FILTER_PROFILE_ZH,
            "1 摘要",
            "摘要",
            "2.1 不良事件概要",
            "不良事件概要",
        ),
        (
            IB_OVERVIEW_FILTER_PROFILE_ZH,
            "1 概要",
            "概要",
            "3 安全性摘要",
            "安全性摘要",
        ),
        (
            CSR_OVERVIEW_FILTER_PROFILE_ZH,
            "1 研究摘要",
            "研究摘要",
            "4 讨论和总体结论",
            "讨论和总体结论",
        ),
        (
            CSR_OVERVIEW_FILTER_PROFILE_ZH,
            "1 概要",
            "概要",
            "2 研究摘要",
            "研究摘要",
        ),
    ],
)
def test_overview_profile_skips_non_h1_headings(
    overview_config,
    h1_text: str,
    h1_stripped: str,
    subheading_text: str,
    sub_stripped: str,
) -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", h1_text, level=1, stripped=h1_stripped),
            _paragraph("p1", "top summary"),
            _heading("h2", subheading_text, level=2, stripped=sub_stripped),
            _paragraph("p2", "sub body"),
        ),
        resolved_filter_job(overview_config),
    )

    assert result["matched_zone_count"] == 1
    assert result["matched_zones"][0]["match"]["matched_heading_level"] == 1


def test_ib_clinical_safety_exclude_heading_terms() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "5.2.1 临床安全性", level=2, stripped="临床安全性"),
            _paragraph("p1", "clinical safety body"),
            _heading("h2", "5.1 非临床安全性", level=2, stripped="非临床安全性"),
            _paragraph("p2", "nonclinical body"),
            _heading("h3", "5.3 不良事件", level=2, stripped="不良事件"),
            _paragraph("p3", "ae body"),
        ),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    matched_block_ids = [
        zone["match"]["matched_heading_block_id"] for zone in result["matched_zones"]
    ]
    assert matched_block_ids == ["h1", "h3"]
    assert result["matched_zone_count"] == 2


def test_overview_profile_without_exclude_heading_terms_unchanged() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "1 摘要", level=1, stripped="摘要"),
            _paragraph("p1", "summary body"),
        ),
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] == 1
    assert result["matched_zones"][0]["zone_config_name"] == "ib_overview_zh"


def test_ib_clinical_safety_profile_matches_any_level() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "1 摘要", level=1, stripped="摘要"),
            _heading("h2", "5.2.1 临床安全性", level=3, stripped="临床安全性"),
            _paragraph("p1", "detail body"),
        ),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] == 1
    zone = result["matched_zones"][0]
    assert zone["match"]["matched_term"] in {"临床安全性", "安全性"}
    assert zone["match"]["matched_heading_level"] == 3
    assert zone["table_blocks"] == []


def test_clinical_safety_zone_includes_table_blocks_in_doc_order_range() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("C0006", "1 前言", level=1, stripped="前言", doc_order_index=5),
            _heading(
                "C0008",
                "6.1 临床安全性",
                level=2,
                stripped="临床安全性",
                doc_order_index=7,
            ),
            _paragraph("C0009", "body", doc_order_index=8),
            _paragraph("C0010", "表1 caption", doc_order_index=9),
            _paragraph("C0011", "注：note", doc_order_index=11),
            _heading("C0012", "6.2 PX-2471", level=2, doc_order_index=12),
            _paragraph("C0013", "after", doc_order_index=13),
            table_blocks=[
                _table("T0001", "table body", doc_order_index=10),
                _table("T0002", "outside zone", doc_order_index=13),
            ],
        ),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    detail_zone = next(
        zone
        for zone in result["matched_zones"]
        if zone["match"]["matched_heading_block_id"] == "C0008"
    )
    assert [block["block_id"] for block in detail_zone["blocks"]] == [
        "C0008",
        "C0009",
        "C0010",
        "C0011",
    ]
    assert [block["block_id"] for block in detail_zone["table_blocks"]] == ["T0001"]
    assert detail_zone["table_blocks"][0]["doc_order_index"] == 10
    zone_start = detail_zone["blocks"][0]["doc_order_index"]
    zone_end = 12
    assert zone_start == 7
    assert zone_start < 10 < zone_end


def test_dsur_clinical_safety_contains_matches_heading_variants() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading(
                "h1a",
                "安全性参考信息的变更",
                level=1,
                stripped="安全性参考信息的变更",
            ),
            _paragraph("p1", "section a"),
            _heading(
                "h1b",
                "重要风险分析",
                level=1,
                stripped="重要风险分析",
            ),
            _paragraph("p2", "section b"),
            _heading(
                "h1c",
                "严重不良反应分析",
                level=1,
                stripped="严重不良反应分析",
            ),
        ),
        resolved_filter_job(DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] == 3
    terms = [z["match"]["matched_term"] for z in result["matched_zones"]]
    assert terms[0] in {"安全性参考信息的变更", "安全性参考信息"}
    assert terms[1] == "重要风险"
    assert terms[2] in {"严重不良反应分析", "严重不良反应", "不良反应"}


def test_combined_ib_profiles_decouple_overview_and_detail() -> None:
    bundle = _bundle(
        _heading("h1", "1 摘要", level=1, stripped="摘要"),
        _paragraph("p1", "summary body"),
        _heading("h2", "2.1 不良事件概要", level=2, stripped="不良事件概要"),
        _paragraph("p2", "detail via ae term, not summary"),
        _heading("h3", "5.2.1 临床安全性", level=3, stripped="临床安全性"),
        _paragraph("p3", "detail body"),
    )
    overview = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )
    safety = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert overview["matched_zone_count"] == 1
    assert safety["matched_zone_count"] == 1
    summary_zone = overview["matched_zones"][0]
    detail_zone = safety["matched_zones"][0]
    assert summary_zone["zone_config_name"] == "ib_overview_zh"
    assert summary_zone["match"]["matched_heading_level"] == 1
    assert detail_zone["zone_config_name"] == "ib_clinical_safety_zh"
    assert detail_zone["match"]["matched_term"] == "不良事件"
    assert detail_zone["match"]["matched_heading_level"] == 2


def test_canonical_zone_match_has_singular_identity_only() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "1 摘要", level=1, stripped="摘要"),
            _paragraph("p1", "summary body"),
        ),
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )

    assert result["zone_config_name"] == "ib_overview_zh"
    assert result["resolved_filter_strategy_id"] == "heading_zone"
    assert "zone_config_names" not in result
    assert "resolved_filter_strategy_ids" not in result
    assert "zone_groups" not in result

    public = to_public_filter_payload(result)
    assert "zone_config_names" not in public
    assert "zone_groups" not in public

    debug = to_debug_filter_payload(result)
    assert "zone_groups" not in debug


def test_no_match_preserves_config_identity() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "无关章节", level=1, stripped="无关章节"),
            _paragraph("p1", "body"),
        ),
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] == 0
    assert result["matched_zones"] == []
    assert result["zone_config_name"] == "ib_overview_zh"
    assert result["zone_config_version"] == IB_OVERVIEW_FILTER_PROFILE_ZH.zone_config_version
    assert result["language"] == "zh"
    assert result["resolved_filter_strategy_id"] == "heading_zone"


def test_combined_csr_profiles_decouple_overview_and_detail() -> None:
    bundle = _bundle(
        _heading("h1", "讨论和总体结论", level=1, stripped="讨论和总体结论"),
        _paragraph("p1", "discussion"),
        _heading("h2", "安全性评价", level=2, stripped="安全性评价"),
        _paragraph("p2", "safety detail"),
    )
    overview = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(CSR_OVERVIEW_FILTER_PROFILE_ZH),
    )
    safety = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert overview["matched_zone_count"] == 1
    assert safety["matched_zone_count"] == 1
    assert overview["matched_zones"][0]["zone_config_name"] == "csr_overview_zh"
    assert safety["matched_zones"][0]["zone_config_name"] == "csr_clinical_safety_zh"
    assert safety["matched_zones"][0]["match"]["matched_term"] in {
        "安全性评价",
        "安全性",
    }


def test_dsur_overview_profile_excludes_literature_abstract_headings() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "执行概要", level=1, stripped="执行概要"),
            _paragraph("p1", "executive summary body"),
            _heading("h2", "文献/论文摘要", level=2, stripped="文献/论文摘要"),
            _paragraph("p2", "literature abstract body"),
            _heading("h3", "结论", level=1, stripped="结论"),
            _paragraph("p3", "conclusion body"),
        ),
        resolved_filter_job(DSUR_OVERVIEW_FILTER_PROFILE_ZH),
    )

    matched_block_ids = [
        zone["match"]["matched_heading_block_id"] for zone in result["matched_zones"]
    ]
    assert matched_block_ids == ["h1", "h3"]
    assert result["matched_zone_count"] == 2
    assert all(z["zone_config_name"] == "dsur_overview_zh" for z in result["matched_zones"])


def test_combined_dsur_profiles_decouple_overview_and_detail() -> None:
    bundle = _bundle(
        _heading("h1", "执行概要", level=1, stripped="执行概要"),
        _paragraph("p1", "executive summary"),
        _heading(
            "h2",
            "安全性参考信息的变更",
            level=1,
            stripped="安全性参考信息的变更",
        ),
        _paragraph("p2", "safety detail"),
    )
    overview = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(DSUR_OVERVIEW_FILTER_PROFILE_ZH),
    )
    safety = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert overview["matched_zone_count"] == 1
    assert safety["matched_zone_count"] == 1
    assert overview["matched_zones"][0]["zone_config_name"] == "dsur_overview_zh"
    assert safety["matched_zones"][0]["zone_config_name"] == "dsur_clinical_safety_zh"
    assert safety["matched_zones"][0]["match"]["matched_term"] in {
        "安全性参考信息的变更",
        "安全性参考信息",
    }
