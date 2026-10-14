"""Product TaskRun page read projection for installed clinical-trial tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from application.clinical_trial_doc_consistency_qc.result_readiness import probe_result_readiness
from application.task_run import load_task_run
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    validate_flow_run_summary,
)
from artifacts.task_lifecycle import load_task_lifecycle_manifest
from runtime.io import load_json

from task.clinical_trial_doc_qc.presentation import PRODUCT_TASK_PRESENTATION_BY_ID
from task.clinical_trial_doc_qc.task_input import (
    load_task_input_manifest,
    task_input_manifest_path,
)


class TaskRunPageReadError(Exception):
    """Base class for TaskRun page read failures."""


class TaskRunPageReadNotFoundError(TaskRunPageReadError):
    """Raised when the requested TaskRun artifact does not exist."""


class TaskRunPageReadUnknownTaskIdError(TaskRunPageReadError):
    """Raised when a persisted TaskRun references an unknown installed task_id."""


@dataclass(frozen=True, slots=True)
class TaskRunFlowRefRecord:
    flow_id: str
    flow_run_id: str


@dataclass(frozen=True, slots=True)
class ProductTaskRunState:
    input_ready: bool
    product_phase: str
    product_failure: dict[str, str] | None
    allocated_flow: TaskRunFlowRefRecord | None
    flow_outcome: str
    requires_user_action: bool | None
    result_available: bool


@dataclass(frozen=True, slots=True)
class TaskRunPageContext:
    task_run_id: str
    task_id: str
    display_name: str
    flow_runs: tuple[TaskRunFlowRefRecord, ...]
    state: ProductTaskRunState


def _project_state(
    *, project_root: Path, task_run_id: str,
    flow_runs: tuple[TaskRunFlowRefRecord, ...],
) -> ProductTaskRunState:
    input_path = task_input_manifest_path(
        project_root=project_root, task_run_id=task_run_id,
    )
    input_ready = input_path.exists()
    if input_ready:
        load_task_input_manifest(project_root=project_root, task_run_id=task_run_id)
    journal = load_task_lifecycle_manifest(
        project_root=project_root, task_run_id=task_run_id,
    )
    phase = "flow_allocated" if flow_runs else "unknown"
    allocated: TaskRunFlowRefRecord | None = None
    failure: dict[str, str] | None = None
    if journal is not None:
        phase = "unknown"
        for event in journal["events"]:
            kind = event["event_type"]
            if kind == "input_admission_started":
                phase = "input_admission"
            elif kind == "flow_allocation_started":
                phase = "flow_allocation"
            elif kind == "flow_allocated":
                phase = "flow_allocated"
                allocated = TaskRunFlowRefRecord(
                    flow_id=event["flow_id"], flow_run_id=event["flow_run_id"],
                )
            elif kind == "flow_execution_requested":
                phase = "flow_execution_requested"
            elif kind == "product_start_failed":
                failure = {"boundary": event["failure_boundary"],
                           "message": event["message"]}
        if flow_runs and (allocated is None or allocated not in flow_runs):
            raise ValueError("journal allocation contradicts TaskRun membership")
        if phase == "flow_execution_requested" and not flow_runs:
            raise ValueError("execution request has no TaskRun child membership")

    outcome = "unknown"
    action: bool | None = None
    result_available = False
    if len(flow_runs) > 1:
        raise ValueError("TaskRun has multiple child Flows without a selection rule")
    if flow_runs:
        child = flow_runs[0]
        prefix = "document_consistency_qc_"
        if child.flow_id != "document_consistency_qc" or not child.flow_run_id.startswith(prefix):
            raise ValueError("TaskRun child is not a DCQC Flow")
        session = child.flow_run_id.removeprefix(prefix)
        if not session or not all(char.isalnum() or char == "_" for char in session):
            raise ValueError("TaskRun child flow_run_id is malformed")
        summary_path = (project_root / "runs" / "document_consistency_qc" / session
                        / FLOW_RUN_SUMMARY_FILENAME)
        if summary_path.exists():
            summary = load_json(summary_path)
            # Page identity/state does not depend on advisory document metadata.
            # Execution, resume and Result readers retain their strict defaults.
            validate_flow_run_summary(summary, require_doc_meta_bundle_reference=False)
            if summary["flow_run_id"] != child.flow_run_id:
                raise ValueError("Flow summary identity contradicts TaskRun membership")
            outcome = summary["status"]
            action = outcome == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE
            if not action and all(slot.get("doc_meta_bundle_path") for slot in summary["slots"]):
                result_available = probe_result_readiness(
                    project_root=project_root,
                    flow_run_id=child.flow_run_id,
                    summary=summary,
                )
    return ProductTaskRunState(
        input_ready=input_ready, product_phase=phase, product_failure=failure,
        allocated_flow=allocated, flow_outcome=outcome,
        requires_user_action=action, result_available=result_available,
    )


def load_task_run_page_context(
    *,
    project_root: Path,
    task_run_id: str,
) -> TaskRunPageContext:
    """Load Task page root context and child Flow membership from a persisted TaskRun."""

    try:
        manifest = load_task_run(project_root=project_root, task_run_id=task_run_id)
    except FileNotFoundError as exc:
        raise TaskRunPageReadNotFoundError(
            f"task_run not found: {task_run_id}"
        ) from exc

    task_id = str(manifest["task_id"])
    presentation = PRODUCT_TASK_PRESENTATION_BY_ID.get(task_id)
    if presentation is None:
        raise TaskRunPageReadUnknownTaskIdError(
            f"task_run references unknown installed task_id: {task_id}"
        )

    flow_runs_raw = manifest["flow_runs"]
    if not isinstance(flow_runs_raw, list):
        raise TypeError("flow_runs must be an array")

    flow_runs = tuple(
        TaskRunFlowRefRecord(
            flow_id=str(item["flow_id"]),
            flow_run_id=str(item["flow_run_id"]),
        )
        for item in flow_runs_raw
    )

    return TaskRunPageContext(
        task_run_id=str(manifest["task_run_id"]),
        task_id=task_id,
        display_name=presentation.display_name,
        flow_runs=flow_runs,
        state=_project_state(
            project_root=project_root, task_run_id=task_run_id,
            flow_runs=flow_runs,
        ),
    )


def task_run_page_context_to_mapping(context: TaskRunPageContext) -> dict[str, object]:
    """Serialize one TaskRun page context for HTTP transport."""

    return {
        "task_run_id": context.task_run_id,
        "task_id": context.task_id,
        "display_name": context.display_name,
        "flow_runs": [
            {
                "flow_id": flow_run.flow_id,
                "flow_run_id": flow_run.flow_run_id,
            }
            for flow_run in context.flow_runs
        ],
        "state": {
            "input_ready": context.state.input_ready,
            "product_phase": context.state.product_phase,
            "product_failure": context.state.product_failure,
            "allocated_flow": (
                {"flow_id": context.state.allocated_flow.flow_id,
                 "flow_run_id": context.state.allocated_flow.flow_run_id}
                if context.state.allocated_flow is not None else None
            ),
            "flow_outcome": context.state.flow_outcome,
            "requires_user_action": context.state.requires_user_action,
            "result_available": context.state.result_available,
        },
    }


__all__ = [
    "TaskRunFlowRefRecord",
    "TaskRunPageContext",
    "TaskRunPageReadError",
    "TaskRunPageReadNotFoundError",
    "TaskRunPageReadUnknownTaskIdError",
    "load_task_run_page_context",
    "task_run_page_context_to_mapping",
]
