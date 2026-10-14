"""Canonical Candidate Scope checkpoint decision artifact contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CANDIDATE_SCOPE_DECISION_FILENAME = "decision.json"
CANDIDATE_SCOPE_DECISION_ARTIFACT_TYPE = "document_consistency_qc_candidate_scope_decision"
CANDIDATE_SCOPE_DECISION_SCHEMA_VERSION = "0.2.0"
CANDIDATE_SCOPE_CHECKPOINT_KIND = "candidate_scope"

_RESOLUTION_KINDS = frozenset({"automatic_unchanged", "review_adjusted"})


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def validate_candidate_scope_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("artifact_type") != CANDIDATE_SCOPE_DECISION_ARTIFACT_TYPE:
        raise ValueError("candidate_scope_decision.artifact_type mismatch")
    if payload.get("schema_version") != CANDIDATE_SCOPE_DECISION_SCHEMA_VERSION:
        raise ValueError("candidate_scope_decision.schema_version mismatch")
    if payload.get("checkpoint_kind") != CANDIDATE_SCOPE_CHECKPOINT_KIND:
        raise ValueError("candidate_scope_decision.checkpoint_kind mismatch")

    flow_run_id = _require_str(payload.get("flow_run_id"), field="flow_run_id")
    slot_id = _require_str(payload.get("slot_id"), field="slot_id")
    decided_at = _require_str(payload.get("decided_at"), field="decided_at")

    filter_job_order = payload.get("filter_job_order")
    if not isinstance(filter_job_order, Sequence) or isinstance(
        filter_job_order, (str, bytes)
    ):
        raise ValueError("filter_job_order must be a sequence")
    ordered_job_ids = [
        _require_str(item, field=f"filter_job_order[{index}]")
        for index, item in enumerate(filter_job_order)
    ]
    if not ordered_job_ids:
        raise ValueError("filter_job_order must be non-empty")

    selections = payload.get("candidate_selections")
    if not isinstance(selections, Sequence) or isinstance(selections, (str, bytes)):
        raise ValueError("candidate_selections must be a sequence")
    if not selections:
        raise ValueError("candidate_selections must be non-empty")

    selection_by_job: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(selections):
        if not isinstance(entry, dict):
            raise ValueError(f"candidate_selections[{index}] must be an object")
        filter_job_id = _require_str(
            entry.get("filter_job_id"),
            field=f"candidate_selections[{index}].filter_job_id",
        )
        if filter_job_id in selection_by_job:
            raise ValueError(
                f"duplicate candidate_selections entry for filter_job_id={filter_job_id!r}"
            )
        anchor_ids = entry.get("anchor_block_ids")
        if not isinstance(anchor_ids, Sequence) or isinstance(anchor_ids, (str, bytes)):
            raise ValueError(
                f"candidate_selections[{index}].anchor_block_ids must be a sequence"
            )
        normalized_anchors = [
            _require_str(
                anchor,
                field=f"candidate_selections[{index}].anchor_block_ids[{anchor_index}]",
            )
            for anchor_index, anchor in enumerate(anchor_ids)
        ]
        resolved_bundle_ref = _require_str(
            entry.get("resolved_bundle_ref"),
            field=f"candidate_selections[{index}].resolved_bundle_ref",
        )
        resolution = entry.get("resolution")
        if not isinstance(resolution, dict):
            raise ValueError(f"candidate_selections[{index}].resolution is required")
        kind = _require_str(
            resolution.get("kind"),
            field=f"candidate_selections[{index}].resolution.kind",
        )
        if kind not in _RESOLUTION_KINDS:
            raise ValueError(
                f"candidate_selections[{index}].resolution.kind must be one of "
                f"{sorted(_RESOLUTION_KINDS)!r}"
            )
        upstream_bundle_ref = _require_str(
            resolution.get("upstream_bundle_ref"),
            field=(
                f"candidate_selections[{index}].resolution.upstream_bundle_ref"
            ),
        )
        selection_by_job[filter_job_id] = {
            "filter_job_id": filter_job_id,
            "anchor_block_ids": normalized_anchors,
            "resolved_bundle_ref": resolved_bundle_ref,
            "resolution": {
                "kind": kind,
                "upstream_bundle_ref": upstream_bundle_ref,
            },
        }

    if set(selection_by_job) != set(ordered_job_ids):
        raise ValueError(
            "candidate_selections filter_job_ids must match filter_job_order"
        )

    return {
        "artifact_type": CANDIDATE_SCOPE_DECISION_ARTIFACT_TYPE,
        "schema_version": CANDIDATE_SCOPE_DECISION_SCHEMA_VERSION,
        "checkpoint_kind": CANDIDATE_SCOPE_CHECKPOINT_KIND,
        "flow_run_id": flow_run_id,
        "slot_id": slot_id,
        "decided_at": decided_at,
        "filter_job_order": ordered_job_ids,
        "candidate_selections": [
            selection_by_job[filter_job_id] for filter_job_id in ordered_job_ids
        ],
    }


__all__ = [
    "CANDIDATE_SCOPE_CHECKPOINT_KIND",
    "CANDIDATE_SCOPE_DECISION_ARTIFACT_TYPE",
    "CANDIDATE_SCOPE_DECISION_FILENAME",
    "CANDIDATE_SCOPE_DECISION_SCHEMA_VERSION",
    "validate_candidate_scope_decision",
]
