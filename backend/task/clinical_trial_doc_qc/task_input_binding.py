"""Map Product Task-keyed inputs to child Flow participant keys at Start boundary."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypeVar

from task.clinical_trial_doc_qc.installation import TaskInputToFlowParticipantBinding

_T = TypeVar("_T")


def bind_task_slot_values_to_flow_participants(
    *,
    task_slot_values: Mapping[str, _T],
    input_bindings: tuple[TaskInputToFlowParticipantBinding, ...],
) -> dict[str, _T]:
    """Apply installed Task→participant bindings to a Task-keyed value map."""

    expected_task_slots = {binding.task_slot_id for binding in input_bindings}
    if set(task_slot_values) != expected_task_slots:
        raise ValueError(
            "task_slot_values keys must match binding task_slot_id set: "
            f"expected {sorted(expected_task_slots)!r}, "
            f"got {sorted(task_slot_values)!r}"
        )
    seen_participant_slots: set[str] = set()
    participant_values: dict[str, _T] = {}
    for binding in input_bindings:
        if binding.participant_slot_id in seen_participant_slots:
            raise ValueError(
                f"duplicate participant_slot_id in bindings: "
                f"{binding.participant_slot_id!r}"
            )
        participant_values[binding.participant_slot_id] = task_slot_values[
            binding.task_slot_id
        ]
        seen_participant_slots.add(binding.participant_slot_id)
    return participant_values


def bind_task_inputs_to_child_flow_participants(
    *,
    task_slot_inputs: Mapping[str, Path],
    input_bindings: tuple[TaskInputToFlowParticipantBinding, ...],
) -> dict[str, Path]:
    """Map Task-keyed upload paths to Flow-participant-keyed paths."""

    return bind_task_slot_values_to_flow_participants(
        task_slot_values=task_slot_inputs,
        input_bindings=input_bindings,
    )


__all__ = [
    "bind_task_inputs_to_child_flow_participants",
    "bind_task_slot_values_to_flow_participants",
]
