"""Slice 4: historical Flow summary ownership regressions."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    validate_flow_run_summary,
)
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from runtime.io import load_json
from tests.test_document_consistency_qc_flow import _run_flow

_TEST_FILE_HASH = (
    "sha256:10910f206d37eb8e78e2cd5becd0e23747dc216bb446014dcc08d1fc61579cb4"
)

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)


def test_flow_summary_012_legacy_intake_semantics_validate() -> None:
    payload = {
        "artifact_type": "document_consistency_qc_flow_run_summary",
        "schema_version": PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
        "flow_id": "document_consistency_qc",
        "flow_run_id": "document_consistency_qc_legacy_fixture",
        "capability_id": "internal_dsur",
        "source_language": "zh",
        "status": "success",
        "created_at": "2026-09-20T01:02:03+00:00",
        "completed_at": "2026-09-20T01:02:04+00:00",
        "slots": [
            {
                "slot_id": "source",
                "status": "success",
                "extract_config_id": "docx",
                "prepare_analysis_config_id": "pacfg_test",
                "intake_run_id": "request_file_intake_legacy",
                "file_hash": _TEST_FILE_HASH,
                "doc_id": "doc_legacy",
                "extract_run_id": "extract_legacy",
                "prepare_analysis_run_id": "prepare_legacy",
                "analysis_bundle_path": "/tmp/analysis_bundle.json",
                "block_manifest_path": "/tmp/block_manifest.json",
                "prepare_analysis_run_summary_path": "/tmp/prepare_summary.json",
                "doc_meta_run_id": "doc_meta_source",
                "doc_meta_output_dir": "/tmp/doc_meta",
                "doc_meta_bundle_path": "/tmp/doc_meta/doc_meta_bundle.json",
                "doc_meta_run_summary_path": "/tmp/doc_meta/run_summary.json",
                "filter_job_ids": [],
            }
        ],
    }
    validate_flow_run_summary(payload)


def test_new_flow_run_has_no_participant_intake_directory(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={"source": SAMPLE_DOCX},
        project_root=tmp_path,
    )
    flow_root = report.flow_run_summary_path.parent
    assert not (flow_root / "participants" / "source" / "intake").exists()
    summary = load_json(report.flow_run_summary_path)
    assert summary["schema_version"] == FLOW_RUN_SUMMARY_SCHEMA_VERSION
    assert "intake_run_id" not in summary["slots"][0]
