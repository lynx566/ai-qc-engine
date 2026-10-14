"""Write doc_meta artifacts and run_summary under ``runs/doc_meta/<timestamp>/<doc_id>/``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from artifacts.doc_meta import (
    DOC_META_BUNDLE_FILENAME,
    DOCUMENT_CONTEXT_PREVIEW_FILENAME,
)
from core.metadata.schemas import MetadataProfile
from steps.doc_meta import build_doc_meta_payloads
from runtime.doc_meta_ids import resolve_doc_meta_bundle_id
from runtime.doc_meta_paths import (
    doc_meta_artifact_paths,
    verify_doc_meta_artifacts_written,
)
from runtime.io import load_json, save_json
from runtime.run_layout import DOC_META_RUN_DIR_LAYOUT
from runtime.run_summaries import build_doc_meta_run_summary


def _resolve_analysis_bundle(
    *,
    analysis_bundle_path: Path,
    analysis_bundle: dict[str, Any] | None,
) -> tuple[Path, dict[str, Any]]:
    resolved_path = analysis_bundle_path.resolve()
    resolved_bundle = (
        analysis_bundle
        if analysis_bundle is not None
        else load_json(resolved_path)
    )
    return resolved_path, resolved_bundle


def run_doc_meta_stage(
    *,
    analysis_bundle_path: Path,
    output_dir: Path,
    analysis_bundle: dict[str, Any] | None = None,
    profile: MetadataProfile,
    build_summary: Callable[[dict[str, Any]], dict[str, Any]],
    git_provenance: dict[str, str | bool | None] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Run doc_meta on ``analysis_bundle`` only.

    *output_dir* must be the resolved run leaf (e.g. ``runs/doc_meta/<ts>/<doc_id>/``).
    All returned paths are absolute and match files written on disk.
    """
    resolved_analysis_path, resolved_analysis_bundle = _resolve_analysis_bundle(
        analysis_bundle_path=analysis_bundle_path,
        analysis_bundle=analysis_bundle,
    )
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = doc_meta_artifact_paths(out_dir)

    doc_meta_bundle_id = resolve_doc_meta_bundle_id(
        run_id=run_id,
        analysis_bundle_path=resolved_analysis_path,
        output_dir=out_dir,
    )
    payloads = build_doc_meta_payloads(
        analysis_bundle=resolved_analysis_bundle,
        profile=profile,
        build_summary=build_summary,
        doc_meta_bundle_id=doc_meta_bundle_id,
    )

    doc_meta_bundle_path = artifacts["doc_meta_bundle"]
    preview_path = artifacts["document_context_preview"]
    summary_path = artifacts["run_summary"]

    save_json(doc_meta_bundle_path, payloads.doc_meta_bundle)
    save_json(preview_path, payloads.document_context_preview)

    summary = build_doc_meta_run_summary(
        run_id=doc_meta_bundle_id,
        analysis_bundle_path=resolved_analysis_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        document_context_preview_path=preview_path,
        profile=profile,
        doc_id=str(resolved_analysis_bundle.get("doc_id") or ""),
        analysis_bundle=resolved_analysis_bundle,
        git_provenance=git_provenance,
    )
    save_json(summary_path, summary)

    verify_doc_meta_artifacts_written(artifacts)

    return {
        "doc_meta_bundle": payloads.doc_meta_bundle,
        "doc_meta_bundle_path": doc_meta_bundle_path.resolve().as_posix(),
        "document_context_preview_path": preview_path.resolve().as_posix(),
        "output_dir": out_dir.resolve().as_posix(),
        "run_summary_path": summary_path.resolve().as_posix(),
        "artifacts": {
            "doc_meta_bundle": DOC_META_BUNDLE_FILENAME,
            "document_context_preview": DOCUMENT_CONTEXT_PREVIEW_FILENAME,
            "run_summary": "run_summary.json",
        },
        "run_dir_layout": DOC_META_RUN_DIR_LAYOUT,
    }
