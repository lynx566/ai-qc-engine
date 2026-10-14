"""Tests for Product Task-owned TaskInput application helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.task_run import create_task_run
from artifacts.task_input import TaskInputEntry
from core.document.doc_identity import compute_content_hash
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.io import save_json_atomic
from runtime.request_file_intake import run_request_file_intake_operation
from task.clinical_trial_doc_qc.product_source_admission import (
    ProductSourceAdmissionError,
    admit_product_task_sources,
)
from task.clinical_trial_doc_qc.task_input import (
    load_task_input_bindings,
    load_task_input_manifest,
    materialize_task_input_source,
    persist_task_input,
    resolve_task_input_source_path,
    task_input_intake_dir,
    task_input_manifest_path,
    task_input_source_dir,
    task_owned_source_ref,
)

TASK_RUN_ID = "task_run_20260920_010203_123456Z_slice2"
TASK_ID = "internal_dsur_qc"
SLOT_ID = "source"
CONTENT = b"task-owned-source-bytes"


@pytest.mark.parametrize(("function_name", "boundary"), [
    ("materialize_task_input_source", "source_materialization"),
    ("run_request_file_intake_operation", "input_intake"),
    ("persist_task_input", "task_input_persistence"),
])
def test_admission_classifies_product_failure(
    tmp_path: Path, function_name: str, boundary: str,
) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "source.docx"
    source.write_bytes(CONTENT)
    with patch(
        f"task.clinical_trial_doc_qc.product_source_admission.{function_name}",
        side_effect=OSError("private internal detail"),
    ), pytest.raises(ProductSourceAdmissionError) as caught:
        admit_product_task_sources(
            project_root=tmp_path, task_run_id=TASK_RUN_ID,
            task_slot_inputs={SLOT_ID: source}, slot_order=(SLOT_ID,),
        )
    assert caught.value.failure_boundary == boundary
    assert "private internal detail" not in caught.value.safe_message
    assert isinstance(caught.value.__cause__, OSError)


def test_second_slot_intake_failure_does_not_persist_partial_task_input(
    tmp_path: Path,
) -> None:
    _ensure_task_run(tmp_path)
    sample = (BACKEND_ROOT / "tests" / "fixtures" / "clinical_trial_doc" / "extract" / "ib_extract_minimal_001.docx")
    attempts = 0

    def intake_then_fail(**kwargs: object) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise OSError("second slot failed")
        return run_request_file_intake_operation(**kwargs)

    with (
        patch(
            "task.clinical_trial_doc_qc.product_source_admission.run_request_file_intake_operation",
            side_effect=intake_then_fail,
        ),
        pytest.raises(ProductSourceAdmissionError) as caught,
    ):
        admit_product_task_sources(
            project_root=tmp_path, task_run_id=TASK_RUN_ID,
            task_slot_inputs={"source": sample, "comparison": sample},
            slot_order=("source", "comparison"),
        )
    assert attempts == 2
    assert caught.value.failure_boundary == "input_intake"
    assert not task_input_manifest_path(
        project_root=tmp_path, task_run_id=TASK_RUN_ID,
    ).exists()


def _ensure_task_run(tmp_path: Path) -> None:
    create_task_run(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_id=TASK_ID,
    )


def _entry_for(tmp_path: Path, *, destination: Path) -> TaskInputEntry:
    source_ref = task_owned_source_ref(project_root=tmp_path, destination_path=destination)
    return TaskInputEntry(
        task_slot_id=SLOT_ID,
        file_hash=compute_content_hash(CONTENT),
        original_file_name=destination.name,
        source_ref=source_ref,
    )


def test_materialize_task_input_source_copies_bytes_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "staging" / "upload.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(CONTENT)

    with (
        patch(
            "steps.request_file_intake.run",
            side_effect=AssertionError("intake must not run"),
        ),
        patch(
            "core.document.doc_identity.compute_file_hash",
            side_effect=AssertionError("hash must not run"),
        ),
    ):
        destination = materialize_task_input_source(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            task_slot_id=SLOT_ID,
            source_path=source,
            original_file_name="source.docx",
        )

    assert destination == (
        tmp_path
        / "runs"
        / "task_runs"
        / TASK_RUN_ID
        / "inputs"
        / SLOT_ID
        / "source"
        / "source.docx"
    )
    assert destination.read_bytes() == CONTENT
    assert source.read_bytes() == CONTENT
    assert not task_input_manifest_path(project_root=tmp_path, task_run_id=TASK_RUN_ID).exists()


def test_materialize_task_input_source_rejects_existing_destination(tmp_path: Path) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)
    destination = materialize_task_input_source(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
        source_path=source,
    )
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_task_input_source(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            task_slot_id=SLOT_ID,
            source_path=source,
        )
    assert destination.read_bytes() == CONTENT
    assert source.read_bytes() == CONTENT


def test_materialize_rejects_escape_slot_and_filename(tmp_path: Path) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)
    with pytest.raises(ValueError, match="task_slot_id"):
        materialize_task_input_source(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            task_slot_id="../escape",
            source_path=source,
        )
    with pytest.raises(ValueError, match="original_file_name"):
        materialize_task_input_source(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            task_slot_id=SLOT_ID,
            source_path=source,
            original_file_name="../evil.docx",
        )


def test_persist_task_input_create_once_and_owner_validation(tmp_path: Path) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)
    destination = materialize_task_input_source(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
        source_path=source,
    )
    entry = _entry_for(tmp_path, destination=destination)
    path = persist_task_input(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        inputs=(entry,),
    )
    assert path == task_input_manifest_path(project_root=tmp_path, task_run_id=TASK_RUN_ID)
    reloaded = load_task_input_manifest(project_root=tmp_path, task_run_id=TASK_RUN_ID)
    assert reloaded["task_run_id"] == TASK_RUN_ID
    assert reloaded["inputs"] == [entry.to_record()]

    with pytest.raises(FileExistsError, match="task_input already exists"):
        persist_task_input(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            inputs=(entry,),
        )

    with pytest.raises(FileNotFoundError):
        persist_task_input(
            project_root=tmp_path,
            task_run_id="task_run_missing_owner_20260920_010203_123456Z",
            inputs=(entry,),
        )


def test_load_task_input_bindings_reconstructs_runtime_binding(tmp_path: Path) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)
    destination = materialize_task_input_source(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
        source_path=source,
    )
    entry = _entry_for(tmp_path, destination=destination)
    persist_task_input(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        inputs=(entry,),
    )

    bindings = load_task_input_bindings(project_root=tmp_path, task_run_id=TASK_RUN_ID)
    assert bindings[SLOT_ID] == DocumentIntakeSourceBinding(
        file_hash=entry.file_hash,
        original_file_name="upload.docx",
        source_path=destination.resolve(),
    )


def test_load_task_input_bindings_rejects_missing_source_and_escape(tmp_path: Path) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)
    destination = materialize_task_input_source(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
        source_path=source,
    )
    entry = _entry_for(tmp_path, destination=destination)
    persist_task_input(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        inputs=(entry,),
    )
    destination.unlink()
    with pytest.raises(ValueError, match="regular file"):
        load_task_input_bindings(project_root=tmp_path, task_run_id=TASK_RUN_ID)

    with pytest.raises(ValueError, match="parent traversal"):
        resolve_task_input_source_path(
            project_root=tmp_path,
            source_ref="../../outside.docx",
        )


def test_task_input_intake_dir_helper_is_stable(tmp_path: Path) -> None:
    intake_dir = task_input_intake_dir(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
    )
    source_dir = task_input_source_dir(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
    )
    assert intake_dir == source_dir.parent / "intake"
    assert source_dir.as_posix().endswith(f"/inputs/{SLOT_ID}/source")


@pytest.mark.parametrize("location", ["other_task", "other_slot", "elsewhere"])
def test_persist_task_input_rejects_source_outside_canonical_owner_layout(
    tmp_path: Path,
    location: str,
) -> None:
    _ensure_task_run(tmp_path)
    if location == "other_task":
        other_task_run_id = f"{TASK_RUN_ID}_other"
        create_task_run(
            project_root=tmp_path,
            task_run_id=other_task_run_id,
            task_id=TASK_ID,
        )
        destination = task_input_source_dir(
            project_root=tmp_path,
            task_run_id=other_task_run_id,
            task_slot_id=SLOT_ID,
        ) / "source.docx"
    elif location == "other_slot":
        destination = task_input_source_dir(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            task_slot_id="other_slot",
        ) / "source.docx"
    else:
        destination = tmp_path / "elsewhere" / "source.docx"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(CONTENT)

    with pytest.raises(ValueError, match="canonical Task-owned source_ref"):
        persist_task_input(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            inputs=(_entry_for(tmp_path, destination=destination),),
        )


@pytest.mark.parametrize("source_kind", ["missing", "directory"])
def test_persist_task_input_requires_regular_canonical_source(
    tmp_path: Path,
    source_kind: str,
) -> None:
    _ensure_task_run(tmp_path)
    destination = task_input_source_dir(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
    ) / "source.docx"
    if source_kind == "directory":
        destination.mkdir(parents=True)
    entry = _entry_for(tmp_path, destination=destination)

    with pytest.raises(ValueError, match="regular file"):
        persist_task_input(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            inputs=(entry,),
        )


def test_reload_rejects_tampered_non_owned_source_ref(tmp_path: Path) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)
    destination = materialize_task_input_source(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
        source_path=source,
    )
    entry = _entry_for(tmp_path, destination=destination)
    persist_task_input(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        inputs=(entry,),
    )
    outside = tmp_path / "elsewhere" / "source.docx"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(CONTENT)
    manifest = load_task_input_manifest(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
    )
    manifest["inputs"][0]["source_ref"] = task_owned_source_ref(
        project_root=tmp_path,
        destination_path=outside,
    )
    save_json_atomic(
        task_input_manifest_path(project_root=tmp_path, task_run_id=TASK_RUN_ID),
        manifest,
    )

    with pytest.raises(ValueError, match="canonical Task-owned source_ref"):
        load_task_input_bindings(project_root=tmp_path, task_run_id=TASK_RUN_ID)


def test_materialize_copy_failure_leaves_no_partial_destination_or_temp(
    tmp_path: Path,
) -> None:
    _ensure_task_run(tmp_path)
    source = tmp_path / "upload.docx"
    source.write_bytes(CONTENT)

    def _partial_copy_then_fail(_source: Path, destination: Path) -> None:
        Path(destination).write_bytes(b"partial")
        raise OSError("copy failed")

    with (
        patch(
            "task.clinical_trial_doc_qc.task_input.shutil.copy2",
            side_effect=_partial_copy_then_fail,
        ),
        pytest.raises(OSError, match="copy failed"),
    ):
        materialize_task_input_source(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
            task_slot_id=SLOT_ID,
            source_path=source,
        )

    source_dir = task_input_source_dir(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_slot_id=SLOT_ID,
    )
    assert not (source_dir / source.name).exists()
    assert list(source_dir.iterdir()) == []
    assert source.read_bytes() == CONTENT
