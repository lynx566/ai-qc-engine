"""Thin TaskRun page read transport for Document Consistency QC Product UI."""

from __future__ import annotations

from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import map_task_run_read_error
from task.clinical_trial_doc_qc.task_run_read import (
    TaskRunPageReadError,
    load_task_run_page_context,
    task_run_page_context_to_mapping,
)


def load_task_run_page_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    task_run_id: str,
) -> dict[str, object]:
    """Load one TaskRun page context for HTTP serialization."""

    project_root = config.project_root or config.default_workspace_root
    try:
        context = load_task_run_page_context(
            project_root=project_root,
            task_run_id=task_run_id,
        )
    except TaskRunPageReadError as exc:
        raise map_task_run_read_error(exc) from exc
    except (TypeError, ValueError) as exc:
        from bridge.document_consistency_qc.errors import (
            DocumentConsistencyQcBridgeValidationError,
        )

        raise DocumentConsistencyQcBridgeValidationError(str(exc)) from exc
    return task_run_page_context_to_mapping(context)


__all__ = [
    "load_task_run_page_request",
]
