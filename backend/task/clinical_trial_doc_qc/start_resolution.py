"""Resolve Product Task Start into installed child Flow execution context."""

from __future__ import annotations

from dataclasses import dataclass

from artifacts.document_consistency_qc_flow_run_summary import (
    DOCUMENT_CONSISTENCY_QC_FLOW_ID,
)
from execution_flow.document_consistency_qc import DocumentConsistencyQcCapabilityConfig
from task.clinical_trial_doc_qc.definitions import (
    PRODUCT_TASK_DEFINITION_BY_ID,
    ProductTaskDefinition,
)
from task.clinical_trial_doc_qc.installation import (
    INSTALLED_PRODUCT_TASK_BY_ID,
    TaskInputToFlowParticipantBinding,
)

from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)

DOCUMENT_CONSISTENCY_QC_INSTALLED_FLOW_ID: str = DOCUMENT_CONSISTENCY_QC_FLOW_ID


@dataclass(frozen=True, slots=True)
class ResolvedInstalledChildFlow:
    """Installed child Flow binding resolved for execution."""

    flow_id: str
    capability_id: str
    capability_config: DocumentConsistencyQcCapabilityConfig
    input_bindings: tuple[TaskInputToFlowParticipantBinding, ...]


@dataclass(frozen=True, slots=True)
class ResolvedInstalledTaskStart:
    """Product Task Start resolved to installed child Flow execution context."""

    task_definition: ProductTaskDefinition
    child_flow: ResolvedInstalledChildFlow


def resolve_installed_task_start(
    task_id: str,
    *,
    composition: DocumentConsistencyQcApplicationComposition,
) -> ResolvedInstalledTaskStart:
    """Look up Product Task definition, installation binding, and DCQC capability config."""

    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")
    normalized_task_id = task_id.strip()
    try:
        installed_task = INSTALLED_PRODUCT_TASK_BY_ID[normalized_task_id]
    except KeyError:
        raise ValueError(f"unsupported task_id: {normalized_task_id}") from None
    try:
        task_definition = PRODUCT_TASK_DEFINITION_BY_ID[normalized_task_id]
    except KeyError as exc:
        raise ValueError(
            f"installed product task {normalized_task_id!r} has no "
            f"ProductTaskDefinition"
        ) from exc

    child_binding = installed_task.child_flow
    flow_id = child_binding.flow_id
    if flow_id != DOCUMENT_CONSISTENCY_QC_INSTALLED_FLOW_ID:
        raise ValueError(
            f"installed product task {normalized_task_id!r} is bound to flow_id "
            f"{flow_id!r}, which is not executable by this installation"
        )

    capability_id = child_binding.capability_id
    try:
        capability_config = composition.capabilities[capability_id]
    except KeyError as exc:
        raise ValueError(
            f"installed product task {normalized_task_id!r} references missing "
            f"capability_id {capability_id!r} in composition"
        ) from exc

    return ResolvedInstalledTaskStart(
        task_definition=task_definition,
        child_flow=ResolvedInstalledChildFlow(
            flow_id=flow_id,
            capability_id=capability_id,
            capability_config=capability_config,
            input_bindings=child_binding.input_bindings,
        ),
    )


__all__ = [
    "DOCUMENT_CONSISTENCY_QC_INSTALLED_FLOW_ID",
    "ResolvedInstalledChildFlow",
    "ResolvedInstalledTaskStart",
    "resolve_installed_task_start",
]
