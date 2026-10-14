"""Product Task Start for installed clinical-trial Document Consistency QC."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from application.clinical_trial_doc_consistency_qc.execution import (
    execute_prepared_installed_clinical_trial_document_consistency_qc,
    prepare_and_allocate_installed_clinical_trial_document_consistency_qc,
)
from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)
from application.document_consistency_qc.create_flow_result import (
    DocumentConsistencyQcCreateFlowResult,
    build_document_consistency_qc_create_flow_result,
)
from application.document_consistency_qc.execution_request import (
    DocumentConsistencyQcExecutionRequest,
)
from application.document_consistency_qc.installation import (
    resolve_installed_project_root,
)
from application.task_lifecycle import append_task_lifecycle_event
from application.task_run import (
    allocate_task_run_id,
    attach_flow_run,
    create_task_run,
)
from execution_flow.document_consistency_qc import CandidateScopeDecisionMode
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)

from task.clinical_trial_doc_qc.product_source_admission import (
    ProductSourceAdmissionError,
    admit_product_task_sources,
)
from task.clinical_trial_doc_qc.start_resolution import (
    ResolvedInstalledTaskStart,
    resolve_installed_task_start,
)
from task.clinical_trial_doc_qc.task_input_binding import (
    bind_task_slot_values_to_flow_participants,
)


@dataclass(frozen=True, slots=True)
class PlannedProductTaskStart:
    """Product Task Start after intent validation and ``task_run_id`` allocation.

    ``slot_ids`` are Product Task input slot IDs (from ``ProductTaskDefinition``).
    """

    task_run_id: str
    task_id: str
    resolved: ResolvedInstalledTaskStart
    slot_ids: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "slot_ids",
            tuple(slot.slot_id for slot in self.resolved.task_definition.input_slots),
        )


@dataclass(frozen=True, slots=True)
class StartInstalledProductTaskResult:
    """Product Task Start outcome: TaskRun identity plus one child DCQC Flow result."""

    task_run_id: str
    child_flow: DocumentConsistencyQcCreateFlowResult


def product_task_start_result_to_mapping(
    result: StartInstalledProductTaskResult,
) -> dict[str, object]:
    """Serialize Product Task Start for public HTTP transport."""

    return {"task_run_id": result.task_run_id}


def start_installed_product_task_result_to_mapping(
    result: StartInstalledProductTaskResult,
) -> dict[str, object]:
    """Alias for the public Product Task Start HTTP projection."""

    return product_task_start_result_to_mapping(result)


def validate_installed_task_start_intent(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    task_id: str,
    upload_slot_ids: Collection[str],
) -> ResolvedInstalledTaskStart:
    """Validate Product Task Start slot keys against Product Task input topology."""

    resolved = resolve_installed_task_start(task_id, composition=composition)
    provided = set(upload_slot_ids)
    expected = {slot.slot_id for slot in resolved.task_definition.input_slots}
    missing = sorted(expected - provided)
    if missing:
        raise ValueError("missing upload for configured slot(s): " + ", ".join(missing))
    unexpected = sorted(provided - expected)
    if unexpected:
        raise ValueError("unexpected upload slot id(s): " + ", ".join(unexpected))
    return resolved


def plan_installed_product_task_start(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    task_id: str,
    upload_slot_ids: Collection[str],
) -> PlannedProductTaskStart:
    """Resolve installed task, validate Product slot keys, and allocate task_run_id."""

    resolved = validate_installed_task_start_intent(
        composition=composition,
        task_id=task_id,
        upload_slot_ids=upload_slot_ids,
    )
    task_run_id = allocate_task_run_id()
    return PlannedProductTaskStart(
        task_run_id=task_run_id,
        task_id=resolved.task_definition.task_id,
        resolved=resolved,
    )


def start_installed_product_task(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    planned: PlannedProductTaskStart,
    slot_inputs: Mapping[str, Path],
    source_language: str = "zh",
    participant_privacy_paths: Mapping[str, Path | None] | None = None,
    project_root: Path | None = None,
    projection_runtime_dependencies: (
        FilterOutputProjectionRuntimeDependencies | None
    ) = None,
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ) = None,
) -> StartInstalledProductTaskResult:
    """Execute a planned Product Task Start through the installed child DCQC Flow.

    ``slot_inputs`` and optional ``participant_privacy_paths`` are Task-keyed
    (Product Task input slot IDs). They are mapped to Flow participant slot IDs
    via ``planned.resolved.child_flow.input_bindings`` before building the DCQC
    execution request.
    """

    resolved = planned.resolved
    child_flow = resolved.child_flow
    task_id = resolved.task_definition.task_id
    if planned.task_id != task_id:
        raise ValueError("planned.task_id does not match planned.resolved task_id")
    if set(slot_inputs) != set(planned.slot_ids):
        raise ValueError(
            "slot_inputs do not match accepted plan: "
            f"expected {sorted(planned.slot_ids)!r}, got {sorted(slot_inputs)!r}"
        )
    expected_flow_id = child_flow.flow_id
    capability_config = child_flow.capability_config
    resolved_project_root = (
        project_root if project_root is not None else resolve_installed_project_root()
    )
    create_task_run(
        project_root=resolved_project_root,
        task_run_id=planned.task_run_id,
        task_id=task_id,
    )
    append_task_lifecycle_event(
        project_root=resolved_project_root,
        task_run_id=planned.task_run_id,
        event_type="input_admission_started",
    )

    try:
        task_slot_bindings = admit_product_task_sources(
            project_root=resolved_project_root,
            task_run_id=planned.task_run_id,
            task_slot_inputs=slot_inputs,
            slot_order=planned.slot_ids,
        )
    except ProductSourceAdmissionError as exc:
        append_task_lifecycle_event(
            project_root=resolved_project_root,
            task_run_id=planned.task_run_id,
            event_type="product_start_failed",
            failure_boundary=exc.failure_boundary,
            message=exc.safe_message,
        )
        raise
    append_task_lifecycle_event(
        project_root=resolved_project_root,
        task_run_id=planned.task_run_id,
        event_type="flow_allocation_started",
    )
    try:
        if participant_privacy_paths is not None:
            resolved_privacy_paths = bind_task_slot_values_to_flow_participants(
                task_slot_values=participant_privacy_paths,
                input_bindings=child_flow.input_bindings,
            )
        else:
            resolved_privacy_paths = {
                slot.slot_id: None for slot in capability_config.slots
            }
        participant_bindings = bind_task_slot_values_to_flow_participants(
            task_slot_values=task_slot_bindings,
            input_bindings=child_flow.input_bindings,
        )
        execution_request = DocumentConsistencyQcExecutionRequest(
            capability_id=child_flow.capability_id,
            project_root=resolved_project_root,
            participant_inputs=participant_bindings,
            participant_privacy_paths=resolved_privacy_paths,
            source_language=source_language,
            candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
        )
        prepared = prepare_and_allocate_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=execution_request,
            projection_runtime_dependencies=projection_runtime_dependencies,
            evidence_source_preparation_execution_dependencies=(
                evidence_source_preparation_execution_dependencies
            ),
        )
    except Exception:
        append_task_lifecycle_event(
            project_root=resolved_project_root,
            task_run_id=planned.task_run_id,
            event_type="product_start_failed",
            failure_boundary="flow_prepare_or_allocation",
            message="Flow preparation or allocation failed",
        )
        raise
    append_task_lifecycle_event(
        project_root=resolved_project_root,
        task_run_id=planned.task_run_id,
        event_type="flow_allocated",
        flow_id=prepared.flow_id,
        flow_run_id=prepared.flow_run_id,
    )
    if prepared.flow_id != expected_flow_id:
        append_task_lifecycle_event(
            project_root=resolved_project_root,
            task_run_id=planned.task_run_id,
            event_type="product_start_failed",
            failure_boundary="flow_prepare_or_allocation",
            message="Allocated Flow does not match the Product definition",
            flow_id=prepared.flow_id,
            flow_run_id=prepared.flow_run_id,
        )
        raise ValueError(
            f"flow_run allocated with flow_id {prepared.flow_id!r}, "
            f"expected resolved Start flow_id {expected_flow_id!r}"
        )
    try:
        attach_flow_run(
            project_root=resolved_project_root,
            task_run_id=planned.task_run_id,
            flow_id=prepared.flow_id,
            flow_run_id=prepared.flow_run_id,
        )
    except Exception:
        append_task_lifecycle_event(
            project_root=resolved_project_root,
            task_run_id=planned.task_run_id,
            event_type="product_start_failed",
            failure_boundary="membership_attach",
            message="Flow membership attachment failed",
            flow_id=prepared.flow_id,
            flow_run_id=prepared.flow_run_id,
        )
        raise
    append_task_lifecycle_event(
        project_root=resolved_project_root,
        task_run_id=planned.task_run_id,
        event_type="flow_execution_requested",
        flow_id=prepared.flow_id,
        flow_run_id=prepared.flow_run_id,
    )
    application_result = (
        execute_prepared_installed_clinical_trial_document_consistency_qc(prepared)
    )
    child_flow_result = build_document_consistency_qc_create_flow_result(
        application_result
    )
    return StartInstalledProductTaskResult(
        task_run_id=planned.task_run_id,
        child_flow=child_flow_result,
    )


__all__ = [
    "PlannedProductTaskStart",
    "StartInstalledProductTaskResult",
    "plan_installed_product_task_start",
    "product_task_start_result_to_mapping",
    "start_installed_product_task",
    "start_installed_product_task_result_to_mapping",
    "validate_installed_task_start_intent",
]
