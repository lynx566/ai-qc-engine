"""Clinical Result eligibility and orchestration for finding review."""

from __future__ import annotations

from pathlib import Path

from application.clinical_trial_doc_consistency_qc.result_read import (
    ResultReadError,
    ResultReadNotFoundError,
    load_document_consistency_qc_result,
)
from application.document_consistency_qc.finding_review import (
    FindingReviewError,
    FindingReviewNotFoundError,
    FindingReviewStateReadModel,
    FindingReviewValidationError,
    persist_finding_review_entry,
)
from application.document_consistency_qc.finding_review import (
    load_finding_review_state as load_review_artifact,
)

_UNSET = object()


class FindingReviewUnknownFindingError(FindingReviewValidationError):
    """Mutation targeted a finding that is not in the system result."""


class FindingReviewFlowNotReadableError(FindingReviewValidationError):
    """Flow exists but is not result-readable."""


def _build_finding_ids(*, project_root: Path, flow_run_id: str) -> set[str]:
    try:
        result = load_document_consistency_qc_result(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except ResultReadNotFoundError as exc:
        raise FindingReviewNotFoundError(str(exc)) from exc
    except ResultReadError as exc:
        raise FindingReviewFlowNotReadableError(str(exc)) from exc

    return {finding.finding_id for finding in result.findings}


def load_finding_review_state(
    *,
    project_root: Path,
    flow_run_id: str,
) -> FindingReviewStateReadModel:
    """Require a readable clinical Result before loading its review state."""

    _build_finding_ids(project_root=project_root, flow_run_id=flow_run_id)
    return load_review_artifact(project_root=project_root, flow_run_id=flow_run_id)


def patch_finding_review_entry(
    *,
    project_root: Path,
    flow_run_id: str,
    finding_id: str,
    decision: str | object = _UNSET,
    resolved: bool | object = _UNSET,
    marked: bool | object = _UNSET,
    note: str | None | object = _UNSET,
) -> FindingReviewStateReadModel:
    """Validate the clinical finding, then persist its Flow-owned review state."""

    if decision is _UNSET and resolved is _UNSET and marked is _UNSET and note is _UNSET:
        raise FindingReviewValidationError(
            "at least one of decision, resolved, marked, or note must be provided"
        )

    finding_ids = _build_finding_ids(project_root=project_root, flow_run_id=flow_run_id)
    if finding_id not in finding_ids:
        raise FindingReviewUnknownFindingError(
            f"finding_id {finding_id!r} is not present in the system result"
        )

    kwargs: dict[str, object] = {
        "project_root": project_root,
        "flow_run_id": flow_run_id,
        "finding_id": finding_id,
    }
    if decision is not _UNSET:
        kwargs["decision"] = decision
    if resolved is not _UNSET:
        kwargs["resolved"] = resolved
    if marked is not _UNSET:
        kwargs["marked"] = marked
    if note is not _UNSET:
        kwargs["note"] = note
    return persist_finding_review_entry(**kwargs)  # type: ignore[arg-type]


def set_finding_decision(
    *,
    project_root: Path,
    flow_run_id: str,
    finding_id: str,
    decision: str,
) -> FindingReviewStateReadModel:
    return patch_finding_review_entry(
        project_root=project_root,
        flow_run_id=flow_run_id,
        finding_id=finding_id,
        decision=decision,
    )


def set_finding_resolved(
    *,
    project_root: Path,
    flow_run_id: str,
    finding_id: str,
    resolved: bool,
) -> FindingReviewStateReadModel:
    return patch_finding_review_entry(
        project_root=project_root,
        flow_run_id=flow_run_id,
        finding_id=finding_id,
        resolved=resolved,
    )


def set_finding_marked(
    *,
    project_root: Path,
    flow_run_id: str,
    finding_id: str,
    marked: bool,
) -> FindingReviewStateReadModel:
    return patch_finding_review_entry(
        project_root=project_root,
        flow_run_id=flow_run_id,
        finding_id=finding_id,
        marked=marked,
    )


def update_finding_note(
    *,
    project_root: Path,
    flow_run_id: str,
    finding_id: str,
    note: str | None,
) -> FindingReviewStateReadModel:
    return patch_finding_review_entry(
        project_root=project_root,
        flow_run_id=flow_run_id,
        finding_id=finding_id,
        note=note,
    )


__all__ = [
    "FindingReviewError",
    "FindingReviewFlowNotReadableError",
    "FindingReviewNotFoundError",
    "FindingReviewUnknownFindingError",
    "FindingReviewValidationError",
    "load_finding_review_state",
    "patch_finding_review_entry",
    "set_finding_decision",
    "set_finding_marked",
    "set_finding_resolved",
    "update_finding_note",
]
