from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.zone_match_bundle import ZONE_MATCH_BUNDLE_FILENAME
from runtime.io import load_json
from runtime.run_index import (
    INDEX_SCHEMA_VERSION,
    RunIndexDocument,
    build_doc_meta_index_document,
    build_extract_index_document,
    build_filter_index_document,
    build_prepare_analysis_index_document,
    build_aggregate_evidence_assess_index_document,
    index_relative_path,
    masked_index_label,
    resolve_index_root,
    write_run_index,
)

RAW_DISPLAY = "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15"
RAW_FILE_NAME = f"{RAW_DISPLAY}.docx"
MASKED_DISPLAY = "StudyDrug_001 研究者手册 V1.0 2024.03.15"
MASKED_FILE_NAME = f"{MASKED_DISPLAY}.docx"
FIXED_DOC_ID = "doc_00000000-0000-4000-8000-000000000001"
ESTABLISHED_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
RAW_SOURCE_PATH = r"D:\secret\uploads\handbook.docx"


def _assert_relative_outputs(data: dict) -> None:
    for entry in data["documents"]:
        for rel_path in entry["outputs"].values():
            assert not Path(rel_path).is_absolute()
            if rel_path and rel_path != ".":
                assert ":" not in rel_path.split("/")[0]


def _assert_no_raw_leak_index(data: dict, *, step: str) -> None:
    assert data["step"] == step
    assert len(data["documents"]) >= 1
    serialized = json.dumps(data, ensure_ascii=False)
    assert RAW_FILE_NAME not in serialized
    assert RAW_DISPLAY not in serialized
    assert RAW_SOURCE_PATH not in serialized
    assert "source_docx" not in serialized
    assert "source_path" not in serialized
    assert "masked" not in serialized
    for entry in data["documents"]:
        assert entry["privacy_level"] in {"raw", "deidentified"}
        assert entry["label"] != RAW_FILE_NAME
        assert entry["label"] != RAW_DISPLAY
    _assert_relative_outputs(data)


def test_resolve_index_root_custom(tmp_path: Path) -> None:
    session = tmp_path / "runs" / "filter" / "20260602_120000"
    session.mkdir(parents=True)
    custom = tmp_path / "custom_out"
    assert resolve_index_root(session_dir=session, custom_output_dir=custom) == custom.resolve()
    assert resolve_index_root(session_dir=session) == session.resolve()


def test_index_relative_path_rejects_outside_root(tmp_path: Path) -> None:
    index_root = tmp_path / "custom"
    index_root.mkdir()
    outside = tmp_path / "elsewhere" / "zone_bundle.json"
    outside.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="not under index root"):
        index_relative_path(outside, index_root)


def test_write_run_index_valid_json(tmp_path: Path) -> None:
    index_root = tmp_path / "20260602_120000"
    docs = [
        RunIndexDocument(
            doc_id=FIXED_DOC_ID,
            label="sample",
            privacy_level="raw",
            file_hash="sha256:abc",
            outputs={"bundle": f"{FIXED_DOC_ID}/bundle.json"},
        )
    ]
    path = write_run_index(index_root, step="extract", documents=docs, created_at="2026-06-02T10:15:00Z")
    assert path == index_root / "index.json"
    data = load_json(path)
    assert data["schema_version"] == INDEX_SCHEMA_VERSION
    assert data["step"] == "extract"
    _assert_relative_outputs(data)


def test_write_run_index_omits_null_doc_id(tmp_path: Path) -> None:
    index_root = tmp_path / "request_file_intake" / "20260816_test"
    doc = RunIndexDocument(
        label="IB.docx",
        file_hash="sha256:" + "a" * 64,
        doc_id=None,
        privacy_level="raw",
        outputs={"request_file_intake_result": "request_file_intake_result.json"},
    )
    path = write_run_index(
        index_root,
        step="request_file_intake",
        documents=[doc],
        run_id="request_file_intake_test",
    )
    data = load_json(path)
    assert data["run_id"] == "request_file_intake_test"
    assert "doc_id" not in data["documents"][0]


def test_write_run_index_merges_documents_by_doc_id(tmp_path: Path) -> None:
    index_root = tmp_path / "20260701_2250"
    zone_key = "ib_clinical_safety_zh"
    other_doc_id = "doc_00000000-0000-4000-8000-000000000002"
    third_doc_id = "doc_00000000-0000-4000-8000-000000000003"

    first = RunIndexDocument(
        doc_id=FIXED_DOC_ID,
        label="IB",
        privacy_level="deidentified",
        file_hash="sha256:ib",
        outputs={"run_summary": f"{zone_key}/{FIXED_DOC_ID}/run_summary.json"},
    )
    write_run_index(
        index_root,
        step="tag_prepare",
        documents=[first],
        created_at="2026-07-01T14:50:00Z",
    )

    second = RunIndexDocument(
        doc_id=other_doc_id,
        label="CSR",
        privacy_level="deidentified",
        file_hash="sha256:csr",
        outputs={"run_summary": f"csr_clinical_safety_zh/{other_doc_id}/run_summary.json"},
    )
    write_run_index(index_root, step="tag_prepare", documents=[second])

    third = RunIndexDocument(
        doc_id=third_doc_id,
        label="DSUR",
        privacy_level="deidentified",
        file_hash="sha256:dsur",
        outputs={"run_summary": f"dsur_clinical_safety_zh/{third_doc_id}/run_summary.json"},
    )
    write_run_index(index_root, step="tag_prepare", documents=[third])

    loaded = load_json(index_root / "index.json")
    assert loaded["step"] == "tag_prepare"
    assert loaded["created_at"] == "2026-07-01T14:50:00Z"
    assert [entry["doc_id"] for entry in loaded["documents"]] == [
        FIXED_DOC_ID,
        other_doc_id,
        third_doc_id,
    ]


def test_write_run_index_same_doc_id_replaces_entry(tmp_path: Path) -> None:
    index_root = tmp_path / "session"
    first = RunIndexDocument(
        doc_id=FIXED_DOC_ID,
        label="first label",
        privacy_level="deidentified",
        file_hash="sha256:first",
        outputs={"run_summary": f"{FIXED_DOC_ID}/run_summary.json"},
    )
    second = RunIndexDocument(
        doc_id=FIXED_DOC_ID,
        label="updated label",
        privacy_level="deidentified",
        file_hash="sha256:second",
        outputs={"run_summary": f"{FIXED_DOC_ID}/run_summary.v2.json"},
    )

    write_run_index(index_root, step="tag_prepare", documents=[first])
    write_run_index(index_root, step="tag_prepare", documents=[second])

    loaded = load_json(index_root / "index.json")
    assert len(loaded["documents"]) == 1
    assert loaded["documents"][0]["label"] == "updated label"
    assert loaded["documents"][0]["file_hash"] == "sha256:second"


def test_write_run_index_step_mismatch_replaces_existing(tmp_path: Path) -> None:
    index_root = tmp_path / "session"
    extract_doc = RunIndexDocument(
        doc_id=FIXED_DOC_ID,
        label="extract",
        privacy_level="raw",
        file_hash="sha256:extract",
        outputs={"bundle": f"{FIXED_DOC_ID}/bundle.json"},
    )
    filter_doc = RunIndexDocument(
        doc_id=FIXED_DOC_ID,
        label="filter",
        privacy_level="deidentified",
        file_hash="sha256:filter",
        outputs={"zone_match_bundle": f"ib/{FIXED_DOC_ID}/zone_match_bundle.json"},
    )

    write_run_index(
        index_root,
        step="extract",
        documents=[extract_doc],
        created_at="2026-06-02T10:00:00Z",
    )
    write_run_index(
        index_root,
        step="filter",
        documents=[filter_doc],
        created_at="2026-06-02T11:00:00Z",
    )

    loaded = load_json(index_root / "index.json")
    assert loaded["step"] == "filter"
    assert loaded["created_at"] == "2026-06-02T11:00:00Z"
    assert len(loaded["documents"]) == 1
    assert loaded["documents"][0]["label"] == "filter"


def test_extract_index_privacy_level_raw_without_analysis_transform(
    tmp_path: Path,
) -> None:
    index_root = tmp_path / "session"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    bundle = SimpleNamespace(
        doc_id=FIXED_DOC_ID,
        display_name=RAW_DISPLAY,
        file_hash="sha256:deadbeef",
    )
    doc = build_extract_index_document(
        bundle=bundle, out_dir=out_dir, index_root=index_root
    )
    write_run_index(index_root, step="extract", documents=[doc])
    loaded = load_json(index_root / "index.json")
    entry = loaded["documents"][0]
    assert entry["privacy_level"] == "raw"
    assert "analysis_transform" not in entry
    assert "privacy_enabled" not in entry


def test_prepare_analysis_index_identity_without_privacy(tmp_path: Path) -> None:
    index_root = tmp_path / "session"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    bundle = {
        "doc_id": FIXED_DOC_ID,
        "display_name": RAW_DISPLAY,
        "privacy_enabled": False,
        "privacy_transforms": {
            "after_extract": {
                "detectors": [],
                "applied": False,
                "detectors_used": [],
            }
        },
        "file_hash": "sha256:identity",
    }
    doc = build_prepare_analysis_index_document(
        analysis_bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
    )
    write_run_index(index_root, step="prepare_analysis", documents=[doc])
    entry = load_json(index_root / "index.json")["documents"][0]
    assert "privacy_level" not in entry
    assert entry["analysis_transform"] == "identity"
    assert entry["privacy_transform_applied"] is False
    assert entry["privacy_detectors"] == []


def test_prepare_analysis_index_privacy_transform(tmp_path: Path) -> None:
    index_root = tmp_path / "session"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    bundle = {
        "doc_id": FIXED_DOC_ID,
        "display_name": MASKED_DISPLAY,
        "privacy_enabled": True,
        "privacy_transforms": {
            "after_extract": {
                "detectors": ["registry", "regex"],
                "applied": True,
                "detectors_used": ["registry", "regex"],
            }
        },
        "file_hash": "sha256:deidentified",
    }
    doc = build_prepare_analysis_index_document(
        analysis_bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
    )
    write_run_index(index_root, step="prepare_analysis", documents=[doc])
    entry = load_json(index_root / "index.json")["documents"][0]
    assert "privacy_level" not in entry
    assert entry["analysis_transform"] == "privacy_transform"
    assert entry["privacy_transform_applied"] is True
    assert entry["privacy_detectors"] == ["registry", "regex"]
    assert "masked" not in json.dumps(entry, ensure_ascii=False)


def test_extract_index_document_fields(tmp_path: Path) -> None:
    index_root = tmp_path / "session"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    bundle = SimpleNamespace(
        doc_id=FIXED_DOC_ID,
        display_name=RAW_DISPLAY,
        file_name=RAW_FILE_NAME,
        file_hash="sha256:deadbeef",
    )
    doc = build_extract_index_document(
        bundle=bundle, out_dir=out_dir, index_root=index_root
    )
    assert doc.outputs["bundle"] == f"{FIXED_DOC_ID}/bundle.json"


def test_extract_default_session_index(tmp_path: Path) -> None:
    index_root = tmp_path / "exports" / "20260602_120000"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)

    bundle = SimpleNamespace(
        doc_id=FIXED_DOC_ID,
        display_name=RAW_DISPLAY,
        file_hash="sha256:abc",
    )
    doc = build_extract_index_document(
        bundle=bundle, out_dir=out_dir, index_root=index_root
    )
    write_run_index(index_root, step="extract", documents=[doc])
    assert (index_root / "index.json").is_file()


def test_extract_custom_output_index_local(tmp_path: Path) -> None:
    runs_session = tmp_path / "runs" / "extract" / "20260602_120000"
    runs_session.mkdir(parents=True)
    custom_root = tmp_path / "custom"
    out_dir = custom_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)

    bundle = SimpleNamespace(doc_id=FIXED_DOC_ID, display_name=RAW_DISPLAY, file_hash="sha256:x")
    doc = build_extract_index_document(
        bundle=bundle, out_dir=out_dir, index_root=custom_root
    )
    write_run_index(custom_root, step="extract", documents=[doc])

    assert (custom_root / "index.json").is_file()
    assert not (runs_session / "index.json").exists()
    data = load_json(custom_root / "index.json")
    assert data["documents"][0]["outputs"]["bundle"] == f"{FIXED_DOC_ID}/bundle.json"
    _assert_relative_outputs(data)


def test_masked_index_label_prefers_safe_display_name() -> None:
    masked_display = "StudyDrug_001-Record_001 研究者手册 V1.0 2024.03.15"
    bundle = {
        "doc_id": FIXED_DOC_ID,
        "display_name": masked_display,
        "file_name": f"{masked_display}.docx",
    }
    assert masked_index_label(bundle) == masked_display
    assert masked_index_label(bundle) != FIXED_DOC_ID


def test_masked_index_label_falls_back_to_doc_id() -> None:
    bundle = {"doc_id": FIXED_DOC_ID, "display_name": ""}
    assert masked_index_label(bundle) == FIXED_DOC_ID


def test_mask_index_document_no_raw_leak(tmp_path: Path) -> None:
    index_root = tmp_path / "20260602_130000"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    masked_display = "StudyDrug_001 研究者手册 V1.0 2024.03.15"
    masked_bundle = {
        "doc_id": FIXED_DOC_ID,
        "display_name": masked_display,
        "file_name": f"{masked_display}.docx",
        "document_meta": {"source_path": None},
        "file_hash": "sha256:masked",
    }
    doc = build_prepare_analysis_index_document(
        analysis_bundle=masked_bundle,
        out_dir=out_dir,
        index_root=index_root,
    )
    assert doc.label == masked_display
    assert doc.label != FIXED_DOC_ID
    assert doc.outputs["analysis_bundle"] == f"{FIXED_DOC_ID}/analysis_bundle.json"
    serialized = json.dumps({"documents": [doc]}, default=lambda o: o.__dict__, ensure_ascii=False)
    assert RAW_FILE_NAME not in serialized
    assert RAW_DISPLAY not in serialized
    assert RAW_SOURCE_PATH not in serialized


def test_doc_meta_index_default_layout(tmp_path: Path) -> None:
    index_root = tmp_path / "20260602_140000"
    out_dir = index_root / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    bundle = {"doc_id": FIXED_DOC_ID, "display_name": MASKED_DISPLAY, "file_hash": "sha256:meta"}
    doc = build_doc_meta_index_document(
        bundle=bundle, out_dir=out_dir, index_root=index_root
    )
    write_run_index(index_root, step="doc_meta", documents=[doc])
    loaded = load_json(index_root / "index.json")
    assert loaded["documents"][0]["outputs"]["doc_meta_bundle"] == (
        f"{FIXED_DOC_ID}/doc_meta_bundle.json"
    )
    _assert_no_raw_leak_index(loaded, step="doc_meta")


def test_doc_meta_custom_output_index_flat_artifacts(tmp_path: Path) -> None:
    custom_root = tmp_path / "custom_doc_meta"
    custom_root.mkdir()
    bundle = {"doc_id": FIXED_DOC_ID, "display_name": MASKED_DISPLAY, "file_hash": "sha256:meta"}
    doc = build_doc_meta_index_document(
        bundle=bundle, out_dir=custom_root, index_root=custom_root
    )
    write_run_index(custom_root, step="doc_meta", documents=[doc])
    loaded = load_json(custom_root / "index.json")
    assert loaded["documents"][0]["outputs"]["doc_meta_bundle"] == "doc_meta_bundle.json"
    _assert_no_raw_leak_index(loaded, step="doc_meta")


def test_filter_index_default_session(tmp_path: Path) -> None:
    index_root = tmp_path / "20260602_150000"
    zone_key = "ib_clinical_safety_zh"
    out_dir = index_root / zone_key / FIXED_DOC_ID
    out_dir.mkdir(parents=True)
    bundle = {"doc_id": FIXED_DOC_ID, "display_name": MASKED_DISPLAY, "file_hash": "sha256:filter"}
    doc = build_filter_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        include_debug=True,
    )
    assert doc.outputs["zone_match_bundle"] == (
        f"{zone_key}/{FIXED_DOC_ID}/{ZONE_MATCH_BUNDLE_FILENAME}"
    )
    write_run_index(index_root, step="filter", documents=[doc])
    _assert_no_raw_leak_index(load_json(index_root / "index.json"), step="filter")


def test_filter_custom_output_index_local(tmp_path: Path) -> None:
    runs_session = tmp_path / "runs" / "filter" / "20260602_150000"
    runs_session.mkdir(parents=True)
    custom_root = tmp_path / "custom"
    zone_key = "ib_clinical_safety_zh"
    out_dir = custom_root / zone_key / FIXED_DOC_ID
    out_dir.mkdir(parents=True)

    bundle = {"doc_id": FIXED_DOC_ID, "display_name": MASKED_DISPLAY, "file_hash": "sha256:f"}
    doc = build_filter_index_document(
        bundle=bundle, out_dir=out_dir, index_root=custom_root
    )
    write_run_index(custom_root, step="filter", documents=[doc])

    assert (custom_root / "index.json").is_file()
    assert not (runs_session / "index.json").exists()
    loaded = load_json(custom_root / "index.json")
    assert loaded["documents"][0]["outputs"]["zone_match_bundle"] == (
        f"{zone_key}/{FIXED_DOC_ID}/{ZONE_MATCH_BUNDLE_FILENAME}"
    )
    _assert_no_raw_leak_index(loaded, step="filter")


@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_extract_doc_identity_fixed_doc_id(_mock_gen) -> None:
    from core.document.doc_identity import build_document_processing_identity

    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_safety_tag_integration_001.docx",
    )
    assert identity.doc_id == FIXED_DOC_ID


def test_build_aggregate_evidence_assess_index_document_outputs(tmp_path: Path) -> None:
    index_root = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "assess"
        / "20260713_120000"
    )
    out_dir = (
        index_root
        / FIXED_DOC_ID
        / "ib_clinical_safety_zh"
        / "aggregate_evidence"
    )
    out_dir.mkdir(parents=True)
    bundle = {
        "doc_id": FIXED_DOC_ID,
        "file_hash": "sha256:abc",
        "display_name": MASKED_DISPLAY,
        "privacy_enabled": True,
    }
    doc = build_aggregate_evidence_assess_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        zone_key="ib_clinical_safety_zh",
    )
    write_run_index(
        index_root,
        step="evidence_source_preparation_assess",
        documents=[doc],
        run_id="20260713_120000",
    )
    loaded = load_json(index_root / "index.json")
    entry = loaded["documents"][0]
    prefix = f"{FIXED_DOC_ID}/ib_clinical_safety_zh/aggregate_evidence"
    assert entry["outputs"]["scope_assessments"] == f"{prefix}/scope_assessments.json"
    assert "scope_processing_plan" not in entry["outputs"]
    assert entry["outputs"]["scope_assessment_review"] == (
        f"{prefix}/scope_assessment_review.json"
    )
    assert entry["zone_key"] == "ib_clinical_safety_zh"
    assert loaded["document_count"] == 1
    serialized = json.dumps(loaded, ensure_ascii=False)
    assert "tag_output.json" not in serialized
    assert "compare_candidates.json" not in serialized
    assert "group_members.json" not in serialized
    _assert_no_raw_leak_index(loaded, step="evidence_source_preparation_assess")
