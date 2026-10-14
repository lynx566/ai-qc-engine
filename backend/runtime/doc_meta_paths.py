"""Paths and loading for doc_meta stage artifacts."""

from __future__ import annotations

from pathlib import Path

from artifacts.doc_meta import (
    DOC_META_BUNDLE_FILENAME,
    DOCUMENT_CONTEXT_PREVIEW_FILENAME,
)
def resolve_doc_meta_output_dir(
    output_dir: str | Path,
    *,
    anchor_root: Path | None = None,
) -> Path:
    """Resolve explicit ``--output-dir`` (relative paths anchor at *anchor_root*)."""
    path = Path(output_dir)
    if not path.is_absolute() and anchor_root is not None:
        path = anchor_root / path
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def doc_meta_artifact_paths(output_dir: Path) -> dict[str, Path]:
    """Canonical artifact paths under a resolved doc_meta output directory."""
    root = output_dir.resolve()
    return {
        "output_dir": root,
        "doc_meta_bundle": root / DOC_META_BUNDLE_FILENAME,
        "document_context_preview": root / DOCUMENT_CONTEXT_PREVIEW_FILENAME,
        "run_summary": root / "run_summary.json",
    }


def verify_doc_meta_artifacts_written(paths: dict[str, Path]) -> None:
    """Raise if any expected doc_meta artifact file is missing on disk."""
    missing: list[str] = []
    out_dir = paths["output_dir"]
    if not out_dir.is_dir():
        raise RuntimeError(f"doc_meta output_dir does not exist: {out_dir}")

    for key in ("doc_meta_bundle", "document_context_preview", "run_summary"):
        path = paths[key].resolve()
        if not path.is_file():
            missing.append(f"{key}={path}")
    if missing:
        raise RuntimeError(
            "doc_meta artifacts missing on disk: " + ", ".join(missing)
        )
