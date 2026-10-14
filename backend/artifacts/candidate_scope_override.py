# ruff: noqa: TRY004
"""Persisted ``candidate_scope_override.json`` contract for heading-level edits."""

from __future__ import annotations

from typing import Any, Literal

CANDIDATE_SCOPE_OVERRIDE_FILENAME = "candidate_scope_override.json"

CandidateScopeOperation = Literal["add", "remove"]
CANDIDATE_SCOPE_OPERATIONS = frozenset({"add", "remove"})


def assert_candidate_scope_override_safe(payload: dict[str, Any]) -> None:
    """Validate the thin heading-level override contract."""
    if not isinstance(payload, dict):
        raise ValueError("candidate_scope_override must be a mapping")

    doc_id = payload.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError("candidate_scope_override.doc_id must be a non-empty string")

    filter_job_id = payload.get("filter_job_id")
    if not isinstance(filter_job_id, str) or not filter_job_id.strip():
        raise ValueError(
            "candidate_scope_override.filter_job_id must be a non-empty string"
        )

    base_filter_run_id = payload.get("base_filter_run_id")
    if not isinstance(base_filter_run_id, str) or not base_filter_run_id.strip():
        raise ValueError(
            "candidate_scope_override.base_filter_run_id must be a non-empty string"
        )

    operations = payload.get("operations")
    if not isinstance(operations, list):
        raise ValueError("candidate_scope_override.operations must be a list")
    if not operations:
        raise ValueError("candidate_scope_override.operations must be non-empty")

    seen_anchors: set[str] = set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError(
                f"candidate_scope_override.operations[{index}] must be a mapping"
            )
        anchor_block_id = operation.get("anchor_block_id")
        if not isinstance(anchor_block_id, str) or not anchor_block_id.strip():
            raise ValueError(
                f"candidate_scope_override.operations[{index}].anchor_block_id "
                "must be a non-empty string"
            )
        anchor = anchor_block_id.strip()
        if anchor in seen_anchors:
            raise ValueError(
                f"duplicate candidate_scope_override operation for anchor_block_id "
                f"{anchor!r}"
            )
        seen_anchors.add(anchor)

        op = operation.get("op")
        if op not in CANDIDATE_SCOPE_OPERATIONS:
            raise ValueError(
                f"candidate_scope_override.operations[{index}].op must be one of "
                f"{sorted(CANDIDATE_SCOPE_OPERATIONS)!r}"
            )


def build_candidate_scope_override(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a validated override payload."""
    result = dict(payload)
    assert_candidate_scope_override_safe(result)
    return result


__all__ = [
    "CANDIDATE_SCOPE_OPERATIONS",
    "CANDIDATE_SCOPE_OVERRIDE_FILENAME",
    "CandidateScopeOperation",
    "assert_candidate_scope_override_safe",
    "build_candidate_scope_override",
]
