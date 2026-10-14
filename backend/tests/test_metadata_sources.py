from __future__ import annotations

import json
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.metadata.metadata_sources import build_metadata_sources
from core.metadata.rule_engine import (
    detect_doc_type_from_sources,
    extract_metadata,
    extract_metadata_from_analysis_bundle,
)
from core.metadata.schemas import (
    DocTypeRule,
    MetadataContextConfig,
    MetadataProfile,
    MetadataSource,
)
from steps.doc_meta import build_doc_meta_payloads
from plugins.clinical_trial_doc.doc_meta.profile_zh import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
)
from application.clinical_trial_doc_consistency_qc.doc_meta_installation import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
    build_clinical_trial_doc_meta_summary,
)

RAW_FILE = "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15.docx"
RAW_DISPLAY = "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15"
RAW_PATH = r"D:\client\uploads\handbook.docx"
MASKED_FILE = "Record_001 研究者手册 V1.0 2024.03.15.docx"
MASKED_DISPLAY = "Record_001 研究者手册 V1.0 2024.03.15"
LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _masked_bundle_for_sources() -> dict:
    return {
        "doc_id": "doc_sources_test",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": MASKED_FILE,
        "display_name": MASKED_DISPLAY,
        "source_type": "docx",
        "stage": "prepare_analysis",
        "document_meta": {"source_path": None, "language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "text": "研究者手册（Investigator's Brochure）",
            },
            {
                "block_id": "C0002",
                "kind": "heading",
                "order": 2,
                "text": "六、临床安全性",
                "meta": {"heading_level": 1, "heading_text_stripped": "临床安全性"},
            },
            {
                "block_id": "C0003",
                "kind": "paragraph",
                "order": 3,
                "text": "试验药物：StudyDrug_001",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_build_metadata_sources_types() -> None:
    sources = build_metadata_sources(
        _masked_bundle_for_sources(), context_block_count=20
    )
    types = {s.source_type for s in sources}
    assert types == {
        "file_name",
        "display_name",
        "title_block",
        "heading",
        "early_block",
    }
    title = next(s for s in sources if s.source_type == "title_block")
    assert title.block_id == "C0001"
    heading = next(s for s in sources if s.source_type == "heading")
    assert heading.block_id == "C0002"
    early = next(s for s in sources if s.source_type == "early_block")
    assert early.block_id == "C0003"


def test_doc_type_csr_from_file_name_unrestricted_rule() -> None:
    csr_text = (
        "StudyDrug_001联合BackgroundDrug_001治疗Indication_001患者"
        "安全性和有效性研究报告 2024.04.15.docx"
    )
    profile = replace(
        CLINICAL_TRIAL_DOC_META_PROFILE,
        doc_type_rules=(
            DocTypeRule(
                doc_type="CSR",
                pattern=r"(?:安全性|有效性).{0,50}研究报告",
                flags=re.IGNORECASE,
            ),
        ),
    )
    sources = [
        MetadataSource(
            source_id="doc:file_name",
            source_type="file_name",
            text=csr_text,
        )
    ]
    doc_type, warnings = detect_doc_type_from_sources(sources, profile)
    assert doc_type.value == "CSR"
    assert doc_type.evidence[0].source_type == "file_name"
    assert doc_type.evidence[0].source_text == csr_text
    assert warnings == []


def test_doc_type_file_name_only_rule_skips_context_sources() -> None:
    profile = replace(
        CLINICAL_TRIAL_DOC_META_PROFILE,
        doc_type_rules=(
            DocTypeRule(
                doc_type="CSR",
                pattern=r"csr_final",
                flags=re.IGNORECASE,
                source="file_name",
            ),
            DocTypeRule(
                doc_type="IB",
                pattern=r"研究者手册",
                flags=re.IGNORECASE,
            ),
        ),
    )
    sources = [
        MetadataSource(
            source_id="doc:title",
            source_type="title_block",
            text="研究者手册（Investigator's Brochure）",
            block_id="C0001",
        ),
        MetadataSource(
            source_id="doc:file_name",
            source_type="file_name",
            text="csr_final_report.docx",
        ),
    ]
    doc_type, _ = detect_doc_type_from_sources(sources, profile)
    assert doc_type.value == "CSR"
    assert doc_type.evidence[0].source_type == "file_name"


def test_doc_type_priority_file_name_before_title() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["file_name"] = "csr_final_report.docx"
    sources = build_metadata_sources(bundle, context_block_count=20)
    profile = replace(
        CLINICAL_TRIAL_DOC_META_PROFILE,
        context=MetadataContextConfig(
            strategy="metadata_sources_v0_1",
            default_block_count=20,
            doc_type_source_priority=(
                "file_name",
                "title_block",
                "heading",
                "early_block",
            ),
        ),
    )
    doc_type, _ = detect_doc_type_from_sources(sources, profile)
    assert doc_type.value == "CSR"
    assert doc_type.evidence[0].source_type == "file_name"
    assert doc_type.evidence[0].priority_rank == 1


def test_doc_type_priority_title_before_file_name() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["file_name"] = "csr_final_report.docx"
    sources = build_metadata_sources(bundle, context_block_count=20)
    profile = replace(
        CLINICAL_TRIAL_DOC_META_PROFILE,
        context=MetadataContextConfig(
            strategy="metadata_sources_v0_1",
            default_block_count=20,
            doc_type_source_priority=(
                "title_block",
                "file_name",
                "heading",
                "early_block",
            ),
        ),
    )
    doc_type, _ = detect_doc_type_from_sources(sources, profile)
    assert doc_type.value == "IB"
    assert doc_type.evidence[0].source_type == "title_block"
    assert doc_type.evidence[0].block_id == "C0001"
    assert doc_type.evidence[0].priority_rank == 1
    assert doc_type.evidence[0].matched_rule


def test_clinical_meta_provenance_and_legacy_fields() -> None:
    bundle = _masked_bundle_for_sources()
    payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
        doc_meta_bundle_id="doc_meta_test",
        build_summary=build_clinical_trial_doc_meta_summary,
    )
    meta = payloads.doc_meta_bundle
    assert meta["context_strategy"] == "metadata_sources_v0_1"
    study_drug = meta["fields"]["study_drug"]
    assert study_drug["value"] == "StudyDrug_001"
    assert study_drug["source_block_ids"] == ["C0003"]
    assert study_drug["evidence"][0]["source_type"] == "early_block"
    assert study_drug["evidence"][0]["matched_rule"]

    preview = payloads.document_context_preview
    assert preview["strategy"] == "metadata_sources_v0_1"
    assert preview["sources"]
    assert preview["blocks"]


def test_document_date_prefers_report_date_over_trial_start_in_blocks() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["content_blocks"] = [
        {
            "block_id": "C0001",
            "kind": "paragraph",
            "order": 1,
            "text": "试验起始日期：2021.12.16",
        },
        {
            "block_id": "C0002",
            "kind": "paragraph",
            "order": 2,
            "text": "研究完成日期：2023.10.02",
        },
        {
            "block_id": "C0003",
            "kind": "paragraph",
            "order": 3,
            "text": "报告日期：2024.04.15",
        },
    ]
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="doc_dates",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    document_date = result.fields["document_date"]
    assert document_date.value == "2024.04.15"
    assert document_date.evidence[0].source_text == "报告日期：2024.04.15"


def test_cutoff_date_not_from_file_name_date() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["file_name"] = "StudyDrug_001_数据截至2024年3月15日.docx"
    bundle["display_name"] = "StudyDrug_001_数据截至2024年3月15日"
    bundle["content_blocks"] = [
        {
            "block_id": "C0001",
            "kind": "paragraph",
            "order": 1,
            "text": "研究者手册",
        },
    ]
    payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
        doc_meta_bundle_id="doc_meta_test",
        build_summary=build_clinical_trial_doc_meta_summary,
    )
    cutoff = payloads.doc_meta_bundle["fields"].get("cutoff_date", {})
    assert not cutoff.get("value")


def test_field_regression_from_early_blocks() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["content_blocks"].extend(
        [
            {
                "block_id": "C0004",
                "kind": "paragraph",
                "order": 4,
                "text": "版本号：V1.0",
            },
            {
                "block_id": "C0005",
                "kind": "paragraph",
                "order": 5,
                "text": "申办方：Sponsor_001",
            },
        ]
    )
    result, _sources = extract_metadata_from_analysis_bundle(
        doc_id="doc_reg",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    assert result.fields["study_drug"].value == "StudyDrug_001"
    assert result.fields["sponsor"].value == "Sponsor_001"
    assert result.fields["version"].value == "V1.0"


def test_privacy_no_raw_in_doc_meta_artifacts() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["document_meta"] = {"source_path": None}
    payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
        doc_meta_bundle_id="doc_meta_test",
        build_summary=build_clinical_trial_doc_meta_summary,
    )
    blob = json.dumps(payloads.doc_meta_bundle, ensure_ascii=False)
    blob += json.dumps(payloads.document_context_preview, ensure_ascii=False)
    assert RAW_PATH not in blob
    assert RAW_FILE not in blob
    assert "D:/client" not in blob
    assert "艾美妥珠单抗" not in blob


def test_display_name_in_sources_not_legacy_param() -> None:
    bundle = _masked_bundle_for_sources()
    sources = build_metadata_sources(bundle, context_block_count=20)
    assert any(s.source_type == "display_name" for s in sources)
    profile = replace(
        CLINICAL_TRIAL_DOC_META_PROFILE,
        context=MetadataContextConfig(
            strategy="metadata_sources_v0_1",
            default_block_count=20,
            doc_type_source_priority=("display_name",),
        ),
    )
    only_display = [
        MetadataSource(
            source_id="d:display_name",
            source_type="display_name",
            text=MASKED_DISPLAY,
        )
    ]
    doc_type, _ = detect_doc_type_from_sources(only_display, profile)
    assert doc_type.value == "IB"
    assert doc_type.evidence[0].source_type == "display_name"


def _dsur_bundle_for_meta(
    *,
    file_name: str,
    display_name: str,
    content_blocks: list[dict] | None = None,
) -> dict:
    return {
        "doc_id": "dsur_meta_test",
        "file_name": file_name,
        "display_name": display_name,
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": content_blocks or [],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


@pytest.mark.parametrize(
    ("file_name", "display_name"),
    [
        (
            "StudyDrug_001 研发期间安全性更新报告#2.docx",
            "GenericName_001 StudyDrug_001 研发期间安全性更新报告#2",
        ),
        (
            "GenericName_001 StudyDrug_001 研发期间安全性更新报告#2.docx",
            "GenericName_001 StudyDrug_001 研发期间安全性更新报告#2",
        ),
    ],
)
def test_dsur_study_drug_fallback_from_title_or_file(
    file_name: str,
    display_name: str,
) -> None:
    bundle = _dsur_bundle_for_meta(file_name=file_name, display_name=display_name)
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="dsur_drug_fallback",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    study_drug = result.fields["study_drug"]
    assert study_drug.value == "StudyDrug_001"
    assert study_drug.evidence[0].matched_rule
    assert "field:study_drug:" in study_drug.evidence[0].matched_rule
    assert study_drug.evidence[0].source_type in {
        "file_name",
        "display_name",
        "title_block",
        "early_block",
    }
    assert result.doc_type.value == "DSUR"
    assert "required field not found: study_drug" not in result.warnings


def test_dsur_reporting_period_bounded_capture() -> None:
    bundle = _dsur_bundle_for_meta(
        file_name="dsur_reporting_period.docx",
        display_name="dsur_reporting_period",
        content_blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "text": (
                    "涵盖周期：2022年12月18日-2023年12月17日 "
                    "报告日期：2024年3月8日 申办者：Sponsor_001"
                ),
            },
        ],
    )
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="dsur_reporting_period",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    reporting_period = result.fields["reporting_period"]
    assert reporting_period.value == "2022年12月18日-2023年12月17日"
    assert reporting_period.evidence[0].source_type == "title_block"
    assert reporting_period.evidence[0].block_id == "C0001"


def test_cutoff_date_from_narrative_jizhi() -> None:
    bundle = _masked_bundle_for_sources()
    bundle["content_blocks"] = [
        {
            "block_id": "C0001",
            "kind": "paragraph",
            "order": 1,
            "text": "研究者手册",
        },
        {
            "block_id": "C0002",
            "kind": "paragraph",
            "order": 2,
            "text": (
                "基于截至2023年12月17日的累计安全性资料，感染性肺炎及药物诱导的"
                "肝损伤将被视为StudyDrug_001的重要已识别风险。"
            ),
        },
    ]
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="cutoff_narrative",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    cutoff = result.fields["cutoff_date"]
    assert cutoff.value == "2023年12月17日"
    assert cutoff.evidence[0].source_type == "early_block"
    assert cutoff.evidence[0].block_id == "C0002"


def test_cutoff_date_from_csr_database_lock() -> None:
    bundle = {
        "doc_id": "csr_lock_test",
        "file_name": "csr_final_report.docx",
        "display_name": "csr_final_report",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "text": "临床研究报告",
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "order": 2,
                "text": "数据库锁定日期：2023.05.17",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="csr_lock_test",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    cutoff = result.fields["cutoff_date"]
    assert cutoff.value == "2023.05.17"
    assert cutoff.evidence[0].source_type == "early_block"
    assert cutoff.evidence[0].block_id == "C0002"
    database_lock = result.fields["database_lock_date"]
    assert database_lock.value == "2023.05.17"
    assert database_lock.evidence[0].block_id == "C0002"
    assert result.doc_type.value == "CSR"


def test_csr_title_page_metadata_extraction() -> None:
    bundle = {
        "doc_id": "csr_title_page_test",
        "file_name": "Protocol_001 临床研究报告 2023.07.15.docx",
        "display_name": "Protocol_001 临床研究报告 2023.07.15",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "text": "临床研究报告",
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "order": 2,
                "text": (
                    "研究标题：一项评价StudyDrug_001单药治疗Indication_001"
                    "试验参与者安全性的开放标签I期研究"
                ),
            },
            {
                "block_id": "C0003",
                "kind": "paragraph",
                "order": 3,
                "text": "药物类别：单克隆抗体",
            },
            {
                "block_id": "C0004",
                "kind": "paragraph",
                "order": 4,
                "text": "适应症：Indication_001",
            },
            {
                "block_id": "C0005",
                "kind": "paragraph",
                "order": 5,
                "text": "研究分期：I期",
            },
            {
                "block_id": "C0006",
                "kind": "paragraph",
                "order": 6,
                "text": "试验起始日期：2021.12.16",
            },
            {
                "block_id": "C0007",
                "kind": "paragraph",
                "order": 7,
                "text": "首例试验参与者给药日期：2021.12.28",
            },
            {
                "block_id": "C0008",
                "kind": "paragraph",
                "order": 8,
                "text": "剂量探索完成日期：2022.06.30",
            },
            {
                "block_id": "C0009",
                "kind": "paragraph",
                "order": 9,
                "text": "研究完成日期：2023.03.20",
            },
            {
                "block_id": "C0010",
                "kind": "paragraph",
                "order": 10,
                "text": "数据库锁定日期：2023.04.30",
            },
            {
                "block_id": "C0011",
                "kind": "paragraph",
                "order": 11,
                "text": "报告日期：2023.07.15",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="csr_title_page_test",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    fields = result.fields
    assert result.doc_type.value == "CSR"
    assert fields["study_title"].value.startswith("一项评价StudyDrug_001")
    assert fields["drug_modality"].value == "单克隆抗体"
    assert fields["indication"].value == "Indication_001"
    assert fields["study_phase"].value == "I期"
    assert fields["study_start_date"].value == "2021.12.16"
    assert fields["first_subject_dosed_date"].value == "2021.12.28"
    assert fields["dose_escalation_completion_date"].value == "2022.06.30"
    assert fields["study_completion_date"].value == "2023.03.20"
    assert fields["database_lock_date"].value == "2023.04.30"
    assert fields["report_date"].value == "2023.07.15"
    assert fields["document_date"].value == "2023.07.15"
    assert fields["cutoff_date"].value == "2023.04.30"
