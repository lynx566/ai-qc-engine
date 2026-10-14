"""Build candidate-scope view models from canonical artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS,
)
from application.document_consistency_qc.candidate_scope_read import (
    load_persisted_candidate_scope_decision,
)
from application.document_consistency_qc.document_read import DocumentReadError
from bridge.candidate_scope.canonical_context import PausedSlotViewContext
from bridge.candidate_scope.errors import CandidateScopeValidationError
from bridge.candidate_scope.schemas import (
    CandidateHeadingState,
    CandidateScopeFilterJobState,
    CandidateScopeSlotStateResponse,
)
from bridge.candidate_scope.selection_ops import (
    anchor_ids_from_zone_bundle,
)
from core.document.structure.headings import get_heading_level, is_heading
from execution_flow.document_consistency_qc.candidate_scope_selection import (
    build_review_heading_ownership,
)
from runtime.io import load_json


def _require_doc_order_index(block: dict[str, Any], *, anchor: str) -> int:
    value = block.get("doc_order_index")
    if not isinstance(value, int) or value < 0:
        raise CandidateScopeValidationError(
            f"heading block {anchor!r} missing valid doc_order_index"
        )
    return value


def _heading_title(block: dict[str, Any]) -> str:
    analysis_text = block.get("analysis_text")
    if isinstance(analysis_text, str) and analysis_text.strip():
        return analysis_text.strip()
    text = block.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return str(block.get("block_id") or "")


def _build_heading_catalog(
    analysis_bundle: dict[str, Any],
    *,
    review_heading_ownership: Mapping[str, str],
) -> list[CandidateHeadingState]:
    doc_id = str(analysis_bundle.get("doc_id") or "")
    catalog: list[CandidateHeadingState] = []

    for block in analysis_bundle.get("content_blocks") or []:
        if not isinstance(block, dict) or not is_heading(block):
            continue
        anchor = str(block.get("block_id") or "").strip()
        if not anchor:
            continue
        level = get_heading_level(block)
        if level is None:
            continue
        heading_path = block.get("heading_path")
        path = (
            [str(item) for item in heading_path]
            if isinstance(heading_path, list)
            else []
        )

        filter_job_id = review_heading_ownership.get(anchor)
        if filter_job_id is None:
            continue

        catalog.append(
            CandidateHeadingState(
                doc_id=doc_id,
                filter_job_id=filter_job_id,
                anchor_block_id=anchor,
                title=_heading_title(block),
                heading_path=path,
                level=int(level),
                doc_order_index=_require_doc_order_index(block, anchor=anchor),
            )
        )

    catalog.sort(key=lambda item: item.doc_order_index)
    return catalog


def _current_anchors_by_job_from_decision(
    decision_path: Path,
    *,
    context: PausedSlotViewContext,
) -> dict[str, set[str]]:
    try:
        decision = load_persisted_candidate_scope_decision(
            decision_path=decision_path,
            flow_run_id=context.flow_run_id,
            slot_id=context.slot_id,
            filter_job_ids=tuple(job.filter_job_id for job in context.filter_jobs),
        )
    except DocumentReadError as exc:
        raise CandidateScopeValidationError(str(exc)) from exc
    return {
        selection["filter_job_id"]: set(selection["anchor_block_ids"])
        for selection in decision["candidate_selections"]
    }


def build_candidate_scope_slot_state(
    *,
    context: PausedSlotViewContext,
    decision_path: Path | None = None,
) -> CandidateScopeSlotStateResponse:
    automatic_by_job: dict[str, set[str]] = {}
    for job in context.filter_jobs:
        automatic_bundle = load_json(job.zone_match_bundle_path)
        automatic_ids = set(anchor_ids_from_zone_bundle(automatic_bundle))
        automatic_by_job[job.filter_job_id] = automatic_ids

    analysis_bundle = load_json(context.analysis_bundle_path)
    manual_default = INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS.get(
        (context.capability_id, context.slot_id)
    )
    review_heading_ownership = build_review_heading_ownership(
        automatic_by_job,
        analysis_bundle=analysis_bundle,
        manual_default_filter_job_id=manual_default,
    )

    automatic_all = sorted(
        {anchor for anchors in automatic_by_job.values() for anchor in anchors}
    )
    if decision_path is not None:
        current_by_job = _current_anchors_by_job_from_decision(
            decision_path, context=context
        )
        if set(current_by_job) != set(automatic_by_job):
            raise CandidateScopeValidationError(
                "candidate scope decision filter jobs do not match installed filter jobs"
            )
    else:
        current_by_job = automatic_by_job

    current_all = sorted(
        {anchor for anchors in current_by_job.values() for anchor in anchors}
    )

    headings = _build_heading_catalog(
        analysis_bundle,
        review_heading_ownership=review_heading_ownership,
    )

    filter_jobs = [
        CandidateScopeFilterJobState(
            filter_job_id=job.filter_job_id,
            automatic_anchor_block_ids=sorted(automatic_by_job[job.filter_job_id]),
            current_anchor_block_ids=sorted(current_by_job[job.filter_job_id]),
        )
        for job in context.filter_jobs
    ]

    return CandidateScopeSlotStateResponse(
        slot_id=context.slot_id,
        doc_id=context.doc_id,
        filter_jobs=filter_jobs,
        automatic_anchor_block_ids=automatic_all,
        current_anchor_block_ids=current_all,
        headings=headings,
    )


__all__ = [
    "_build_heading_catalog",
    "build_candidate_scope_slot_state",
]
