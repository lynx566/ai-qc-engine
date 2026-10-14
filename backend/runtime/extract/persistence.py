"""Persist one Extract document's runtime artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from core.document.document_schema import DocumentBundle
from runtime.io import save_json
from runtime.run_layout import sanitize_run_segment
from runtime.run_summaries import build_extract_run_summary_dict


@dataclass(frozen=True)
class ExtractDocumentPersistenceResult:
    bundle_path: Path
    run_summary_path: Path


def persist_extract_document(
    *,
    bundle: DocumentBundle,
    source_path: Path,
    out_dir: Path,
    run_id: str,
    project_root: Path,
    export_slices: bool = False,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> ExtractDocumentPersistenceResult:
    """Write bundle.json, run_summary.json, and optional slices for one document."""
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = out_dir / "bundle.json"
    save_json(bundle_path, asdict(bundle))

    if export_slices:
        slices_dir = out_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)
        save_json(
            slices_dir / "content_blocks.json",
            [asdict(block) for block in bundle.content_blocks],
        )
        save_json(
            slices_dir / "table_blocks.json",
            [asdict(block) for block in bundle.table_blocks],
        )
        save_json(
            slices_dir / "front_matter_blocks.json",
            [asdict(block) for block in bundle.front_matter_blocks],
        )
        save_json(
            slices_dir / "format_blocks.json",
            [asdict(block) for block in bundle.format_blocks],
        )
        save_json(slices_dir / "document_meta.json", bundle.document_meta)

    context = sanitize_run_segment(bundle.source_type or "docx").lower()
    run_summary_path = out_dir / "run_summary.json"
    save_json(
        run_summary_path,
        build_extract_run_summary_dict(
            run_id=run_id,
            bundle=bundle,
            export_slices=export_slices,
            source_docx=source_path.resolve(),
            git_root=project_root,
            context=context,
            git_provenance=git_provenance,
        ),
    )

    return ExtractDocumentPersistenceResult(
        bundle_path=bundle_path,
        run_summary_path=run_summary_path,
    )
