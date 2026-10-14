from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.document_schema import BUNDLE_SCHEMA_VERSION
from core.document.sentence_index import SENTENCE_INDEX_POLICY, SENTENCE_INDEX_VERSION
from runtime.io import load_json
from runtime.run_layout import EXTRACT_RUN_DIR_LAYOUT
from scripts.tools.inspect_runs import find_by_doc_id, load_run_indexes, search_records
from scripts.stage_runners import extract_runner

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)


def test_extract_runner_export_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert SAMPLE_DOCX.is_file()
    monkeypatch.setattr(extract_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        extract_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_runner.py",
            "export",
            "--file",
            str(SAMPLE_DOCX),
        ],
    )

    extract_runner.main()

    legacy_exports = tmp_path / "runs" / "extract" / "docx" / "exports"
    assert not legacy_exports.exists()

    session_dirs = [p for p in (tmp_path / "runs" / "extract").iterdir() if p.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]

    index_path = session_dir / "index.json"
    assert index_path.is_file()
    index_data = load_json(index_path)
    assert index_data["step"] == "extract"
    assert len(index_data["documents"]) == 1
    bundle_rel = index_data["documents"][0]["outputs"]["bundle"]
    assert bundle_rel.count("/") == 1
    assert not bundle_rel.startswith("docx/")
    assert bundle_rel.endswith("/bundle.json")

    doc_dirs = [p for p in session_dir.iterdir() if p.is_dir()]
    assert len(doc_dirs) == 1
    doc_dir = doc_dirs[0]
    assert (doc_dir / "bundle.json").is_file()
    assert (doc_dir / "run_summary.json").is_file()

    bundle = load_json(doc_dir / "bundle.json")
    summary = load_json(doc_dir / "run_summary.json")
    assert bundle["source_type"] == "docx"
    assert bundle["document_meta"]["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
    assert bundle["document_meta"]["sentence_index_version"] == SENTENCE_INDEX_VERSION
    assert bundle["document_meta"]["sentence_index_policy"] == SENTENCE_INDEX_POLICY
    assert summary["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
    assert summary["sentence_index_version"] == SENTENCE_INDEX_VERSION
    assert summary["sentence_index_policy"] == SENTENCE_INDEX_POLICY
    assert summary["run_dir_layout"] == EXTRACT_RUN_DIR_LAYOUT
    assert bundle["doc_id"] == summary["doc_id"]
    assert summary["file_hash"] == bundle["file_hash"]
    assert isinstance(bundle.get("file_hash"), str) and bundle["file_hash"].startswith("sha256:")


def test_inspect_runs_finds_new_extract_layout(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    session = runs / "extract" / "20260602_120000"
    doc_id = "doc_test0001-0000-4000-8000-000000000099"
    doc_dir = session / doc_id
    doc_dir.mkdir(parents=True)
    index_payload = {
        "schema_version": "0.1.0",
        "step": "extract",
        "created_at": "2026-06-02T12:00:00Z",
        "documents": [
            {
                "doc_id": doc_id,
                "label": "minimal extract",
                "privacy_level": "raw",
                "file_hash": "sha256:deadbeef",
                "outputs": {
                    "bundle": f"{doc_id}/bundle.json",
                    "run_summary": f"{doc_id}/run_summary.json",
                },
            }
        ],
    }
    (session / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    records = load_run_indexes(runs)
    assert any(r.step == "extract" for r in records)
    assert search_records(records, "minimal extract", runs_root=runs)
    assert find_by_doc_id(records, "doc_test0001")
