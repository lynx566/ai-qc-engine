"""Canonical Extract runtime operation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from core.document.doc_identity import DocumentProcessingIdentity
from core.document.document_schema import DocumentBundle
from steps.extract import run as run_extract_step
from runtime.extract.persistence import persist_extract_document
from runtime.run_ids import build_run_id_from_session_dir, build_session_dir_segment, utc_run_stamp
from runtime.run_index import (
    build_extract_index_document,
    resolve_index_root,
    write_run_index,
)
from runtime.run_layout import EXTRACT_RUN_DIR_LAYOUT, build_stage_run_layout, sanitize_run_segment

EXTRACT_STAGE = "extract"


@dataclass(frozen=True)
class ExtractDocumentInput:
    source_path: Path | str
    identity: DocumentProcessingIdentity


@dataclass(frozen=True)
class ExtractDocumentResult:
    identity: DocumentProcessingIdentity
    bundle: DocumentBundle
    output_dir: Path
    bundle_path: Path
    run_summary_path: Path


@dataclass(frozen=True)
class ExtractOperationResult:
    run_id: str
    output_dir: Path
    document: ExtractDocumentResult
    index_path: Path


@dataclass(frozen=True)
class ExtractOperationReport:
    result: ExtractOperationResult
    messages: tuple[str, ...]


def _allocate_session_dir(*, runs_root: Path, stamp) -> Path:
    """Allocate ``runs/extract/<run_id>/`` with collision suffix when needed."""
    session_base = build_session_dir_segment(stamp)
    stage_root = runs_root / sanitize_run_segment(EXTRACT_STAGE).lower()
    stage_root.mkdir(parents=True, exist_ok=True)
    candidate = stage_root / session_base
    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    suffix = 2
    while True:
        alt = stage_root / f"{session_base}__{suffix}"
        if not alt.exists():
            alt.mkdir(parents=True, exist_ok=True)
            return alt
        suffix += 1


def _resolve_output_root(
    *,
    project_root: Path,
    output_dir: Path | str | None,
    stamp,
) -> tuple[Path, str]:
    if output_dir is not None:
        resolved = Path(output_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        run_id = build_run_id_from_session_dir(EXTRACT_STAGE, resolved.name)
        return resolved, run_id

    session_dir = _allocate_session_dir(runs_root=project_root / "runs", stamp=stamp)
    run_id = build_run_id_from_session_dir(EXTRACT_STAGE, session_dir.name)
    return session_dir, run_id


def _resolve_source_path(path: Path | str) -> Path:
    candidate = Path(path)
    if not candidate.is_file():
        label = candidate.as_posix()
        raise ValueError(f"document.source_path must be a regular file: {label}")
    return candidate.resolve()


def _validate_document(document: ExtractDocumentInput) -> ExtractDocumentInput:
    if not isinstance(document, ExtractDocumentInput):
        raise TypeError("document must be an ExtractDocumentInput")
    if not isinstance(document.identity, DocumentProcessingIdentity):
        raise TypeError("document.identity must be a DocumentProcessingIdentity")
    doc_id = document.identity.doc_id.strip()
    if not doc_id:
        raise ValueError("document.identity.doc_id is required")
    return ExtractDocumentInput(
        source_path=_resolve_source_path(document.source_path),
        identity=document.identity,
    )


def _resolve_document_output_dir(
    *,
    session_root: Path,
    layout,
    custom_output_dir: Path | str | None,
) -> Path:
    if custom_output_dir is not None:
        return session_root

    doc_out_dir = layout.artifact_leaf(session_root)
    doc_out_dir.mkdir(parents=True, exist_ok=True)
    return doc_out_dir


def run_extract_operation(
    *,
    project_root: Path,
    document: ExtractDocumentInput,
    extract_config_id: str,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
    export_slices: bool = False,
    git_provenance: Mapping[str, str | bool | None] | None = None,
) -> ExtractOperationReport:
    """Execute one Extract run for one document: Step, persistence, summary, and index."""
    if not isinstance(extract_config_id, str) or not extract_config_id.strip():
        raise TypeError("extract_config_id must be a non-empty str")
    validated = _validate_document(document)
    extract_context = sanitize_run_segment(extract_config_id).lower()
    stamp = utc_run_stamp()
    session_root, resolved_run_id = _resolve_output_root(
        project_root=project_root,
        output_dir=output_dir,
        stamp=stamp,
    )
    if run_id is not None:
        resolved_run_id = run_id

    index_root = resolve_index_root(
        session_dir=session_root,
        custom_output_dir=output_dir,
    )
    git_prov = dict(git_provenance) if git_provenance is not None else None

    layout = build_stage_run_layout(
        stage=EXTRACT_STAGE,
        context=extract_context,
        doc_id=validated.identity.doc_id,
        stamp=stamp,
        session_dir_name=session_root.name,
        run_dir_layout=EXTRACT_RUN_DIR_LAYOUT,
    )
    doc_out_dir = _resolve_document_output_dir(
        session_root=session_root,
        layout=layout,
        custom_output_dir=output_dir,
    )

    source_bytes = validated.source_path.read_bytes()
    bundle = run_extract_step(
        source_bytes,
        identity=validated.identity,
        extract_config_id=extract_config_id,
    )
    persistence = persist_extract_document(
        bundle=bundle,
        source_path=validated.source_path,
        out_dir=doc_out_dir,
        run_id=resolved_run_id,
        project_root=project_root,
        export_slices=export_slices,
        git_provenance=git_prov,
    )
    document_result = ExtractDocumentResult(
        identity=validated.identity,
        bundle=bundle,
        output_dir=doc_out_dir,
        bundle_path=persistence.bundle_path,
        run_summary_path=persistence.run_summary_path,
    )
    index_document = build_extract_index_document(
        bundle=bundle,
        out_dir=doc_out_dir,
        index_root=index_root,
    )

    index_path = write_run_index(
        index_root,
        step=EXTRACT_STAGE,
        documents=[index_document],
        run_id=resolved_run_id,
    )

    messages: list[str] = [f"run_id: {resolved_run_id}"]
    messages.append(f"bundle: {document_result.bundle_path}")
    messages.append(f"run_summary: {document_result.run_summary_path}")
    messages.append(f"index: {index_path}")

    result = ExtractOperationResult(
        run_id=resolved_run_id,
        output_dir=session_root,
        document=document_result,
        index_path=index_path,
    )
    return ExtractOperationReport(result=result, messages=tuple(messages))
