from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.doc_meta import metadata_result_to_doc_meta_bundle
from core.metadata.rule_engine import extract_metadata_from_analysis_bundle
from plugins.clinical_trial_doc.doc_meta.summary import (
    build_clinical_trial_doc_meta_summary,
)
from plugins.clinical_trial_doc.doc_meta.profile_zh import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
)


def _clinical_doc_meta_bundle(result, *, doc_meta_bundle_id: str = "doc_meta_test") -> dict:
    base = result.to_dict()
    summary = build_clinical_trial_doc_meta_summary(base)
    return metadata_result_to_doc_meta_bundle(
        result,
        doc_meta_bundle_id=doc_meta_bundle_id,
        summary=summary,
    )


def test_csr_title_page_summary_dates_normalized() -> None:
    bundle = {
        "doc_id": "csr_title_page_test",
        "file_name": "Protocol_001 临床研究报告 2023.07.15.docx",
        "display_name": "Protocol_001 临床研究报告 2023.07.15",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
            {"block_id": "C0001", "kind": "paragraph", "order": 1, "text": "临床研究报告"},
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
    doc_meta = _clinical_doc_meta_bundle(result)
    fields = doc_meta["fields"]
    summary = doc_meta["summary"]

    assert fields["study_start_date"]["value"] == "2021.12.16"
    assert summary["study_start_date"] == "2021-12-16"
    assert fields["first_subject_dosed_date"]["value"] == "2021.12.28"
    assert summary["first_subject_dosed_date"] == "2021-12-28"
    assert fields["dose_escalation_completion_date"]["value"] == "2022.06.30"
    assert summary["dose_escalation_completion_date"] == "2022-06-30"
    assert fields["study_completion_date"]["value"] == "2023.03.20"
    assert summary["study_completion_date"] == "2023-03-20"
    assert fields["database_lock_date"]["value"] == "2023.04.30"
    assert summary["database_lock_date"] == "2023-04-30"
    assert fields["report_date"]["value"] == "2023.07.15"
    assert summary["report_date"] == "2023-07-15"
    assert fields["document_date"]["value"] == "2023.07.15"
    assert summary["document_date"] == "2023-07-15"
    assert fields["cutoff_date"]["value"] == "2023.04.30"
    assert summary["cutoff_date"] == "2023-04-30"


def test_dsur_reporting_period_summary_normalized() -> None:
    bundle = {
        "doc_id": "dsur_reporting_period",
        "file_name": "dsur_reporting_period.docx",
        "display_name": "dsur_reporting_period",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
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
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result, _ = extract_metadata_from_analysis_bundle(
        doc_id="dsur_reporting_period",
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
    )
    doc_meta = _clinical_doc_meta_bundle(result)

    assert doc_meta["fields"]["reporting_period"]["value"] == "2022年12月18日-2023年12月17日"
    assert doc_meta["summary"]["reporting_period"] == "2022-12-18/2023-12-17"
