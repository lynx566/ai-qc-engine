"""Installed Product Tasks and explicit Task input → Flow participant bindings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from artifacts.document_consistency_qc_flow_run_summary import (
    DOCUMENT_CONSISTENCY_QC_FLOW_ID,
)
from capability.clinical_trial_doc_consistency_qc import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
)
from execution_flow.document_consistency_qc import DocumentConsistencyQcCapabilityConfig

from .definitions import PRODUCT_TASK_DEFINITION_BY_ID, ProductTaskDefinition
from .task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
)


@dataclass(frozen=True, slots=True)
class TaskInputToFlowParticipantBinding:
    """Maps one Product Task input slot to one child Flow participant slot."""

    task_slot_id: str
    participant_slot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.task_slot_id, str) or not self.task_slot_id.strip():
            raise ValueError("task_slot_id must be a non-empty string")
        if (
            not isinstance(self.participant_slot_id, str)
            or not self.participant_slot_id.strip()
        ):
            raise ValueError("participant_slot_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class InstalledChildFlowBinding:
    """One installed child Flow and how Task inputs feed its participants."""

    flow_id: str
    capability_id: str
    input_bindings: tuple[TaskInputToFlowParticipantBinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.flow_id, str) or not self.flow_id.strip():
            raise ValueError("flow_id must be a non-empty string")
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class InstalledProductTask:
    """Canonical installed Product Task with one child Flow binding."""

    task_id: str
    child_flow: InstalledChildFlowBinding

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string")


_INSTALLED_PRODUCT_TASKS: tuple[InstalledProductTask, ...] = (
    InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    ),
    InstalledProductTask(
        task_id=INTERNAL_IB_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_ib",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    ),
    InstalledProductTask(
        task_id=INTERNAL_CSR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_csr",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    ),
    InstalledProductTask(
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="dsur_updated_ib",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_a",
                    participant_slot_id="source_a",
                ),
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_b",
                    participant_slot_id="source_b",
                ),
            ),
        ),
    ),
)


def _validate_installed_product_task_tuple(
    tasks: Sequence[InstalledProductTask],
) -> None:
    task_ids = [task.task_id for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("installed Product Task task_id values must be unique")


def validate_installed_product_task_installation(
    task: InstalledProductTask,
    *,
    product_task_definitions: Mapping[str, ProductTaskDefinition],
    installed_dcqc_capabilities: Mapping[str, DocumentConsistencyQcCapabilityConfig],
) -> None:
    """Validate one installed Task against Product definitions and DCQC participant slots."""

    try:
        definition = product_task_definitions[task.task_id]
    except KeyError as exc:
        raise ValueError(
            f"installed Product Task references unknown task_id: {task.task_id!r}"
        ) from exc

    child = task.child_flow
    if child.flow_id != DOCUMENT_CONSISTENCY_QC_FLOW_ID:
        raise ValueError(
            f"installed Product Task {task.task_id!r} references unsupported "
            f"child flow_id: {child.flow_id!r}"
        )
    try:
        capability_config = installed_dcqc_capabilities[child.capability_id]
    except KeyError as exc:
        raise ValueError(
            f"installed Product Task {task.task_id!r} references unknown "
            f"capability_id: {child.capability_id!r}"
        ) from exc

    task_slot_ids = {slot.slot_id for slot in definition.input_slots}
    participant_slot_ids = {slot.slot_id for slot in capability_config.slots}

    seen_task_slots: set[str] = set()
    seen_participant_slots: set[str] = set()
    for binding in child.input_bindings:
        if binding.task_slot_id not in task_slot_ids:
            raise ValueError(
                f"installed Product Task {task.task_id!r} binding references "
                f"unknown task_slot_id: {binding.task_slot_id!r}"
            )
        if binding.participant_slot_id not in participant_slot_ids:
            raise ValueError(
                f"installed Product Task {task.task_id!r} binding references "
                f"unknown participant_slot_id: {binding.participant_slot_id!r}"
            )
        if binding.task_slot_id in seen_task_slots:
            raise ValueError(
                f"duplicate task_slot_id binding for installed Product Task "
                f"{task.task_id!r}: {binding.task_slot_id!r}"
            )
        if binding.participant_slot_id in seen_participant_slots:
            raise ValueError(
                f"duplicate participant_slot_id binding for installed Product Task "
                f"{task.task_id!r}: {binding.participant_slot_id!r}"
            )
        seen_task_slots.add(binding.task_slot_id)
        seen_participant_slots.add(binding.participant_slot_id)

    missing_task_slots = task_slot_ids - seen_task_slots
    if missing_task_slots:
        raise ValueError(
            f"installed Product Task {task.task_id!r} missing bindings for "
            f"task input slots: {sorted(missing_task_slots)!r}"
        )
    missing_participant_slots = participant_slot_ids - seen_participant_slots
    if missing_participant_slots:
        raise ValueError(
            f"installed Product Task {task.task_id!r} missing bindings for "
            f"DCQC participant slots: {sorted(missing_participant_slots)!r}"
        )


def validate_installed_product_task_installations(
    *,
    installed_tasks: Sequence[InstalledProductTask],
    product_task_definitions: Mapping[str, ProductTaskDefinition],
    installed_dcqc_capabilities: Mapping[str, DocumentConsistencyQcCapabilityConfig],
) -> None:
    """Validate the full installed Product Task registry."""

    _validate_installed_product_task_tuple(installed_tasks)
    for task in installed_tasks:
        validate_installed_product_task_installation(
            task,
            product_task_definitions=product_task_definitions,
            installed_dcqc_capabilities=installed_dcqc_capabilities,
        )


_INSTALLED_DCQC_CAPABILITIES_FOR_VALIDATION: Mapping[
    str, DocumentConsistencyQcCapabilityConfig
] = MappingProxyType(
    {
        INTERNAL_DSUR_CONSISTENCY_QC.capability_id: INTERNAL_DSUR_CONSISTENCY_QC,
        INTERNAL_IB_CONSISTENCY_QC.capability_id: INTERNAL_IB_CONSISTENCY_QC,
        INTERNAL_CSR_CONSISTENCY_QC.capability_id: INTERNAL_CSR_CONSISTENCY_QC,
        DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id: DSUR_UPDATED_IB_CONSISTENCY_QC,
    }
)

validate_installed_product_task_installations(
    installed_tasks=_INSTALLED_PRODUCT_TASKS,
    product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
    installed_dcqc_capabilities=_INSTALLED_DCQC_CAPABILITIES_FOR_VALIDATION,
)

INSTALLED_PRODUCT_TASKS: tuple[InstalledProductTask, ...] = _INSTALLED_PRODUCT_TASKS

INSTALLED_PRODUCT_TASK_BY_ID: Mapping[str, InstalledProductTask] = MappingProxyType(
    {task.task_id: task for task in INSTALLED_PRODUCT_TASKS}
)

__all__ = [
    "INSTALLED_PRODUCT_TASKS",
    "INSTALLED_PRODUCT_TASK_BY_ID",
    "InstalledChildFlowBinding",
    "InstalledProductTask",
    "TaskInputToFlowParticipantBinding",
    "validate_installed_product_task_installation",
    "validate_installed_product_task_installations",
]
