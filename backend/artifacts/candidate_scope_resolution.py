"""Candidate Scope resolution input contract (flow checkpoint; allows zero operations)."""

from __future__ import annotations

from typing import Any

from artifacts.candidate_scope_override import CANDIDATE_SCOPE_OPERATIONS


def assert_candidate_scope_resolution_input_safe(payload: dict[str, Any]) -> None:
    """Validate resolution input for canonical Candidate Scope materialization."""
    if not isinstance(payload, dict):
        raise ValueError("candidate_scope_resolution_input must be a mapping")

    doc_id = payload.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError(
            "candidate_scope_resolution_input.doc_id must be a non-empty string"
        )

    filter_job_id = payload.get("filter_job_id")
    if not isinstance(filter_job_id, str) or not filter_job_id.strip():
        raise ValueError(
            "candidate_scope_resolution_input.filter_job_id must be a non-empty string"
        )

    base_filter_run_id = payload.get("base_filter_run_id")
    if not isinstance(base_filter_run_id, str) or not base_filter_run_id.strip():
        raise ValueError(
            "candidate_scope_resolution_input.base_filter_run_id must be a non-empty string"
        )

    operations = payload.get("operations")
    if not isinstance(operations, list):
        raise ValueError("candidate_scope_resolution_input.operations must be a list")

    seen_anchors: set[str] = set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError(
                f"candidate_scope_resolution_input.operations[{index}] must be a mapping"
            )
        anchor_block_id = operation.get("anchor_block_id")
        if not isinstance(anchor_block_id, str) or not anchor_block_id.strip():
            raise ValueError(
                f"candidate_scope_resolution_input.operations[{index}].anchor_block_id "
                "must be a non-empty string"
            )
        anchor = anchor_block_id.strip()
        if anchor in seen_anchors:
            raise ValueError(
                f"duplicate candidate_scope_resolution_input operation for "
                f"anchor_block_id {anchor!r}"
            )
        seen_anchors.add(anchor)

        op = operation.get("op")
        if op not in CANDIDATE_SCOPE_OPERATIONS:
            raise ValueError(
                f"candidate_scope_resolution_input.operations[{index}].op must be one of "
                f"{sorted(CANDIDATE_SCOPE_OPERATIONS)!r}"
            )


__all__ = ["assert_candidate_scope_resolution_input_safe"]
