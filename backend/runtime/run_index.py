"""Session- or output-local index.json for human-readable run navigation (not pipeline data)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from artifacts.prepare_analysis import ANALYSIS_BUNDLE_FILENAME
from artifacts.request_file_intake import REQUEST_FILE_INTAKE_RESULT_FILENAME
from runtime.io import load_json, save_json
from runtime.run_layout import utc_now_iso

INDEX_SCHEMA_VERSION = "0.1.0"

PrivacyLevel = Literal["raw", "deidentified"]
AnalysisTransform = Literal["identity", "privacy_transform"]


@dataclass
class RunIndexDocument:
    label: str
    file_hash: str | None
    doc_id: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    privacy_level: PrivacyLevel | None = None
    analysis_transform: AnalysisTransform | None = None
    privacy_transform_applied: bool | None = None
    privacy_detectors: list[str] | None = None
    zone_key: str | None = None
    route: str | None = None
    task_key: str | None = None


@dataclass
class RunIndex:
    step: str
    created_at: str
    run_id: str | None = None
    document_count: int | None = None
    documents: list[RunIndexDocument] = field(default_factory=list)


def resolve_index_root(
    *,
    session_dir: Path,
    custom_output_dir: str | Path | None = None,
) -> Path:
    """
    Directory that will contain ``index.json`` (artifact root).

    Default layout: ``session_dir``. Explicit runner ``--output-dir`` / ``--out``:
    the resolved custom output root.
    """
    if custom_output_dir is not None:
        return Path(custom_output_dir).resolve()
    return session_dir.resolve()


def index_relative_path(path: Path, index_root: Path) -> str:
    """
    POSIX path of *path* relative to *index_root* (where ``index.json`` lives).

    Raises if *path* is not under *index_root* (no absolute-path fallback).
    """
    root = index_root.resolve()
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"artifact path {resolved} is not under index root {root}"
        ) from exc
    text = rel.as_posix()
    return text if text else "."


def _output_paths(
    *,
    out_dir: Path,
    index_root: Path,
    output_files: dict[str, str],
) -> dict[str, str]:
    doc_leaf = index_relative_path(out_dir, index_root)
    if doc_leaf == ".":
        return dict(output_files)
    return {key: f"{doc_leaf}/{filename}" for key, filename in output_files.items()}


def _privacy_detectors_from_bundle(bundle: dict[str, Any]) -> list[str]:
    """Collect detectors from applied privacy transform slots in bundle metadata."""
    transforms = bundle.get("privacy_transforms")
    if not isinstance(transforms, dict):
        return []
    detectors: list[str] = []
    for slot_data in transforms.values():
        if not isinstance(slot_data, dict) or not slot_data.get("applied"):
            continue
        source = slot_data.get("detectors_used") or slot_data.get("detectors") or []
        if not isinstance(source, list):
            continue
        for name in source:
            token = str(name).strip()
            if token and token not in detectors:
                detectors.append(token)
    return detectors


def _privacy_index_fields_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Derive ``privacy_level`` for downstream post-extract index entries."""
    enabled = bundle.get("privacy_enabled")
    if enabled is True:
        return {"privacy_level": "deidentified"}
    return {"privacy_level": "raw"}


def _prepare_analysis_index_fields(bundle: dict[str, Any]) -> dict[str, Any]:
    """Prepare_analysis index: analysis transform state, not raw/deidentified."""
    if bundle.get("privacy_enabled") is True:
        return {
            "analysis_transform": "privacy_transform",
            "privacy_transform_applied": True,
            "privacy_detectors": _privacy_detectors_from_bundle(bundle),
        }
    return {
        "analysis_transform": "identity",
        "privacy_transform_applied": False,
        "privacy_detectors": [],
    }


def masked_index_label(bundle: dict[str, Any]) -> str:
    """
    Label for post-extract index entries (prepare_analysis and downstream).

    Prefer ``display_name`` when present. Fall back to ``doc_id``.
    """
    doc_id = str(bundle.get("doc_id") or "unnamed")
    display = bundle.get("display_name")
    if isinstance(display, str):
        text = display.strip()
        if text:
            return text
    return doc_id


def build_extract_index_document(
    *,
    bundle: Any,
    out_dir: Path,
    index_root: Path,
) -> RunIndexDocument:
    file_hash = getattr(bundle, "file_hash", None)
    return RunIndexDocument(
        doc_id=str(bundle.doc_id),
        label=str(bundle.display_name),
        privacy_level="raw",
        file_hash=file_hash if isinstance(file_hash, str) else None,
        outputs=_output_paths(
            out_dir=out_dir,
            index_root=index_root,
            output_files={
                "bundle": "bundle.json",
                "run_summary": "run_summary.json",
            },
        ),
    )


def build_request_file_intake_index_document(
    *,
    run_id: str,
    request_file_intake_result: dict[str, Any],
    out_dir: Path,
    index_root: Path,
) -> RunIndexDocument:
    """Index entry for a request-level intake run (no document processing ``doc_id``)."""
    document = request_file_intake_result.get("document")
    label = run_id
    index_file_hash = None
    if isinstance(document, dict):
        original_file_name = str(document.get("original_file_name") or "").strip()
        if original_file_name:
            label = original_file_name
        file_hash = document.get("file_hash")
        if isinstance(file_hash, str) and file_hash.strip():
            index_file_hash = file_hash.strip()
    return RunIndexDocument(
        label=label,
        file_hash=index_file_hash,
        doc_id=None,
        privacy_level="raw",
        outputs=_output_paths(
            out_dir=out_dir,
            index_root=index_root,
            output_files={
                "request_file_intake_result": REQUEST_FILE_INTAKE_RESULT_FILENAME,
                "run_summary": "run_summary.json",
            },
        ),
    )


def build_safe_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    output_files: dict[str, str],
) -> RunIndexDocument:
    """Post-extract index entry (doc_meta, filter, tag)."""
    file_hash = bundle.get("file_hash")
    privacy_fields = _privacy_index_fields_from_bundle(bundle)
    return RunIndexDocument(
        doc_id=str(bundle.get("doc_id") or "unnamed"),
        label=masked_index_label(bundle),
        file_hash=file_hash if isinstance(file_hash, str) else None,
        outputs=_output_paths(
            out_dir=out_dir,
            index_root=index_root,
            output_files=output_files,
        ),
        **privacy_fields,
    )


def build_prepare_analysis_index_document(
    *,
    analysis_bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
) -> RunIndexDocument:
    file_hash = analysis_bundle.get("file_hash")
    return RunIndexDocument(
        doc_id=str(analysis_bundle.get("doc_id") or "unnamed"),
        label=masked_index_label(analysis_bundle),
        file_hash=file_hash if isinstance(file_hash, str) else None,
        outputs=_output_paths(
            out_dir=out_dir,
            index_root=index_root,
            output_files={
                "analysis_bundle": ANALYSIS_BUNDLE_FILENAME,
                "run_summary": "run_summary.json",
            },
        ),
        **_prepare_analysis_index_fields(analysis_bundle),
    )


def build_doc_meta_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
) -> RunIndexDocument:
    from artifacts.doc_meta import (
        DOC_META_BUNDLE_FILENAME,
        DOCUMENT_CONTEXT_PREVIEW_FILENAME,
    )

    return build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files={
            "doc_meta_bundle": DOC_META_BUNDLE_FILENAME,
            "document_context_preview": DOCUMENT_CONTEXT_PREVIEW_FILENAME,
            "run_summary": "run_summary.json",
        },
    )


def build_filter_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    include_debug: bool = False,
    zone_key: str | None = None,
) -> RunIndexDocument:
    from artifacts.zone_match_bundle import (
        ZONE_MATCH_BUNDLE_DEBUG_FILENAME,
        ZONE_MATCH_BUNDLE_FILENAME,
    )

    output_files: dict[str, str] = {
        "zone_match_bundle": ZONE_MATCH_BUNDLE_FILENAME,
        "coverage_bundle": "coverage_bundle.json",
        "run_summary": "run_summary.json",
    }
    if include_debug:
        output_files["zone_match_bundle_debug"] = ZONE_MATCH_BUNDLE_DEBUG_FILENAME
    doc = build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files=output_files,
    )
    if zone_key:
        doc.zone_key = zone_key
        doc.task_key = zone_key
    return doc


def build_route_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    zone_key: str | None = None,
) -> RunIndexDocument:
    from artifacts.routing.schema import (
        ROUTED_UNITS_ROUTE_FILENAMES,
        ROUTING_MANIFEST_FILENAME,
    )

    doc = build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files={
            "routed_units_aggregate": ROUTED_UNITS_ROUTE_FILENAMES["aggregate"],
            "routed_units_table": ROUTED_UNITS_ROUTE_FILENAMES["table"],
            "routed_units_case": ROUTED_UNITS_ROUTE_FILENAMES["case"],
            "routed_units_unknown": ROUTED_UNITS_ROUTE_FILENAMES["unknown"],
            "routing_manifest": ROUTING_MANIFEST_FILENAME,
            "run_summary": "run_summary.json",
        },
    )
    if zone_key:
        doc.zone_key = zone_key
        doc.task_key = zone_key
    return doc


def build_aggregate_evidence_prepare_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    zone_key: str | None = None,
    task_key: str | None = None,
) -> RunIndexDocument:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
        ASSESSMENT_INPUT_FILENAME,
        ASSESSMENT_INPUT_PREVIEW_FILENAME,
    )
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
        ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
    )

    doc = build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files={
            "assessment_input": ASSESSMENT_INPUT_FILENAME,
            "assessment_input_preview": ASSESSMENT_INPUT_PREVIEW_FILENAME,
            "assessment_runtime_context": ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
            "run_summary": "run_summary.json",
        },
    )
    if zone_key:
        doc.zone_key = zone_key
    if task_key:
        doc.task_key = task_key
    elif zone_key:
        doc.task_key = zone_key
    return doc


def build_aggregate_evidence_assess_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    zone_key: str | None = None,
    task_key: str | None = None,
) -> RunIndexDocument:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_review import (
        SCOPE_ASSESSMENT_REVIEW_FILENAME,
    )
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import SCOPE_ASSESSMENTS_FILENAME

    doc = build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files={
            "scope_assessments": SCOPE_ASSESSMENTS_FILENAME,
            "scope_assessment_review": SCOPE_ASSESSMENT_REVIEW_FILENAME,
            "run_summary": "run_summary.json",
        },
    )
    if zone_key:
        doc.zone_key = zone_key
    if task_key:
        doc.task_key = task_key
    elif zone_key:
        doc.task_key = zone_key
    return doc


def build_aggregate_evidence_eligibility_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    zone_key: str | None = None,
    task_key: str | None = None,
) -> RunIndexDocument:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
        HEADING_SCOPE_ELIGIBILITY_FILENAME,
    )

    doc = build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files={
            "heading_scope_eligibility": HEADING_SCOPE_ELIGIBILITY_FILENAME,
            "run_summary": "run_summary.json",
        },
    )
    if zone_key:
        doc.zone_key = zone_key
    if task_key:
        doc.task_key = task_key
    elif zone_key:
        doc.task_key = zone_key
    return doc


def build_aggregate_evidence_assemble_index_document(
    *,
    bundle: dict[str, Any],
    out_dir: Path,
    index_root: Path,
    zone_key: str | None = None,
    task_key: str | None = None,
) -> RunIndexDocument:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
        AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
    )

    doc = build_safe_index_document(
        bundle=bundle,
        out_dir=out_dir,
        index_root=index_root,
        output_files={
            "aggregate_evidence_source_bundle": AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
            "run_summary": "run_summary.json",
        },
    )
    if zone_key:
        doc.zone_key = zone_key
    if task_key:
        doc.task_key = task_key
    elif zone_key:
        doc.task_key = zone_key
    return doc


def _index_document_to_dict(doc: RunIndexDocument) -> dict[str, Any]:
    data = asdict(doc)
    return {key: value for key, value in data.items() if value is not None}


def _load_existing_index_payload(index_path: Path) -> dict[str, Any] | None:
    if not index_path.is_file():
        return None
    try:
        data = load_json(index_path)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _index_entry_key(entry: dict[str, Any]) -> str:
    doc_id = str(entry.get("doc_id") or "unnamed")
    zone_key = str(entry.get("zone_key") or entry.get("task_key") or "")
    route = str(entry.get("route") or "")
    if zone_key or route:
        return f"{doc_id}|{zone_key}|{route}"
    return doc_id


def _merge_index_document_dicts(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge index entries by doc_id (+ zone/route when present)."""
    merged_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for entry in existing:
        key = _index_entry_key(entry)
        merged_by_id[key] = entry
        order.append(key)

    for entry in incoming:
        key = _index_entry_key(entry)
        if key not in merged_by_id:
            order.append(key)
        merged_by_id[key] = entry

    return [merged_by_id[key] for key in order]


def write_run_index(
    index_root: Path,
    *,
    step: str,
    documents: list[RunIndexDocument],
    created_at: str | None = None,
    run_id: str | None = None,
) -> Path:
    """Write ``index.json`` under *index_root* (artifact root for this run).

    When an index already exists for the same *step*, new documents are merged
    by ``doc_id`` (+ zone/route when present) instead of replacing the whole file.
    """
    index_root = index_root.resolve()
    index_root.mkdir(parents=True, exist_ok=True)
    path = index_root / "index.json"
    incoming_documents = [_index_document_to_dict(doc) for doc in documents]

    resolved_created_at = created_at or utc_now_iso()
    existing_payload = _load_existing_index_payload(path)
    resolved_run_id = run_id
    if (
        existing_payload is not None
        and str(existing_payload.get("step") or "") == step
    ):
        existing_created_at = existing_payload.get("created_at")
        if isinstance(existing_created_at, str) and existing_created_at.strip():
            resolved_created_at = existing_created_at
        existing_run_id = existing_payload.get("run_id")
        if resolved_run_id is None and isinstance(existing_run_id, str):
            resolved_run_id = existing_run_id
        existing_documents = existing_payload.get("documents")
        if isinstance(existing_documents, list):
            existing_dicts = [
                entry for entry in existing_documents if isinstance(entry, dict)
            ]
            merged_documents = _merge_index_document_dicts(
                existing_dicts,
                incoming_documents,
            )
        else:
            merged_documents = incoming_documents
    else:
        merged_documents = incoming_documents

    payload: dict[str, Any] = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "step": step,
        "stage": step,
        "created_at": resolved_created_at,
        "document_count": len(merged_documents),
        "documents": merged_documents,
    }
    if resolved_run_id:
        payload["run_id"] = resolved_run_id
    save_json(path, payload)
    return path
