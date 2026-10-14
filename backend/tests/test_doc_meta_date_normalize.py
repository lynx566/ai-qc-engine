from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.metadata.date_normalize import (
    normalize_date_range_value,
    normalize_date_value,
)
from artifacts.doc_meta import metadata_result_to_doc_meta_bundle
from core.metadata.schemas import MetadataField, MetadataResult
from plugins.clinical_trial_doc.doc_meta.summary import (
    CLINICAL_TRIAL_DOC_META_SUMMARY_FIELD_NAMES,
    build_clinical_trial_doc_meta_summary,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2022.01.02", "2022-01-02"),
        ("2022.1.2", "2022-01-02"),
        ("2022/01/02", "2022-01-02"),
        ("2022-1-2", "2022-01-02"),
        ("2022年1月2日", "2022-01-02"),
        ("2022年01月02日", "2022-01-02"),
        ("Date_001", "Date_001"),
        ("not-a-date", "not-a-date"),
        ("2022-13-40", "2022-13-40"),
    ],
)
def test_normalize_date_value(raw: str, expected: str) -> None:
    assert normalize_date_value(raw) == expected


def test_normalize_date_value_none() -> None:
    assert normalize_date_value(None) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2022.12.01-2023.11.30", "2022-12-01/2023-11-30"),
        ("2022/12/01-2023/11/30", "2022-12-01/2023-11-30"),
        ("2022-12-01-2023-11-30", "2022-12-01/2023-11-30"),
        ("2022年12月1日-2023年11月30日", "2022-12-01/2023-11-30"),
        ("Date_001-Date_002", "Date_001/Date_002"),
        ("2022-12-01/2023-11-30", "2022-12-01/2023-11-30"),
        ("invalid-range", "invalid-range"),
    ],
)
def test_normalize_date_range_value(raw: str, expected: str) -> None:
    assert normalize_date_range_value(raw) == expected


def test_normalize_date_range_value_none() -> None:
    assert normalize_date_range_value(None) is None


def test_metadata_result_to_doc_meta_bundle_uses_caller_summary() -> None:
    result = MetadataResult(
        doc_id="doc_test",
        profile="clinical_trial_doc.meta.zh.v0_1",
        context_strategy="metadata_sources_v0_1",
        context_block_count=20,
        doc_type=MetadataField(value="IB", confidence="high"),
        fields={"study_drug": MetadataField(value="StudyDrug_001", confidence="high")},
        warnings=[],
    )
    caller_summary = {"doc_type": "IB", "study_drug": "StudyDrug_001"}

    bundle = metadata_result_to_doc_meta_bundle(
        result,
        doc_meta_bundle_id="doc_meta_test",
        summary=caller_summary,
        file_hash="sha256:abc",
    )

    assert bundle["summary"] is caller_summary
    assert bundle["summary"]["study_drug"] == "StudyDrug_001"
    assert bundle["fields"]["study_drug"]["value"] == "StudyDrug_001"
    assert bundle["file_hash"] == "sha256:abc"


def test_artifacts_doc_meta_has_no_clinical_summary_fields() -> None:
    source = Path(__file__).resolve().parents[1] / "artifacts" / "doc_meta.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        if node.module not in {"__future__", "typing"}
    }

    assert "plugins.clinical_trial_doc" not in source_text
    assert "study_drug" not in source_text
    assert "study_start_date" not in source_text
    assert "build_doc_meta_summary" not in source_text
    assert "DOC_META_SUMMARY_FIELD_NAMES" not in source_text
    assert imported_modules == {"core.metadata.schemas"}


def test_build_clinical_trial_doc_meta_summary_normalizes_dates_preserves_fields() -> None:
    bundle = {
        "doc_type": {"value": "CSR"},
        "fields": {
            "study_start_date": {
                "value": "2022.01.02",
                "confidence": "high",
                "evidence": [{"source_text": "试验起始日期：2022.01.02"}],
            },
            "reporting_period": {
                "value": "2022.12.01-2023.11.30",
                "confidence": "high",
                "evidence": [{"source_text": "涵盖周期：2022.12.01-2023.11.30"}],
            },
            "protocol_id": {"confidence": "none"},
        },
    }

    summary = build_clinical_trial_doc_meta_summary(bundle)

    assert summary["study_start_date"] == "2022-01-02"
    assert summary["reporting_period"] == "2022-12-01/2023-11-30"
    assert summary["protocol_ids"] == []
    assert bundle["fields"]["study_start_date"]["value"] == "2022.01.02"
    assert bundle["fields"]["reporting_period"]["value"] == "2022.12.01-2023.11.30"
    assert (
        bundle["fields"]["study_start_date"]["evidence"][0]["source_text"]
        == "试验起始日期：2022.01.02"
    )


def test_build_clinical_trial_doc_meta_summary_includes_missing_fields_as_none() -> None:
    summary = build_clinical_trial_doc_meta_summary(
        {"doc_type": {"value": "IB"}, "fields": {}}
    )

    assert summary["doc_type"] == "IB"
    assert summary["protocol_ids"] == []
    for field_name in CLINICAL_TRIAL_DOC_META_SUMMARY_FIELD_NAMES:
        assert field_name in summary
        assert summary[field_name] is None


def test_build_clinical_trial_doc_meta_summary_protocol_ids_list() -> None:
    summary = build_clinical_trial_doc_meta_summary(
        {
            "doc_type": {"value": "IB"},
            "fields": {
                "protocol_id": {
                    "value": "Protocol_001",
                    "values": ["Protocol_001", "Protocol_002"],
                    "confidence": "high",
                }
            },
        }
    )

    assert summary["protocol_ids"] == ["Protocol_001", "Protocol_002"]


def _clinical_doc_meta_bundle(
    result: MetadataResult,
    *,
    doc_meta_bundle_id: str = "doc_meta_test",
) -> dict:
    base = result.to_dict()
    summary = build_clinical_trial_doc_meta_summary(base)
    return metadata_result_to_doc_meta_bundle(
        result,
        doc_meta_bundle_id=doc_meta_bundle_id,
        summary=summary,
    )


def test_clinical_doc_meta_bundle_summary_dates_normalized() -> None:
    result = MetadataResult(
        doc_id="doc_test",
        profile="clinical_trial_doc_meta_zh",
        context_strategy="metadata_sources_v0_1",
        context_block_count=20,
        doc_type=MetadataField(value="CSR", confidence="high"),
        fields={
            "study_start_date": MetadataField(value="2021.12.16", confidence="high"),
            "first_subject_dosed_date": MetadataField(
                value="2021.12.28", confidence="high"
            ),
            "dose_escalation_completion_date": MetadataField(
                value="2022.06.30", confidence="high"
            ),
            "study_completion_date": MetadataField(
                value="2023.03.20", confidence="high"
            ),
            "database_lock_date": MetadataField(value="2023.04.30", confidence="high"),
            "report_date": MetadataField(value="2023.07.15", confidence="high"),
            "document_date": MetadataField(value="2023.07.15", confidence="high"),
            "cutoff_date": MetadataField(value="2023.04.30", confidence="high"),
            "reporting_period": MetadataField(
                value="2022年12月18日-2023年12月17日", confidence="high"
            ),
        },
        warnings=[],
    )

    bundle = _clinical_doc_meta_bundle(result)

    assert bundle["fields"]["study_start_date"]["value"] == "2021.12.16"
    assert bundle["summary"]["study_start_date"] == "2021-12-16"
    assert bundle["summary"]["first_subject_dosed_date"] == "2021-12-28"
    assert bundle["summary"]["dose_escalation_completion_date"] == "2022-06-30"
    assert bundle["summary"]["study_completion_date"] == "2023-03-20"
    assert bundle["summary"]["database_lock_date"] == "2023-04-30"
    assert bundle["summary"]["report_date"] == "2023-07-15"
    assert bundle["summary"]["document_date"] == "2023-07-15"
    assert bundle["summary"]["cutoff_date"] == "2023-04-30"
    assert bundle["summary"]["reporting_period"] == "2022-12-18/2023-12-17"
