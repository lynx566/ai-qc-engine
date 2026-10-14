"""Persisted Candidate Scope reading. No installed configuration or UI state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from application.document_consistency_qc.document_read import (
    DocumentReadIdentityError,
    DocumentReadNotFoundError,
    DocumentReadValidationError,
    load_document_read_execution,
)
from artifacts.candidate_scope_decision import (
    CANDIDATE_SCOPE_DECISION_FILENAME,
    validate_candidate_scope_decision,
)
from artifacts.effective_candidate_scope import RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
from artifacts.zone_match_bundle import assert_zone_match_bundle_safe
from core.document.structure.headings import is_heading
from runtime.io import load_json


@dataclass(frozen=True, slots=True)
class FinalCandidateScopeSelection:
    flow_run_id: str
    slot_id: str
    doc_id: str
    filter_job_id: str
    persisted_decision_at: str
    automatic_anchor_block_ids: tuple[str, ...]
    effective_anchor_block_ids: tuple[str, ...]
    added_anchor_block_ids: tuple[str, ...]
    removed_anchor_block_ids: tuple[str, ...]


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DocumentReadNotFoundError(f"persisted artifact missing: {path}")
    try:
        payload = load_json(path)
    except (ValueError, OSError) as exc:
        raise DocumentReadValidationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DocumentReadValidationError(f"artifact must be a mapping: {path}")
    return payload


def load_persisted_candidate_scope_decision(
    *,
    decision_path: Path,
    flow_run_id: str,
    slot_id: str,
    filter_job_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Shared Setup/report decision validation against persisted membership."""
    try:
        decision = validate_candidate_scope_decision(_read(decision_path))
    except (ValueError, TypeError, KeyError) as exc:
        raise DocumentReadValidationError(str(exc)) from exc
    if decision["flow_run_id"] != flow_run_id or decision["slot_id"] != slot_id:
        raise DocumentReadIdentityError(
            "candidate scope decision flow/slot does not match request"
        )
    if tuple(decision["filter_job_order"]) != filter_job_ids:
        raise DocumentReadIdentityError(
            "decision filter job order does not match persisted provenance"
        )
    for selection in decision["candidate_selections"]:
        ids = selection["anchor_block_ids"]
        if len(ids) != len(set(ids)):
            raise DocumentReadValidationError("duplicate persisted selection anchor")
    return decision


def _owned_path(value: str | None, expected: Path, *, project_root: Path) -> Path:
    if not value:
        raise DocumentReadValidationError("missing persisted artifact reference")
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    if path.resolve() != expected.absolute() or not expected.resolve().is_relative_to(
        project_root.resolve()
    ):
        raise DocumentReadIdentityError(
            f"artifact reference does not belong to requested flow/slot/job: {value}"
        )
    return path


def _anchors(bundle: dict[str, Any], *, doc_id: str, job: Any) -> set[str]:
    try:
        assert_zone_match_bundle_safe(bundle)
    except (ValueError, TypeError, KeyError) as exc:
        raise DocumentReadValidationError(str(exc)) from exc
    for field, expected in (
        ("doc_id", doc_id),
        ("zone_config_name", job.zone_config_name),
        ("zone_config_version", job.zone_config_version),
        ("language", job.source_language),
    ):
        if bundle.get(field) != expected:
            raise DocumentReadIdentityError(
                f"zone bundle {field} does not match persisted provenance"
            )
    ids = []
    for zone in bundle["matched_zones"]:
        anchor = (zone.get("match") or {}).get("matched_heading_block_id")
        if not isinstance(anchor, str) or not anchor.strip():
            raise DocumentReadValidationError("zone missing canonical heading anchor")
        ids.append(anchor)
    if len(ids) != len(set(ids)):
        raise DocumentReadValidationError("duplicate zone heading anchor")
    return set(ids)


def load_final_candidate_scope_configuration(
    *,
    project_root: Path,
    flow_run_id: str,
) -> tuple[FinalCandidateScopeSelection, ...]:
    """Read final slot × job selections; missing final decisions fail explicitly.

    Resolved bundles and decision anchors are the already-normalized persisted
    result. We never replay selection operations or today's ownership rules.
    """
    execution = load_document_read_execution(
        project_root=project_root, flow_run_id=flow_run_id
    )
    rows = []
    for slot in execution.slot_provenance:
        slot_root = execution.output_dir / "participants" / slot.slot_id
        scope_root = slot_root / "candidate_scope"
        decision_path = _owned_path(
            slot.candidate_scope_decision_path,
            scope_root / CANDIDATE_SCOPE_DECISION_FILENAME,
            project_root=project_root,
        )
        jobs = {job.filter_job_id: job for job in slot.filter_jobs}
        if (
            len(jobs) != len(slot.filter_jobs)
            or set(jobs) != set(slot.filter_job_ids)
            or not jobs
        ):
            raise DocumentReadIdentityError("invalid persisted filter job membership")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+", job_id) for job_id in jobs):
            raise DocumentReadValidationError("invalid persisted filter job identity")
        decision = load_persisted_candidate_scope_decision(
            decision_path=decision_path,
            flow_run_id=flow_run_id,
            slot_id=slot.slot_id,
            filter_job_ids=slot.filter_job_ids,
        )
        analysis_path = _owned_path(
            slot.analysis_bundle_path,
            slot_root / "prepare_analysis/analysis_bundle.json",
            project_root=project_root,
        )
        analysis = _read(analysis_path)
        if not slot.doc_id or analysis.get("doc_id") != slot.doc_id:
            raise DocumentReadIdentityError(
                "analysis document does not match participant"
            )
        order = {}
        headings = set()
        for block in analysis.get("content_blocks") or []:
            block_id = block.get("block_id")
            if block_id in order:
                raise DocumentReadValidationError("duplicate analysis block identity")
            order[block_id] = block.get("doc_order_index")
            if is_heading(block):
                headings.add(block_id)
        selections = {
            row["filter_job_id"]: row for row in decision["candidate_selections"]
        }
        for job_id in slot.filter_job_ids:
            job = jobs[job_id]
            selection = selections[job_id]
            auto_expected = slot_root / "filter" / job_id / "zone_match_bundle.json"
            auto_path = _owned_path(
                job.zone_match_bundle_path, auto_expected, project_root=project_root
            )
            _owned_path(
                selection["resolution"]["upstream_bundle_ref"],
                auto_expected,
                project_root=project_root,
            )
            resolved_path = _owned_path(
                selection["resolved_bundle_ref"],
                scope_root / job_id / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME,
                project_root=project_root,
            )
            auto_bundle, final_bundle = _read(auto_path), _read(resolved_path)
            for bundle in (auto_bundle, final_bundle):
                if bundle.get("file_hash") != slot.file_hash:
                    raise DocumentReadIdentityError(
                        "zone bundle file_hash does not match participant"
                    )
            automatic = _anchors(auto_bundle, doc_id=slot.doc_id, job=job)
            effective = _anchors(final_bundle, doc_id=slot.doc_id, job=job)
            if effective != set(selection["anchor_block_ids"]):
                raise DocumentReadValidationError(
                    "decision anchors do not match persisted resolved bundle"
                )
            for block_id in automatic | effective:
                value = order.get(block_id)
                if (
                    block_id not in headings
                    or isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    raise DocumentReadValidationError(
                        f"anchor {block_id} missing persisted document order"
                    )

            def ordered(ids: set[str]) -> tuple[str, ...]:
                return tuple(sorted(ids, key=lambda key: (order[key], key)))

            rows.append(
                FinalCandidateScopeSelection(
                    flow_run_id,
                    slot.slot_id,
                    slot.doc_id,
                    job_id,
                    decision["decided_at"],
                    ordered(automatic),
                    ordered(effective),
                    ordered(effective - automatic),
                    ordered(automatic - effective),
                )
            )
    return tuple(rows)
