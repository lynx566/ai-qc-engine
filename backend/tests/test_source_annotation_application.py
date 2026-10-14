"""Targeted tests for source annotation application read/write boundary."""

from __future__ import annotations

# ruff: noqa: E402

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.finding_review import (
    load_finding_review_state,
    set_finding_marked,
    set_finding_resolved,
)
from application.clinical_trial_doc_consistency_qc.result_read import (
    load_document_consistency_qc_result,
)
from application.document_consistency_qc.source_annotation import (
    SourceAnnotationNotFoundError,
    SourceAnnotationPersistenceError,
    SourceAnnotationUnknownAnnotationError,
    SourceAnnotationValidationError,
    create_source_annotation,
    delete_source_annotation,
    delete_source_annotations_by_kind,
    load_source_annotations,
    resolve_source_annotation_state_path,
    update_source_annotation_content,
)
from artifacts.finding_review_state import FINDING_REVIEW_STATE_FILENAME
from runtime.io import load_json, save_json
from tests.test_internal_result_read import (
    _default_extract_blocks,
    _write_minimal_internal_result_fixture,
)


def _valid_anchor(**overrides: str) -> dict[str, str]:
    base = {
        "slot_id": "source",
        "doc_id": "doc_test",
        "block_id": "C0002",
        "sentence_id": "C0002:S001",
    }
    base.update(overrides)
    return base


def _write_fixture(tmp_path: Path, *, extract_blocks: list[dict] | None = None) -> str:
    return _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "label": "fail",
                        "conclusion": "issue",
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=extract_blocks or _default_extract_blocks(),
    )


def test_completed_flow_loads_empty_when_annotation_artifact_missing(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_fixture(tmp_path)
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    annotation_path = resolve_source_annotation_state_path(flow_root=flow_root)
    assert not annotation_path.is_file()

    model = load_source_annotations(project_root=tmp_path, flow_run_id=flow_run_id)
    assert model.flow_run_id == flow_run_id
    assert model.annotations == ()


def test_create_valid_anchor_persists(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    assert path.is_file()
    payload = load_json(path)
    assert created.annotation_id in payload["annotations"]


def test_unknown_slot_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationValidationError, match="slot_id"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(slot_id="missing"),
        )


def test_doc_id_mismatch_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationValidationError, match="doc_id"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(doc_id="doc_other"),
        )


def test_unknown_block_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationValidationError, match="block_id"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="C9999", sentence_id="C9999:S001"),
        )


def test_nonexistent_sentence_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationValidationError, match="not a member"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(sentence_id="C0002:S099"),
        )


def test_sentence_on_other_block_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(ValueError, match="block prefix"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="C0002", sentence_id="C0003:S001"),
        )


def test_two_annotations_same_sentence(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    first = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    second = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    assert first.annotation_id != second.annotation_id


def test_delete_one_leaves_other(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    first = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    second = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0003", sentence_id="C0003:S001"),
    )
    model = delete_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        annotation_id=first.annotation_id,
    )
    remaining_ids = {entry.annotation_id for entry in model.annotations}
    assert remaining_ids == {second.annotation_id}


def test_delete_last_removes_artifact(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    delete_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        annotation_id=created.annotation_id,
    )
    assert not path.is_file()


def test_delete_unknown_annotation_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationUnknownAnnotationError):
        delete_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            annotation_id="ann_missing",
        )


def test_persistence_uses_save_json_atomic(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with (
        patch(
            "application.document_consistency_qc.source_annotation.save_json_atomic",
            side_effect=OSError("disk full"),
        ) as mocked,
        pytest.raises(SourceAnnotationPersistenceError, match="disk full"),
    ):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(),
        )
    assert mocked.called


def test_create_does_not_mutate_extract_or_result_or_review(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    extract_path = flow_root / "participants" / "source" / "extract" / "bundle.json"
    findings_path = (
        flow_root / "participants" / "source" / "evidence_comparison" / "findings.json"
    )
    extract_before = load_json(extract_path)
    findings_before = load_json(findings_path)

    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )

    assert load_json(extract_path) == extract_before
    assert load_json(findings_path) == findings_before

    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    review_path = flow_root / "finding_review" / FINDING_REVIEW_STATE_FILENAME
    review_before = load_json(review_path)
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0003", sentence_id="C0003:S001"),
    )
    assert load_json(review_path) == review_before


def test_format_block_anchor_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    extract_bundle_blocks = blocks
    flow_run_id = _write_fixture(tmp_path, extract_blocks=extract_bundle_blocks)
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    extract_path = flow_root / "participants" / "source" / "extract" / "bundle.json"
    bundle = load_json(extract_path)
    bundle["format_blocks"] = [
        {
            "block_id": "F0001",
            "kind": "header",
            "raw_text": "Header text",
            "normalized_text": "Header text",
            "sentences": [
                {
                    "sentence_id": "F0001:S001",
                    "raw_text": "Header text",
                    "normalized_text": "Header text",
                }
            ],
        }
    ]
    save_json(extract_path, bundle)

    with pytest.raises(SourceAnnotationValidationError, match="block_id"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="F0001", sentence_id="F0001:S001"),
        )


def test_table_sentence_anchor_allowed(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    blocks.append(
        {
            "block_id": "T0001",
            "kind": "table",
            "heading_path": ["Scope A"],
            "doc_order_index": 6,
            "raw_text": "A | B",
            "meta": {"raw_rows": [["A", "B"]]},
            "sentences": [
                {
                    "sentence_id": "T0001:S001",
                    "raw_text": "A | B",
                    "normalized_text": "A | B",
                }
            ],
        }
    )
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="T0001", sentence_id="T0001:S001"),
    )
    assert created.anchor.sentence_id == "T0001:S001"


def test_unknown_flow_rejected(tmp_path: Path) -> None:
    with pytest.raises(SourceAnnotationNotFoundError):
        load_source_annotations(
            project_root=tmp_path,
            flow_run_id="document_consistency_qc_missing",
        )


def test_result_still_loads_after_annotation_create(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    before = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    after = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    assert len(before.scope_results) == len(after.scope_results)


def _paragraph_with_emoji_block() -> dict:
    return {
        "block_id": "C0100",
        "kind": "paragraph",
        "heading_path": ["Scope A"],
        "doc_order_index": 10,
        "raw_text": "A😀B",
        "sentences": [
            {
                "sentence_id": "C0100:S001",
                "raw_text": "A😀B",
                "normalized_text": "A😀B",
            }
        ],
    }


def test_create_paragraph_range_persists(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_paragraph_with_emoji_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0100", sentence_id="C0100:S001"),
        range={"start_offset": 1, "end_offset": 2},
    )
    assert created.range is not None
    assert created.range.start_offset == 1
    assert created.range.end_offset == 2


def test_range_end_equal_to_raw_text_length_accepted(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_paragraph_with_emoji_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0100", sentence_id="C0100:S001"),
        range={"start_offset": 0, "end_offset": 3},
    )
    assert created.range is not None
    assert created.range.end_offset == 3


def test_range_end_out_of_bounds_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_paragraph_with_emoji_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    with pytest.raises(SourceAnnotationValidationError, match="end_offset exceeds"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="C0100", sentence_id="C0100:S001"),
            range={"start_offset": 0, "end_offset": 99},
        )


def test_heading_range_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    heading = next(block for block in blocks if block["block_id"] == "C0001")
    heading["sentences"] = [
        {
            "sentence_id": "C0001:S001",
            "raw_text": heading["raw_text"],
            "normalized_text": heading["raw_text"],
        }
    ]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    with pytest.raises(SourceAnnotationValidationError, match="paragraph blocks"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="C0001", sentence_id="C0001:S001"),
            range={"start_offset": 0, "end_offset": 1},
        )


def test_table_range_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    blocks.append(
        {
            "block_id": "T0001",
            "kind": "table",
            "heading_path": ["Scope A"],
            "doc_order_index": 6,
            "raw_text": "A | B",
            "meta": {"raw_rows": [["A", "B"]]},
            "sentences": [
                {
                    "sentence_id": "T0001:S001",
                    "raw_text": "A | B",
                    "normalized_text": "A | B",
                }
            ],
        }
    )
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    with pytest.raises(SourceAnnotationValidationError, match="paragraph blocks"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="T0001", sentence_id="T0001:S001"),
            range={"start_offset": 0, "end_offset": 1},
        )


def test_list_item_range_rejected_in_v1(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    blocks.append(
        {
            "block_id": "C0020",
            "kind": "list_item",
            "heading_path": ["Scope A"],
            "doc_order_index": 7,
            "raw_text": "列表项",
            "sentences": [
                {
                    "sentence_id": "C0020:S001",
                    "raw_text": "列表项",
                    "normalized_text": "列表项",
                }
            ],
        }
    )
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    with pytest.raises(SourceAnnotationValidationError, match="paragraph blocks"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="C0020", sentence_id="C0020:S001"),
            range={"start_offset": 0, "end_offset": 1},
        )


def test_range_less_sentence_annotation_still_allowed_on_heading(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    heading = next(block for block in blocks if block["block_id"] == "C0001")
    heading["sentences"] = [
        {
            "sentence_id": "C0001:S001",
            "raw_text": heading["raw_text"],
            "normalized_text": heading["raw_text"],
        }
    ]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0001", sentence_id="C0001:S001"),
    )
    assert created.range is None


def test_unicode_code_point_range_resolves_emoji_slice(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_paragraph_with_emoji_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    extract_path = flow_root / "participants" / "source" / "extract" / "bundle.json"
    bundle = load_json(extract_path)
    raw_text = bundle["content_blocks"][-1]["sentences"][0]["raw_text"]
    assert raw_text[1:2] == "😀"
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0100", sentence_id="C0100:S001"),
        range={"start_offset": 1, "end_offset": 2},
    )
    assert raw_text[created.range.start_offset : created.range.end_offset] == "😀"


def test_range_validation_does_not_require_analysis_artifacts(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_paragraph_with_emoji_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    with patch(
        "application.document_consistency_qc.source_annotation.resolve_slot_extract_bundle",
        wraps=__import__(
            "application.document_consistency_qc.document_read",
            fromlist=["resolve_slot_extract_bundle"],
        ).resolve_slot_extract_bundle,
    ) as mocked:
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(block_id="C0100", sentence_id="C0100:S001"),
            range={"start_offset": 1, "end_offset": 2},
        )
    assert mocked.called


def _highlight_range_block() -> dict:
    return {
        "block_id": "C0101",
        "kind": "paragraph",
        "heading_path": ["Scope A"],
        "doc_order_index": 11,
        "raw_text": "感染性肺炎2例",
        "sentences": [
            {
                "sentence_id": "C0101:S001",
                "raw_text": "感染性肺炎2例",
                "normalized_text": "感染性肺炎2例",
            }
        ],
    }


def test_create_highlight_persists_kind_and_range(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0101", sentence_id="C0101:S001"),
        range={"start_offset": 0, "end_offset": 4},
        kind="highlight",
    )
    assert created.kind == "highlight"
    assert created.range is not None
    assert created.range.start_offset == 0
    assert created.range.end_offset == 4


def test_overlapping_highlight_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0101", sentence_id="C0101:S001")
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 1, "end_offset": 5},
        kind="highlight",
    )
    with pytest.raises(SourceAnnotationValidationError, match="overlaps"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=anchor,
            range={"start_offset": 3, "end_offset": 7},
            kind="highlight",
        )


def test_adjacent_highlight_accepted(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0101", sentence_id="C0101:S001")
    first = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 0, "end_offset": 2},
        kind="highlight",
    )
    second = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 2, "end_offset": 4},
        kind="highlight",
    )
    assert first.annotation_id != second.annotation_id


def test_exact_duplicate_highlight_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0101", sentence_id="C0101:S001")
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 1, "end_offset": 3},
        kind="highlight",
    )
    with pytest.raises(SourceAnnotationValidationError, match="overlaps"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=anchor,
            range={"start_offset": 1, "end_offset": 3},
            kind="highlight",
        )


def test_overlap_rule_only_applies_to_highlight_kind(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0101", sentence_id="C0101:S001")
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 1, "end_offset": 3},
    )
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 1, "end_offset": 3},
        kind="highlight",
    )
    assert created.kind == "highlight"


def test_create_range_comment_succeeds(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
        kind="comment",
        content="这里应改为80.0%",
        range={"start_offset": 0, "end_offset": 1},
    )
    assert created.kind == "comment"
    assert created.content == "这里应改为80.0%"
    assert created.range is not None
    assert created.range.start_offset == 0
    assert created.range.end_offset == 1
    assert created.annotation_id.startswith("ann_")


def test_create_comment_without_range_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    with pytest.raises(SourceAnnotationValidationError, match="range is required"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=_valid_anchor(),
            kind="comment",
            content="note",
        )


def test_second_non_overlapping_comment_on_same_sentence_succeeds(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_fixture(tmp_path)
    anchor = _valid_anchor()
    first = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="first",
        range={"start_offset": 0, "end_offset": 1},
    )
    second = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="second",
        range={"start_offset": 2, "end_offset": 3},
    )
    assert first.annotation_id != second.annotation_id


def test_overlapping_comment_range_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    anchor = _valid_anchor()
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="first",
        range={"start_offset": 1, "end_offset": 5},
    )
    with pytest.raises(SourceAnnotationValidationError, match="overlaps"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=anchor,
            kind="comment",
            content="second",
            range={"start_offset": 3, "end_offset": 8},
        )


def test_duplicate_comment_range_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    anchor = _valid_anchor()
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="first",
        range={"start_offset": 1, "end_offset": 4},
    )
    with pytest.raises(SourceAnnotationValidationError, match="overlaps"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=anchor,
            kind="comment",
            content="second",
            range={"start_offset": 1, "end_offset": 4},
        )


def test_adjacent_comment_ranges_allowed(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    anchor = _valid_anchor()
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="first",
        range={"start_offset": 1, "end_offset": 4},
    )
    second = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="second",
        range={"start_offset": 4, "end_offset": 8},
    )
    assert second.annotation_id.startswith("ann_")


def test_comment_and_highlight_on_same_sentence_allowed(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0101", sentence_id="C0101:S001")
    comment = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="确认后修改",
        range={"start_offset": 0, "end_offset": 2},
    )
    highlight = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 0, "end_offset": 4},
        kind="highlight",
    )
    assert comment.kind == "comment"
    assert highlight.kind == "highlight"


def test_edit_comment_content_succeeds(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
        kind="comment",
        content="first",
        range={"start_offset": 0, "end_offset": 1},
    )
    updated = update_source_annotation_content(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        annotation_id=created.annotation_id,
        content="second",
    )
    assert updated.content == "second"
    assert updated.kind == "comment"
    assert updated.range == created.range
    assert updated.created_at == created.created_at
    assert updated.updated_at
    assert updated.anchor == created.anchor


def test_highlight_cannot_use_comment_content_patch(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0101", sentence_id="C0101:S001"),
        range={"start_offset": 0, "end_offset": 4},
        kind="highlight",
    )
    with pytest.raises(SourceAnnotationValidationError, match="only comment"):
        update_source_annotation_content(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            annotation_id=created.annotation_id,
            content="nope",
        )


def test_delete_comment_does_not_delete_same_sentence_highlights(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_highlight_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0101", sentence_id="C0101:S001")
    comment = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="note",
        range={"start_offset": 0, "end_offset": 2},
    )
    highlight = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 0, "end_offset": 4},
        kind="highlight",
    )
    model = delete_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        annotation_id=comment.annotation_id,
    )
    remaining_ids = {entry.annotation_id for entry in model.annotations}
    assert remaining_ids == {highlight.annotation_id}


def test_review_state_unchanged_by_annotation_create(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        marked=True,
    )
    before = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(),
    )
    after = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    assert before.findings == after.findings


def _edit_range_block() -> dict:
    return {
        "block_id": "C0102",
        "kind": "paragraph",
        "sentences": [
            {
                "sentence_id": "C0102:S001",
                "raw_text": "ADR发生率为70.0%。",
            }
        ],
    }


def test_create_edit_succeeds(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0102", sentence_id="C0102:S001")
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="edit",
        range={"start_offset": 6, "end_offset": 11},
        replacement_text="80.0%",
    )
    assert created.kind == "edit"
    assert created.replacement_text == "80.0%"
    assert created.range is not None
    assert created.range.start_offset == 6
    assert created.range.end_offset == 11


def test_overlapping_edits_rejected(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0102", sentence_id="C0102:S001")
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="edit",
        range={"start_offset": 1, "end_offset": 5},
        replacement_text="A",
    )
    with pytest.raises(SourceAnnotationValidationError, match="overlaps"):
        create_source_annotation(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            anchor=anchor,
            kind="edit",
            range={"start_offset": 3, "end_offset": 8},
            replacement_text="B",
        )


def test_existing_edit_then_overlapping_comment_allowed(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0102", sentence_id="C0102:S001")
    edit = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="edit",
        range={"start_offset": 3, "end_offset": 6},
        replacement_text="80.0%",
    )
    comment = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="note",
        range={"start_offset": 1, "end_offset": 4},
    )
    assert edit.kind == "edit"
    assert comment.kind == "comment"


def test_existing_comment_then_overlapping_edit_allowed(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0102", sentence_id="C0102:S001")
    comment = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="note",
        range={"start_offset": 1, "end_offset": 4},
    )
    edit = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="edit",
        range={"start_offset": 3, "end_offset": 6},
        replacement_text="80.0%",
    )
    assert comment.kind == "comment"
    assert edit.kind == "edit"


def test_exact_overlap_comment_and_edit_allowed(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0102", sentence_id="C0102:S001")
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="edit",
        range={"start_offset": 6, "end_offset": 11},
        replacement_text="80.0%",
    )
    comment = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="note",
        range={"start_offset": 6, "end_offset": 11},
    )
    assert comment.range is not None
    assert comment.range.start_offset == 6
    assert comment.range.end_offset == 11


def test_disjoint_comment_and_edit_allowed(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    anchor = _valid_anchor(block_id="C0102", sentence_id="C0102:S001")
    comment = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="comment",
        content="note",
        range={"start_offset": 1, "end_offset": 4},
    )
    edit = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        kind="edit",
        range={"start_offset": 6, "end_offset": 11},
        replacement_text="80.0%",
    )
    assert comment.kind == "comment"
    assert edit.kind == "edit"


def test_update_edit_replacement_text_succeeds(tmp_path: Path) -> None:
    from application.document_consistency_qc.source_annotation import (
        update_source_annotation_replacement_text,
    )

    blocks = _default_extract_blocks() + [_edit_range_block()]
    flow_run_id = _write_fixture(tmp_path, extract_blocks=blocks)
    created = create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=_valid_anchor(block_id="C0102", sentence_id="C0102:S001"),
        kind="edit",
        range={"start_offset": 6, "end_offset": 11},
        replacement_text="80.0%",
    )
    updated = update_source_annotation_replacement_text(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        annotation_id=created.annotation_id,
        replacement_text="85.0%",
    )
    assert updated.replacement_text == "85.0%"
    assert updated.kind == "edit"
    assert updated.range == created.range
    assert updated.created_at == created.created_at
    assert updated.anchor == created.anchor


def test_delete_source_annotations_by_kind_scoped_to_doc_and_preserves_other_kinds(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_fixture(tmp_path)
    anchor = _valid_anchor()

    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 0, "end_offset": 1},
        kind="edit",
        replacement_text="80.0%",
    )
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 1, "end_offset": 2},
        kind="comment",
        content="note",
    )
    create_source_annotation(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        anchor=anchor,
        range={"start_offset": 2, "end_offset": 3},
        kind="highlight",
    )

    model = delete_source_annotations_by_kind(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        doc_id="doc_test",
        kind="edit",
    )

    kinds = sorted(entry.kind for entry in model.annotations)
    assert kinds == ["comment", "highlight"]
    assert len(model.annotations) == 2


def test_delete_source_annotations_by_kind_rejects_highlight_kind(tmp_path: Path) -> None:
    flow_run_id = _write_fixture(tmp_path)

    with pytest.raises(SourceAnnotationValidationError):
        delete_source_annotations_by_kind(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            doc_id="doc_test",
            kind="highlight",
        )
