"""Targeted tests for application cleanup of legacy kind=highlight annotations."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.document_consistency_qc.source_annotation import (
    SourceAnnotationValidationError,
    count_legacy_source_highlights,
    create_source_annotation,
    delete_legacy_source_highlights,
    delete_source_annotations_by_kind,
    load_source_annotations,
    resolve_source_annotation_state_path,
)
from artifacts.source_annotation_state import (
    SOURCE_ANNOTATION_KIND_HIGHLIGHT,
    build_source_annotation_state_payload,
    generate_annotation_id,
)
from runtime.io import load_json, save_json
from tests.test_source_annotation_application import (
    _default_extract_blocks,
    _highlight_range_block,
    _valid_anchor,
    _write_fixture,
)


def _flow_root(tmp_path: Path) -> Path:
    return tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"


def _create_highlight(
    tmp_path: Path,
    flow_run_id: str,
    *,
    start_offset: int,
    end_offset: int,
) -> None:
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(
            block_id="C0101",
            sentence_id="C0101:S001",
        ),
        range={"start_offset": start_offset, "end_offset": end_offset},
        kind="highlight",
    )


def _seed_legacy_highlight_for_doc(
    tmp_path: Path,
    flow_run_id: str,
    *,
    doc_id: str,
    start_offset: int,
    end_offset: int,
) -> None:
    path = resolve_source_annotation_state_path(flow_root=_flow_root(tmp_path))
    entries: dict[str, dict[str, object]] = {}
    if path.is_file():
        artifact = load_json(path)
        raw_entries = artifact.get("annotations")
        if isinstance(raw_entries, dict):
            entries = {str(key): dict(value) for key, value in raw_entries.items()}

    annotation_id = generate_annotation_id()
    entries[annotation_id] = {
        "annotation_id": annotation_id,
        "anchor": _valid_anchor(
            doc_id=doc_id,
            block_id="C0101",
            sentence_id="C0101:S001",
        ),
        "kind": SOURCE_ANNOTATION_KIND_HIGHLIGHT,
        "range": {"start_offset": start_offset, "end_offset": end_offset},
        "created_at": "2026-09-13T00:00:00Z",
        "updated_at": "2026-09-13T00:00:00Z",
    }
    payload = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=entries,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path, payload)


def _write_fixture_with_highlight_block(tmp_path: Path) -> str:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    return _write_fixture(tmp_path, extract_blocks=blocks)


def test_count_legacy_source_highlights_finds_scoped_highlights(tmp_path: Path) -> None:
    flow_run_id = _write_fixture_with_highlight_block(tmp_path)
    _create_highlight(tmp_path, flow_run_id, start_offset=0, end_offset=2)
    _create_highlight(tmp_path, flow_run_id, start_offset=2, end_offset=4)
    _seed_legacy_highlight_for_doc(
        tmp_path,
        flow_run_id,
        doc_id="doc_other",
        start_offset=0,
        end_offset=1,
    )

    assert (
        count_legacy_source_highlights(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            doc_id="doc_test",
        )
        == 2
    )


def test_delete_legacy_source_highlights_removes_only_target_doc_highlights(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_fixture_with_highlight_block(tmp_path)
    _create_highlight(tmp_path, flow_run_id, start_offset=0, end_offset=2)
    _create_highlight(tmp_path, flow_run_id, start_offset=2, end_offset=4)
    _seed_legacy_highlight_for_doc(
        tmp_path,
        flow_run_id,
        doc_id="doc_other",
        start_offset=0,
        end_offset=1,
    )
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0101", sentence_id="C0101:S001"),
        range={"start_offset": 4, "end_offset": 5},
        kind="edit",
        replacement_text="x",
    )
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0101", sentence_id="C0101:S001"),
        range={"start_offset": 5, "end_offset": 6},
        kind="comment",
        content="note",
    )

    summary = delete_legacy_source_highlights(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        doc_id="doc_test",
    )

    assert summary.legacy_highlights_found == 2
    assert summary.legacy_highlights_deleted == 2
    assert summary.revisions_preserved == 1
    assert summary.comments_preserved == 1

    model = load_source_annotations(project_root=tmp_path, flow_run_id=flow_run_id)
    kinds = sorted(entry.kind for entry in model.annotations)
    assert kinds == ["comment", "edit", "highlight"]


def test_delete_legacy_source_highlights_zero_highlight_is_no_op(tmp_path: Path) -> None:
    flow_run_id = _write_fixture_with_highlight_block(tmp_path)
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0101", sentence_id="C0101:S001"),
        range={"start_offset": 0, "end_offset": 2},
        kind="edit",
        replacement_text="x",
    )

    summary = delete_legacy_source_highlights(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        doc_id="doc_test",
    )

    assert summary.legacy_highlights_found == 0
    assert summary.legacy_highlights_deleted == 0
    assert summary.revisions_preserved == 1
    assert summary.comments_preserved == 0

    path = resolve_source_annotation_state_path(flow_root=_flow_root(tmp_path))
    assert path.is_file()


def test_count_and_delete_with_missing_artifact_are_no_ops(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    path = resolve_source_annotation_state_path(flow_root=_flow_root(tmp_path))
    assert not path.is_file()

    assert (
        count_legacy_source_highlights(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            doc_id="doc_test",
        )
        == 0
    )

    summary = delete_legacy_source_highlights(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        doc_id="doc_test",
    )
    assert summary.legacy_highlights_deleted == 0
    assert not path.is_file()


def test_delete_last_legacy_highlights_removes_artifact(tmp_path: Path) -> None:
    flow_run_id = _write_fixture_with_highlight_block(tmp_path)
    _create_highlight(tmp_path, flow_run_id, start_offset=0, end_offset=2)
    path = resolve_source_annotation_state_path(flow_root=_flow_root(tmp_path))
    assert path.is_file()

    delete_legacy_source_highlights(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        doc_id="doc_test",
    )
    assert not path.is_file()


def test_delete_legacy_source_highlights_requires_doc_id(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationValidationError, match="doc_id"):
        delete_legacy_source_highlights(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            doc_id="",
        )


def test_delete_source_annotations_by_kind_still_rejects_highlight(tmp_path: Path) -> None:
    flow_run_id = _write_fixture_with_highlight_block(tmp_path)
    with pytest.raises(SourceAnnotationValidationError):
        delete_source_annotations_by_kind(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            doc_id="doc_test",
            kind="highlight",
        )
