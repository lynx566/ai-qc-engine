"""Process-level application composition boundaries."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from application.document_consistency_qc.composition import (
        DocumentConsistencyQcApplicationComposition,
    )


def __getattr__(name: str):
    """Keep existing exports without loading business code for pure models."""
    if name in {
        "allocate_task_run_id",
        "attach_flow_run",
        "create_task_run",
        "create_task_run_for_flow",
        "load_task_run",
    }:
        module = "application.task_run"
    elif name == "DocumentConsistencyQcApplicationComposition":
        module = "application.document_consistency_qc.composition"
    elif name == "build_clinical_trial_doc_consistency_qc_application_composition":
        module = "application.clinical_trial_doc_consistency_qc"
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value


def build_installed_document_consistency_qc_application_composition() -> (
    DocumentConsistencyQcApplicationComposition
):
    """Build the application composition installed for this process."""

    builder = getattr(
        import_module(__name__),
        "build_clinical_trial_doc_consistency_qc_application_composition",
    )
    return builder()


__all__ = [
    "allocate_task_run_id",
    "attach_flow_run",
    "build_installed_document_consistency_qc_application_composition",
    "create_task_run",
    "create_task_run_for_flow",
    "load_task_run",
]
