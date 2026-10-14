"""Tests for the neutral persisted TaskInput artifact contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.task_input import (
    TASK_INPUT_SCHEMA_VERSION,
    TaskInputEntry,
    build_task_input_entry,
    build_task_input_entry_from_intake,
    build_task_input_manifest,
    validate_task_input_manifest,
    validate_task_input_source_ref,
)
from core.document.doc_identity import compute_content_hash

_VALID_HASH = compute_content_hash(b"task-input-test")
_SOURCE_REF = "runs/task_runs/task_run_20260920_010203_123456Z/inputs/source/source.docx"


def _manifest(*, inputs: object, task_run_id: str = "task_run_20260920_010203_123456Z") -> dict:
    return {
        "artifact_type": "task_input",
        "schema_version": TASK_INPUT_SCHEMA_VERSION,
        "task_run_id": task_run_id,
        "inputs": inputs,
    }


def _entry(**overrides: str) -> dict[str, str]:
    base = {
        "task_slot_id": "source",
        "file_hash": _VALID_HASH,
        "original_file_name": "source.docx",
        "source_ref": _SOURCE_REF,
    }
    base.update(overrides)
    return base


def test_task_input_manifest_single_and_multi_slot() -> None:
    single = build_task_input_manifest(
        task_run_id="task_run_20260920_010203_123456Z",
        inputs=(
            TaskInputEntry(
                task_slot_id="source",
                file_hash=_VALID_HASH,
                original_file_name="source.docx",
                source_ref=_SOURCE_REF,
            ),
        ),
    )
    validate_task_input_manifest(single)

    multi = build_task_input_manifest(
        task_run_id="task_run_20260920_010203_123456Z",
        inputs=(
            TaskInputEntry(
                task_slot_id="source_a",
                file_hash=_VALID_HASH,
                original_file_name="a.docx",
                source_ref="runs/task_runs/task_run_20260920_010203_123456Z/inputs/source_a/source/a.docx",
            ),
            TaskInputEntry(
                task_slot_id="source_b",
                file_hash=compute_content_hash(b"b"),
                original_file_name="b.docx",
                source_ref="runs/task_runs/task_run_20260920_010203_123456Z/inputs/source_b/source/b.docx",
            ),
        ),
    )
    validate_task_input_manifest(multi)
    assert [entry["task_slot_id"] for entry in multi["inputs"]] == [
        "source_a",
        "source_b",
    ]


def test_task_input_rejects_duplicate_task_slot_id() -> None:
    with pytest.raises(ValueError, match="duplicate task_slot_id"):
        validate_task_input_manifest(
            _manifest(
                inputs=[
                    _entry(task_slot_id="source"),
                    _entry(
                        task_slot_id="source",
                        original_file_name="other.docx",
                        source_ref="runs/task_runs/task_run_20260920_010203_123456Z/inputs/source/other.docx",
                    ),
                ]
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_type", "task_run"),
        ("schema_version", "0.2.0"),
        ("task_run_id", "../escape"),
        ("inputs", []),
    ],
)
def test_task_input_rejects_invalid_root(field: str, value: object) -> None:
    manifest = _manifest(inputs=[_entry()])
    manifest[field] = value
    with pytest.raises(ValueError):
        validate_task_input_manifest(manifest)


def test_task_input_rejects_unknown_root_and_entry_fields() -> None:
    root_extra = _manifest(inputs=[_entry()])
    root_extra["status"] = "ready"
    with pytest.raises(ValueError, match="unexpected keys"):
        validate_task_input_manifest(root_extra)

    entry_extra = _manifest(inputs=[{**_entry(), "doc_id": "doc_x"}])
    with pytest.raises(ValueError, match="unexpected keys"):
        validate_task_input_manifest(entry_extra)


@pytest.mark.parametrize(
    "source_ref",
    [
        "/absolute/path.docx",
        "C:/absolute/path.docx",
        "../outside.docx",
        "runs/../escape.docx",
    ],
)
def test_task_input_rejects_unsafe_source_ref(source_ref: str) -> None:
    with pytest.raises(ValueError, match="source_ref"):
        validate_task_input_source_ref(source_ref)


def test_task_input_entry_validation_rejects_invalid_facts() -> None:
    with pytest.raises(ValueError, match="file_hash"):
        build_task_input_entry(
            task_slot_id="source",
            file_hash="bad",
            original_file_name="source.docx",
            source_ref=_SOURCE_REF,
        )
    with pytest.raises(ValueError, match="original_file_name"):
        build_task_input_entry(
            task_slot_id="source",
            file_hash=_VALID_HASH,
            original_file_name="../source.docx",
            source_ref=_SOURCE_REF,
        )


def test_build_task_input_entry_from_intake_uses_neutral_facts() -> None:
    intake_result = {
        "artifact_type": "request_file_intake_result",
        "schema_version": "0.2.0",
        "document": {
            "file_hash": _VALID_HASH,
            "original_file_name": "from_intake.docx",
        },
    }
    entry = build_task_input_entry_from_intake(
        task_slot_id="source",
        source_ref=_SOURCE_REF,
        request_file_intake_result=intake_result,
    )
    assert entry == {
        "task_slot_id": "source",
        "file_hash": _VALID_HASH,
        "original_file_name": "from_intake.docx",
        "source_ref": _SOURCE_REF,
    }
