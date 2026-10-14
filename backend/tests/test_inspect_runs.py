# ruff: noqa: RUF015
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.tools.inspect_runs import (
    CURRENT_STEPS,
    LEGACY_STEPS,
    DocumentRunRecord,
    find_by_doc_id,
    flatten_documents,
    load_run_indexes,
    search_records,
    short_doc_id,
)


def test_step_constants_separate_current_and_legacy_pipeline_steps() -> None:
    assert "route" in CURRENT_STEPS
    assert "evidence_source_preparation_prepare" in CURRENT_STEPS
    assert "evidence_source_preparation_assess" in CURRENT_STEPS
    assert "process_prepare" in LEGACY_STEPS
    assert "process_assess" in LEGACY_STEPS
    assert "match_candidate_select" in LEGACY_STEPS
    assert "tag_prepare" in LEGACY_STEPS
    assert "tag" in LEGACY_STEPS
    assert "compare_candidate" in LEGACY_STEPS
    assert "group" in LEGACY_STEPS


def _write_index(
    path: Path,
    *,
    step: str,
    created_at: str,
    documents: list[dict] | None = None,
    extra: dict | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "schema_version": "0.1.0",
        "step": step,
        "created_at": created_at,
        "documents": documents if documents is not None else [],
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


DOC_FULL = "doc_a4528432-f165-4fe7-bac1-feb6b15181cc"
DOC_LABEL = "Record_001 StudyDrug_001研究者手册 V1.0"
FILE_HASH = "sha256:abc123def456"


@pytest.fixture
def sample_runs(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    mask_dir = runs / "mask" / "20260602_120000"
    filter_dir = runs / "filter" / "20260602_121000"
    doc_entry = {
        "doc_id": DOC_FULL,
        "label": DOC_LABEL,
        "privacy_level": "deidentified",
        "file_hash": FILE_HASH,
        "outputs": {
            "analysis_bundle": f"{DOC_FULL}/analysis_bundle.json",
            "mapping": f"{DOC_FULL}/mapping.json",
        },
    }
    _write_index(
        mask_dir / "index.json",
        step="mask",
        created_at="2026-06-02T12:00:00Z",
        documents=[doc_entry],
    )
    filter_outputs = dict(doc_entry["outputs"])
    filter_outputs["zone_match_bundle"] = f"{DOC_FULL}/zone_match_bundle.json"
    _write_index(
        filter_dir / "index.json",
        step="filter",
        created_at="2026-06-02T12:10:00Z",
        documents=[{**doc_entry, "outputs": filter_outputs}],
    )
    # filter index newer on disk (sort key for latest)
    (mask_dir / "index.json").touch()
    time.sleep(0.02)
    (filter_dir / "index.json").touch()
    return runs


def test_load_run_indexes_reads_two_sessions(sample_runs: Path) -> None:
    records = load_run_indexes(sample_runs, include_legacy=True)
    assert len(records) == 2
    steps = {r.step for r in records}
    assert steps == {"mask", "filter"}


def test_load_run_indexes_excludes_legacy_steps_by_default(sample_runs: Path) -> None:
    records = load_run_indexes(sample_runs)
    assert len(records) == 1
    assert records[0].step == "filter"


def test_latest_order_by_mtime(sample_runs: Path) -> None:
    records = load_run_indexes(sample_runs, include_legacy=True)
    assert records[0].step == "filter"
    assert records[1].step == "mask"


def test_search_matches_label_doc_id_and_hash(sample_runs: Path) -> None:
    records = load_run_indexes(sample_runs, include_legacy=True)
    assert len(search_records(records, "StudyDrug_001", runs_root=sample_runs)) == 2
    assert len(search_records(records, "doc_a452", runs_root=sample_runs)) == 2
    assert len(search_records(records, "sha256:abc", runs_root=sample_runs)) == 2
    assert len(search_records(records, "STUDYDRUG", runs_root=sample_runs)) == 2
    assert search_records(records, "nomatch_xyz", runs_root=sample_runs) == []


def test_find_doc_id_prefix_multiple_steps(sample_runs: Path) -> None:
    records = load_run_indexes(sample_runs, include_legacy=True)
    found = find_by_doc_id(records, "doc_a4528432")
    assert len(found) == 2
    steps = {d.index.step for d in found}
    assert steps == {"mask", "filter"}
    assert all(d.doc_id == DOC_FULL for d in found)


def test_missing_fields_do_not_crash(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    index_path = runs / "tag" / "20260602_130000" / "index.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text('{"step": "tag"}', encoding="utf-8")
    records = load_run_indexes(runs, include_legacy=True)
    assert len(records) == 1
    assert records[0].step == "tag"
    assert records[0].created_at == ""
    docs = flatten_documents(records[0])
    assert docs == []
    # document with missing label
    _write_index(
        runs / "mask" / "20260602_140000" / "index.json",
        step="mask",
        created_at="",
        documents=[{"doc_id": "doc_only", "outputs": "not-a-dict"}],
    )
    records = load_run_indexes(runs, include_legacy=True)
    sparse = [r for r in records if r.step == "mask" and r.created_at == ""][0]
    docs = flatten_documents(sparse)
    assert len(docs) == 1
    assert docs[0].doc_id == "doc_only"
    assert docs[0].label == "doc_only"
    assert docs[0].outputs == {}


def test_parse_failure_skipped_with_warning(tmp_path: Path, capsys) -> None:
    runs = tmp_path / "runs"
    bad = runs / "filter" / "bad" / "index.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    good = runs / "filter" / "good" / "index.json"
    _write_index(good, step="filter", created_at="2026-06-02T00:00:00Z")
    records = load_run_indexes(runs)
    assert len(records) == 1
    err = capsys.readouterr().err
    assert "warning" in err
    assert "skip" in err


def test_short_doc_id() -> None:
    assert short_doc_id(DOC_FULL) == "doc_a4528432"


def test_flatten_documents_privacy_and_hash(sample_runs: Path) -> None:
    records = load_run_indexes(sample_runs)
    doc: DocumentRunRecord = flatten_documents(records[0])[0]
    assert doc.privacy_level == "deidentified"
    assert doc.file_hash == FILE_HASH


def test_legacy_index_excluded_by_default(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_index(
        runs / "filter" / "20260602_120000" / "index.json",
        step="filter",
        created_at="2026-06-02T12:00:00Z",
    )
    _write_index(
        runs / "_legacy" / "mask" / "20260501_000000" / "index.json",
        step="mask",
        created_at="2026-05-01T00:00:00Z",
    )
    records = load_run_indexes(runs)
    assert len(records) == 1
    assert records[0].step == "filter"
    assert "_legacy" not in records[0].index_path.parts


def test_legacy_step_excluded_by_default(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_index(
        runs / "route" / "20260602_120000" / "index.json",
        step="route",
        created_at="2026-06-02T12:00:00Z",
    )
    _write_index(
        runs / "tag" / "20260602_121000" / "index.json",
        step="tag",
        created_at="2026-06-02T12:10:00Z",
    )
    records = load_run_indexes(runs)
    assert len(records) == 1
    assert records[0].step == "route"
    records_all = load_run_indexes(runs, include_legacy=True)
    assert len(records_all) == 2
    assert {r.step for r in records_all} == {"route", "tag"}


def test_legacy_index_included_when_requested(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_index(
        runs / "filter" / "20260602_120000" / "index.json",
        step="filter",
        created_at="2026-06-02T12:00:00Z",
    )
    _write_index(
        runs / "_legacy" / "filter" / "20260501_000000" / "index.json",
        step="filter",
        created_at="2026-05-01T00:00:00Z",
    )
    records = load_run_indexes(runs, include_legacy=True)
    assert len(records) == 2
    steps = {r.step for r in records}
    assert steps == {"filter"}
    legacy = [r for r in records if "_legacy" in r.index_path.parts]
    assert len(legacy) == 1
    assert legacy[0].step == "filter"


def test_load_run_indexes_discovers_legacy_process_step_when_requested(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    doc_entry = {
        "doc_id": DOC_FULL,
        "label": DOC_LABEL,
        "file_hash": FILE_HASH,
        "zone_key": "ib_clinical_safety_zh",
        "outputs": {
            "scope_assessments": (
                f"{DOC_FULL}/ib_clinical_safety_zh/aggregate_evidence/"
                "scope_assessments.json"
            ),
        },
    }
    _write_index(
        runs / "process" / "assess" / "20260713_120000" / "index.json",
        step="process_assess",
        created_at="2026-07-13T12:00:00Z",
        documents=[doc_entry],
    )
    _write_index(
        runs / "match" / "20260713_121000" / "index.json",
        step="match_candidate_select",
        created_at="2026-07-13T12:10:00Z",
        documents=[
            {
                **doc_entry,
                "outputs": {
                    "match_candidates": (
                        f"{DOC_FULL}/dsur_clinical_safety_zh/aggregate_evidence/"
                        "candidate_select/match_candidates.json"
                    ),
                },
            }
        ],
    )
    records = load_run_indexes(runs)
    assert records == []
    legacy_records = load_run_indexes(runs, include_legacy=True)
    legacy_steps = {record.step for record in legacy_records}
    assert "process_assess" in legacy_steps
    assert "match_candidate_select" in legacy_steps
    legacy_assess_record = next(
        r for r in legacy_records if r.step == "process_assess"
    )
    flattened = flatten_documents(legacy_assess_record)
    assert flattened[0].doc_id == DOC_FULL
