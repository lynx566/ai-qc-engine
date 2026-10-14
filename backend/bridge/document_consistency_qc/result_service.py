"""Thin Result read transport service for Document Consistency QC."""

from __future__ import annotations

from application.clinical_trial_doc_consistency_qc.result_read import (
    ResultReadError,
    internal_result_read_model_to_mapping,
    load_document_consistency_qc_result,
)
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import map_result_read_error


def load_flow_result_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
) -> dict[str, object]:
    """Load one persisted internal Result read model for HTTP serialization."""

    project_root = config.project_root or config.default_workspace_root
    try:
        result = load_document_consistency_qc_result(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except ResultReadError as exc:
        raise map_result_read_error(exc) from exc
    return internal_result_read_model_to_mapping(result)


__all__ = [
    "load_flow_result_request",
]
