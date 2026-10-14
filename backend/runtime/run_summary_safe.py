"""Safe provenance fields for run_summary.json after prepare_analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.run_layout import posix_relative

# Stages that must not record raw upload paths or filenames in run_summary.
POST_MASK_STAGES = frozenset({"prepare_analysis", "doc_meta", "filter", "tag"})

FORBIDDEN_INPUT_KEYS = frozenset({"source_docx", "source_path"})

PATHS_BASE = Path(__file__).resolve().parents[1]


def summary_artifact_path(path: Path, *, base: Path | None = None) -> str:
    """POSIX path relative to *base* (default: backend source root), for run_summary inputs."""
    root = (base or PATHS_BASE).resolve()
    return posix_relative(path.resolve(), root)


def post_analysis_bundle_extra(bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Provenance fields safe to retain after prepare_analysis (no raw filenames)."""
    if not bundle:
        return {}
    extra: dict[str, Any] = {}
    file_hash = bundle.get("file_hash")
    if isinstance(file_hash, str) and file_hash:
        extra["file_hash"] = file_hash
    return extra


def post_mask_bundle_extra(bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Deprecated alias for :func:`post_analysis_bundle_extra`."""
    return post_analysis_bundle_extra(bundle)


def post_mask_inputs(inputs: dict[str, str], *, base: Path | None = None) -> dict[str, str]:
    """Drop forbidden keys and rewrite paths as relative POSIX under *base*."""
    root = base or PATHS_BASE
    safe: dict[str, str] = {}
    for key, value in inputs.items():
        if key in FORBIDDEN_INPUT_KEYS:
            continue
        if not value:
            continue
        safe[key] = summary_artifact_path(Path(value), base=root)
    return safe
