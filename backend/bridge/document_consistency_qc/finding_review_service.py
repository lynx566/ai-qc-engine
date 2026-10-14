"""Thin finding review transport service for Document Consistency QC."""

from __future__ import annotations

from application.clinical_trial_doc_consistency_qc.finding_review import (
    FindingReviewError,
    load_finding_review_state,
    patch_finding_review_entry,
)
from application.document_consistency_qc.finding_review import finding_review_state_to_mapping
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import map_finding_review_error


def load_finding_review_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    try:
        model = load_finding_review_state(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except FindingReviewError as exc:
        raise map_finding_review_error(exc) from exc
    return finding_review_state_to_mapping(model)


def patch_finding_review_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
    finding_id: str,
    decision: str | None = None,
    resolved: bool | None = None,
    marked: bool | None = None,
    note: str | None | object = ...,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    kwargs: dict[str, object] = {
        "project_root": project_root,
        "flow_run_id": flow_run_id,
        "finding_id": finding_id,
    }
    if decision is not None:
        kwargs["decision"] = decision
    if resolved is not None:
        kwargs["resolved"] = resolved
    if marked is not None:
        kwargs["marked"] = marked
    if note is not ...:
        kwargs["note"] = note
    try:
        model = patch_finding_review_entry(**kwargs)  # type: ignore[arg-type]
    except FindingReviewError as exc:
        raise map_finding_review_error(exc) from exc
    return finding_review_state_to_mapping(model)


__all__ = [
    "load_finding_review_request",
    "patch_finding_review_request",
]
