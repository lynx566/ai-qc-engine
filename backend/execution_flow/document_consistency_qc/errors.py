"""Operational execution errors for Document Consistency QC flows."""

from __future__ import annotations

from pathlib import Path

from execution_flow.document_consistency_qc.execution_provenance import (
    FlowRunExecution,
    persist_flow_run_summary_best_effort,
    resolve_flow_status,
)


class DocumentConsistencyQcFlowExecutionError(Exception):
    """Post-allocation flow failure that preserves canonical flow identity."""

    def __init__(
        self,
        message: str,
        *,
        flow_run_id: str,
        flow_run_summary_path: Path,
    ) -> None:
        super().__init__(message)
        self.flow_run_id = flow_run_id
        self.flow_run_summary_path = flow_run_summary_path


def reraise_post_allocation_flow_execution_failure(
    execution: FlowRunExecution,
    exc: BaseException,
) -> None:
    """Persist best-effort flow summary, then raise with allocated flow identity."""

    flow_status = resolve_flow_status(execution.slot_provenance)
    persist_flow_run_summary_best_effort(execution, status=flow_status)
    raise DocumentConsistencyQcFlowExecutionError(
        str(exc),
        flow_run_id=execution.flow_run_id,
        flow_run_summary_path=execution.flow_run_summary_path,
    ) from exc


__all__ = [
    "DocumentConsistencyQcFlowExecutionError",
    "reraise_post_allocation_flow_execution_failure",
]
