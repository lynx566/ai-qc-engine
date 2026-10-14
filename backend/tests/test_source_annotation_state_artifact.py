"""Targeted tests for source annotation state artifact contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.source_annotation_state import (
    ANNOTATION_ID_PREFIX,
    SOURCE_ANNOTATION_KIND_COMMENT,
    SOURCE_ANNOTATION_KIND_EDIT,
    SOURCE_ANNOTATION_KIND_HIGHLIGHT,
    SOURCE_ANNOTATION_STATE_SCHEMA_VERSION,
    SOURCE_ANNOTATION_STATE_SCHEMA_VERSION_LEGACY,
    build_source_annotation_state_payload,
    generate_annotation_id,
    validate_source_annotation_content,
    validate_source_annotation_entry,
    validate_source_annotation_kind,
    validate_source_annotation_replacement_text,
    validate_source_annotation_state,
    validate_source_sentence_anchor,
    validate_source_text_range,
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


def test_valid_empty_artifact() -> None:
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={},
    )
    assert payload["annotations"] == {}


def test_valid_paragraph_sentence_anchor() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["annotations"][annotation_id]["anchor"]["sentence_id"] == "C0002:S001"


def test_valid_table_sentence_anchor() -> None:
    anchor = _valid_anchor(block_id="T0001", sentence_id="T0001:S001")
    validated = validate_source_sentence_anchor(anchor)
    assert validated["sentence_id"] == "T0001:S001"


def test_bare_comparison_alias_sentence_rejected() -> None:
    with pytest.raises(ValueError, match="bare comparison alias"):
        validate_source_sentence_anchor(_valid_anchor(sentence_id="T0001"))


def test_bare_h_and_u_aliases_rejected() -> None:
    with pytest.raises(ValueError, match="bare comparison alias"):
        validate_source_sentence_anchor(_valid_anchor(sentence_id="H0001"))
    with pytest.raises(ValueError, match="bare comparison alias"):
        validate_source_sentence_anchor(_valid_anchor(sentence_id="U0001"))


def test_annotation_map_key_mismatch_rejected() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="must match annotations map key"):
        validate_source_annotation_entry(
            {
                "annotation_id": "ann_other",
                "anchor": _valid_anchor(),
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )


def test_malformed_anchor_rejected() -> None:
    with pytest.raises(ValueError, match="slot_id is required"):
        validate_source_sentence_anchor(
            {
                "doc_id": "doc_test",
                "block_id": "C0002",
                "sentence_id": "C0002:S001",
            }
        )


def test_prefix_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="block prefix"):
        validate_source_sentence_anchor(
            _valid_anchor(block_id="C0002", sentence_id="C0003:S001")
        )


def test_generate_annotation_id_uses_opaque_prefix() -> None:
    annotation_id = generate_annotation_id()
    assert annotation_id.startswith(ANNOTATION_ID_PREFIX)
    assert len(annotation_id) > len(ANNOTATION_ID_PREFIX)


def test_validate_source_annotation_state_rejects_bad_artifact_type() -> None:
    with pytest.raises(ValueError, match="artifact_type mismatch"):
        validate_source_annotation_state(
            {
                "artifact_type": "wrong",
                "schema_version": SOURCE_ANNOTATION_STATE_SCHEMA_VERSION,
                "flow_run_id": "document_consistency_qc_test",
                "annotations": {},
            }
        )


def test_range_absent_annotation_remains_valid() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert "range" not in payload["annotations"][annotation_id]
    assert payload["schema_version"] == SOURCE_ANNOTATION_STATE_SCHEMA_VERSION


def test_valid_source_text_range() -> None:
    validated = validate_source_text_range({"start_offset": 0, "end_offset": 1})
    assert validated == {"start_offset": 0, "end_offset": 1}


def test_negative_start_offset_rejected() -> None:
    with pytest.raises(ValueError, match="start_offset must be >= 0"):
        validate_source_text_range({"start_offset": -1, "end_offset": 1})


def test_end_not_greater_than_start_rejected() -> None:
    with pytest.raises(ValueError, match="end_offset must be greater than start_offset"):
        validate_source_text_range({"start_offset": 3, "end_offset": 3})
    with pytest.raises(ValueError, match="end_offset must be greater than start_offset"):
        validate_source_text_range({"start_offset": 4, "end_offset": 2})


def test_non_int_offset_rejected() -> None:
    with pytest.raises(TypeError, match="start_offset must be an integer"):
        validate_source_text_range({"start_offset": "0", "end_offset": 1})
    with pytest.raises(TypeError, match="end_offset must be an integer"):
        validate_source_text_range({"start_offset": 0, "end_offset": 1.5})


def test_legacy_schema_version_still_reads() -> None:
    annotation_id = generate_annotation_id()
    payload = validate_source_annotation_state(
        {
            "artifact_type": "document_consistency_qc_source_annotation_state",
            "schema_version": SOURCE_ANNOTATION_STATE_SCHEMA_VERSION_LEGACY,
            "flow_run_id": "document_consistency_qc_test",
            "annotations": {
                annotation_id: {
                    "annotation_id": annotation_id,
                    "anchor": _valid_anchor(),
                    "created_at": "2026-09-13T00:00:00Z",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    assert payload["schema_version"] == SOURCE_ANNOTATION_STATE_SCHEMA_VERSION_LEGACY
    assert "range" not in payload["annotations"][annotation_id]


def test_legacy_0_2_annotation_without_kind_remains_readable() -> None:
    annotation_id = generate_annotation_id()
    payload = validate_source_annotation_state(
        {
            "artifact_type": "document_consistency_qc_source_annotation_state",
            "schema_version": "0.2.0",
            "flow_run_id": "document_consistency_qc_test",
            "annotations": {
                annotation_id: {
                    "annotation_id": annotation_id,
                    "anchor": _valid_anchor(),
                    "range": {"start_offset": 0, "end_offset": 1},
                    "created_at": "2026-09-13T00:00:00Z",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    assert "kind" not in payload["annotations"][annotation_id]


def test_highlight_annotation_requires_range() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="range is required when kind is highlight"):
        validate_source_annotation_entry(
            {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_HIGHLIGHT,
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValueError, match="kind must be one of"):
        validate_source_annotation_kind("suggested_edit")


def test_highlight_annotation_entry_valid() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_HIGHLIGHT,
                "range": {"start_offset": 1, "end_offset": 3},
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    entry = payload["annotations"][annotation_id]
    assert entry["kind"] == SOURCE_ANNOTATION_KIND_HIGHLIGHT
    assert payload["schema_version"] == SOURCE_ANNOTATION_STATE_SCHEMA_VERSION


def test_comment_annotation_entry_valid() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_COMMENT,
                "content": "这里应改为80.0%",
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    entry = payload["annotations"][annotation_id]
    assert entry["kind"] == SOURCE_ANNOTATION_KIND_COMMENT
    assert entry["content"] == "这里应改为80.0%"
    assert "range" not in entry
    assert payload["schema_version"] == SOURCE_ANNOTATION_STATE_SCHEMA_VERSION


def test_legacy_0_4_rangeless_comment_remains_readable() -> None:
    annotation_id = generate_annotation_id()
    payload = validate_source_annotation_state(
        {
            "artifact_type": "document_consistency_qc_source_annotation_state",
            "schema_version": "0.4.0",
            "flow_run_id": "document_consistency_qc_test",
            "annotations": {
                annotation_id: {
                    "annotation_id": annotation_id,
                    "anchor": _valid_anchor(),
                    "kind": SOURCE_ANNOTATION_KIND_COMMENT,
                    "content": "legacy note",
                    "created_at": "2026-09-13T00:00:00Z",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    entry = payload["annotations"][annotation_id]
    assert entry["kind"] == SOURCE_ANNOTATION_KIND_COMMENT
    assert "range" not in entry


def test_comment_with_range_valid() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_COMMENT,
                "content": "note",
                "range": {"start_offset": 0, "end_offset": 1},
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    entry = payload["annotations"][annotation_id]
    assert entry["kind"] == SOURCE_ANNOTATION_KIND_COMMENT
    assert entry["range"] == {"start_offset": 0, "end_offset": 1}
    assert payload["schema_version"] == SOURCE_ANNOTATION_STATE_SCHEMA_VERSION


def test_comment_without_content_rejected() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="content is required"):
        validate_source_annotation_entry(
            {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_COMMENT,
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )


def test_whitespace_only_comment_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty after trimming whitespace"):
        validate_source_annotation_content("   \n\t  ")


def test_highlight_with_comment_content_rejected() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="content must be absent when kind is highlight"):
        validate_source_annotation_entry(
            {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_HIGHLIGHT,
                "range": {"start_offset": 0, "end_offset": 1},
                "content": "note",
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )


def test_legacy_0_3_highlight_artifact_remains_readable() -> None:
    annotation_id = generate_annotation_id()
    payload = validate_source_annotation_state(
        {
            "artifact_type": "document_consistency_qc_source_annotation_state",
            "schema_version": "0.3.0",
            "flow_run_id": "document_consistency_qc_test",
            "annotations": {
                annotation_id: {
                    "annotation_id": annotation_id,
                    "anchor": _valid_anchor(),
                    "kind": SOURCE_ANNOTATION_KIND_HIGHLIGHT,
                    "range": {"start_offset": 1, "end_offset": 3},
                    "created_at": "2026-09-13T00:00:00Z",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    assert payload["annotations"][annotation_id]["kind"] == SOURCE_ANNOTATION_KIND_HIGHLIGHT


def test_annotation_entry_with_optional_range() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "range": {"start_offset": 2, "end_offset": 5},
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["annotations"][annotation_id]["range"] == {
        "start_offset": 2,
        "end_offset": 5,
    }


def test_edit_annotation_entry_valid() -> None:
    annotation_id = generate_annotation_id()
    payload = build_source_annotation_state_payload(
        flow_run_id="document_consistency_qc_test",
        annotations={
            annotation_id: {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_EDIT,
                "range": {"start_offset": 1, "end_offset": 3},
                "replacement_text": "80.0%",
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    entry = payload["annotations"][annotation_id]
    assert entry["kind"] == SOURCE_ANNOTATION_KIND_EDIT
    assert entry["replacement_text"] == "80.0%"
    assert payload["schema_version"] == SOURCE_ANNOTATION_STATE_SCHEMA_VERSION


def test_edit_without_range_rejected() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="range is required when kind is edit"):
        validate_source_annotation_entry(
            {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_EDIT,
                "replacement_text": "80.0%",
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )


def test_edit_with_empty_replacement_rejected() -> None:
    with pytest.raises(ValueError, match="replacement_text must be non-empty"):
        validate_source_annotation_replacement_text("   ")


def test_edit_with_content_rejected() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="content must be absent when kind is edit"):
        validate_source_annotation_entry(
            {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_EDIT,
                "range": {"start_offset": 1, "end_offset": 3},
                "replacement_text": "80.0%",
                "content": "note",
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )


def test_comment_with_replacement_text_rejected() -> None:
    annotation_id = generate_annotation_id()
    with pytest.raises(ValueError, match="replacement_text must be absent when kind is comment"):
        validate_source_annotation_entry(
            {
                "annotation_id": annotation_id,
                "anchor": _valid_anchor(),
                "kind": SOURCE_ANNOTATION_KIND_COMMENT,
                "content": "note",
                "range": {"start_offset": 0, "end_offset": 1},
                "replacement_text": "80.0%",
                "created_at": "2026-09-13T00:00:00Z",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            annotation_id=annotation_id,
        )
