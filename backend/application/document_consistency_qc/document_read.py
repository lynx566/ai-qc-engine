"""Runtime document read boundary for Document Consistency QC flows."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from execution_flow.document_consistency_qc.execution_provenance import (
    FlowRunExecution,
    FlowRunSlotProvenance,
    slot_participant_operation_output_dirs,
)
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    load_flow_run_execution,
)
from runtime.io import load_json

EXTRACT_BUNDLE_FILENAME = "bundle.json"


class DocumentReadError(Exception):
    """Base error for application document read."""


class DocumentReadNotFoundError(DocumentReadError):
    """Flow, slot, or extract artifact could not be located."""


class DocumentReadValidationError(DocumentReadError):
    """Request or artifact ownership validation failed."""


class DocumentReadIdentityError(DocumentReadValidationError):
    """Artifact belongs to a different flow, participant or document."""


def load_document_read_execution(
    *,
    project_root: Path,
    flow_run_id: str,
    require_doc_meta_bundle_reference: bool = True,
) -> FlowRunExecution:
    """Load persisted membership, without installed capability interpretation."""
    if not isinstance(flow_run_id, str) or not re.fullmatch(
        r"document_consistency_qc_[A-Za-z0-9_-]+", flow_run_id
    ):
        raise DocumentReadValidationError("invalid canonical flow_run_id")
    try:
        execution = load_flow_run_execution(
            project_root=project_root,
            flow_run_id=flow_run_id,
            require_doc_meta_bundle_reference=require_doc_meta_bundle_reference,
        )
    except FlowResumeError as exc:
        raise DocumentReadNotFoundError(str(exc)) from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise DocumentReadValidationError(str(exc)) from exc
    expected = (
        project_root
        / "runs/document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
    )
    if (
        execution.output_dir.resolve() != expected.absolute()
        or not expected.resolve().is_relative_to(project_root.resolve())
    ):
        raise DocumentReadIdentityError("flow path escapes requested project")
    slots = [slot.slot_id for slot in execution.slot_provenance]
    if len(slots) != len(set(slots)) or any(
        not re.fullmatch(r"[A-Za-z0-9_-]+", slot) for slot in slots
    ):
        raise DocumentReadIdentityError(
            "invalid or duplicate participant slot identity"
        )
    return execution


def _slot_provenance_for_request(
    execution: FlowRunExecution,
    *,
    slot_id: str,
) -> FlowRunSlotProvenance:
    try:
        return next(
            slot for slot in execution.slot_provenance if slot.slot_id == slot_id
        )
    except StopIteration:
        raise DocumentReadValidationError(
            f"slot_id {slot_id!r} is not configured for "
            f"flow_run_id={execution.flow_run_id!r}"
        ) from None


def resolve_slot_extract_bundle_path(
    *,
    execution: FlowRunExecution,
    slot_provenance: FlowRunSlotProvenance,
) -> Path:
    """Return canonical participant Extract bundle path for one flow slot."""

    extract_output_dir, _, _ = slot_participant_operation_output_dirs(
        flow_root=execution.output_dir,
        slot_id=slot_provenance.slot_id,
    )
    return extract_output_dir / EXTRACT_BUNDLE_FILENAME


def resolve_slot_extract_bundle(
    *,
    project_root: Path,
    flow_run_id: str,
    slot_id: str,
    require_doc_meta_bundle_reference: bool = True,
) -> dict[str, Any]:
    """Load persisted Extract Bundle for one flow participant slot."""

    execution = load_document_read_execution(
        project_root=project_root,
        flow_run_id=flow_run_id,
        require_doc_meta_bundle_reference=require_doc_meta_bundle_reference,
    )
    return resolve_slot_extract_bundle_for_execution(
        execution=execution, slot_id=slot_id
    )


def resolve_slot_extract_bundle_for_execution(
    *,
    execution: FlowRunExecution,
    slot_id: str,
) -> dict[str, Any]:
    """Same Extract boundary for callers reading several anchors in one flow."""
    flow_run_id = execution.flow_run_id

    slot_provenance = _slot_provenance_for_request(execution, slot_id=slot_id)

    extract_run_id = str(slot_provenance.extract_run_id or "").strip()
    if not extract_run_id:
        raise DocumentReadValidationError(
            f"slot {slot_id!r} has not completed Extract for "
            f"flow_run_id={flow_run_id!r}"
        )

    bundle_path = resolve_slot_extract_bundle_path(
        execution=execution,
        slot_provenance=slot_provenance,
    )
    if not bundle_path.resolve().is_relative_to(execution.output_dir.resolve()):
        raise DocumentReadIdentityError("Extract path escapes requested flow")
    if not bundle_path.is_file():
        raise DocumentReadNotFoundError(
            f"extract bundle is missing for slot {slot_id!r} in "
            f"flow_run_id={flow_run_id!r}"
        )

    try:
        bundle = load_json(bundle_path)
    except (ValueError, OSError) as exc:
        raise DocumentReadValidationError(f"invalid Extract bundle: {exc}") from exc
    if not isinstance(bundle, dict):
        raise DocumentReadValidationError("Extract bundle must be a mapping")

    provenance_doc_id = str(slot_provenance.doc_id or "").strip()
    if not provenance_doc_id:
        raise DocumentReadValidationError(
            f"slot {slot_id!r} provenance is missing doc_id for "
            f"flow_run_id={flow_run_id!r}"
        )

    bundle_doc_id = str(bundle.get("doc_id") or "").strip()
    if bundle_doc_id != provenance_doc_id:
        raise DocumentReadIdentityError(
            f"extract bundle doc_id {bundle_doc_id!r} does not match slot "
            f"provenance doc_id {provenance_doc_id!r}"
        )

    if (
        bundle.get("file_hash") is not None
        and bundle["file_hash"] != slot_provenance.file_hash
    ):
        raise DocumentReadIdentityError(
            "Extract file_hash does not match participant provenance"
        )

    return bundle


__all__ = [
    "EXTRACT_BUNDLE_FILENAME",
    "DocumentReadError",
    "DocumentReadNotFoundError",
    "DocumentReadValidationError",
    "DocumentReadIdentityError",
    "resolve_slot_extract_bundle",
    "resolve_slot_extract_bundle_path",
    "resolve_slot_extract_bundle_for_execution",
    "load_document_read_execution",
]
