"""Product Task-owned source copy, Intake, and TaskInput persistence before DCQC."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from artifacts.task_input import (
    TaskInputEntry,
    build_task_input_entry_from_intake,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.request_file_intake import run_request_file_intake_operation

from task.clinical_trial_doc_qc.task_input import (
    materialize_task_input_source,
    persist_task_input,
    task_input_intake_dir,
    task_owned_source_ref,
)


class ProductSourceAdmissionError(Exception):
    """Safe Product boundary and message for a failed source admission."""

    def __init__(self, failure_boundary: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.failure_boundary = failure_boundary
        self.safe_message = safe_message


def admit_product_task_sources(
    *,
    project_root: Path,
    task_run_id: str,
    task_slot_inputs: Mapping[str, Path],
    slot_order: tuple[str, ...],
) -> dict[str, DocumentIntakeSourceBinding]:
    """Copy, Intake, and persist one complete TaskInput for all task slots.

    Raises on any copy, Intake, or persistence failure without starting DCQC.
    """

    if set(task_slot_inputs) != set(slot_order):
        raise ValueError("task_slot_inputs keys must match slot_order")

    bindings: dict[str, DocumentIntakeSourceBinding] = {}
    entries: list[TaskInputEntry] = []

    for task_slot_id in slot_order:
        staged_path = task_slot_inputs[task_slot_id]
        try:
            owned_path = materialize_task_input_source(
                project_root=project_root,
                task_run_id=task_run_id,
                task_slot_id=task_slot_id,
                source_path=staged_path,
            )
        except Exception as exc:
            raise ProductSourceAdmissionError(
                "source_materialization", "Source materialization failed"
            ) from exc
        try:
            intake_report = run_request_file_intake_operation(
                project_root=project_root,
                source_file=owned_path,
                output_dir=task_input_intake_dir(
                    project_root=project_root,
                    task_run_id=task_run_id,
                    task_slot_id=task_slot_id,
                ),
            )
            source_ref = task_owned_source_ref(
                project_root=project_root,
                destination_path=owned_path,
            )
            entry_record = build_task_input_entry_from_intake(
                task_slot_id=task_slot_id,
                source_ref=source_ref,
                request_file_intake_result=intake_report.result.request_file_intake_result,
            )
            entries.append(
                TaskInputEntry(
                    task_slot_id=entry_record["task_slot_id"],
                    file_hash=entry_record["file_hash"],
                    original_file_name=entry_record["original_file_name"],
                    source_ref=entry_record["source_ref"],
                )
            )
            binding = intake_report.result.source_binding
            if binding.source_path != owned_path.resolve():
                raise RuntimeError(
                    "Intake source binding path does not match Task-owned source path"
                )
            bindings[task_slot_id] = binding
        except Exception as exc:
            raise ProductSourceAdmissionError(
                "input_intake", "Input intake failed"
            ) from exc

    try:
        persist_task_input(
            project_root=project_root,
            task_run_id=task_run_id,
            inputs=tuple(entries),
        )
    except Exception as exc:
        raise ProductSourceAdmissionError(
            "task_input_persistence", "Task input persistence failed"
        ) from exc
    return bindings


__all__ = ["ProductSourceAdmissionError", "admit_product_task_sources"]
