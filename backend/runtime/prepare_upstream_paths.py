"""Resolve ESP prepare upstream inputs from filter/doc_meta run directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.doc_meta import DOC_META_BUNDLE_FILENAME
from artifacts.private_audit_bundle import PRIVATE_AUDIT_BUNDLE_FILENAME
from runtime.io import load_json
from runtime.run_summary_safe import PATHS_BASE

COVERAGE_BUNDLE_FILENAME = "coverage_bundle.json"


def _resolve_summary_path(
    path_str: str,
    *,
    project_root: Path,
    relative_base: Path | None = None,
) -> Path:
    raw = Path(path_str)
    if raw.is_absolute():
        candidate = raw.resolve()
    elif relative_base is not None:
        sibling = (relative_base / raw).resolve()
        if sibling.is_file():
            candidate = sibling
        else:
            candidate = (project_root / raw).resolve()
    else:
        candidate = (project_root / raw).resolve()
    if not candidate.is_file():
        raise ValueError(f"expected file at {path_str!r}, resolved to missing: {candidate}")
    return candidate


def _require_existing_file(path: Path, *, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} must be a file: {resolved}")
    return resolved


def _analysis_path_from_summary_inputs(
    inputs: dict[str, Any],
    *,
    project_root: Path,
) -> Path | None:
    for key in ("analysis_bundle", "input_analysis_bundle"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            return _resolve_summary_path(value, project_root=project_root)
    return None


def _validate_prepare_upstream_bundle_refs(
    *,
    coverage_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
) -> tuple[str, str]:
    coverage_doc_id = str(coverage_bundle.get("doc_id") or "")
    manifest_doc_id = str(block_manifest.get("doc_id") or "")
    doc_meta_doc_id = str(doc_meta_bundle.get("doc_id") or "")
    analysis_doc_id = str(analysis_bundle.get("doc_id") or "")

    doc_ids = {
        coverage_doc_id,
        manifest_doc_id,
        doc_meta_doc_id,
        analysis_doc_id,
    }
    if len(doc_ids) != 1 or not coverage_doc_id:
        raise ValueError(
            "doc_id mismatch across prepare upstream inputs: "
            f"coverage_bundle={coverage_doc_id!r}, "
            f"block_manifest={manifest_doc_id!r}, "
            f"doc_meta_bundle={doc_meta_doc_id!r}, "
            f"analysis_bundle={analysis_doc_id!r}"
        )

    coverage_manifest_ref = coverage_bundle.get("block_manifest_ref") or {}
    coverage_manifest_id = str(coverage_manifest_ref.get("block_manifest_id") or "")
    block_manifest_id = str(block_manifest.get("block_manifest_id") or "")
    if not coverage_manifest_id or coverage_manifest_id != block_manifest_id:
        raise ValueError(
            "block_manifest_id mismatch: "
            f"coverage_bundle.block_manifest_ref.block_manifest_id="
            f"{coverage_manifest_id!r}, "
            f"block_manifest.block_manifest_id={block_manifest_id!r}"
        )

    coverage_analysis_ref = coverage_bundle.get("analysis_bundle_ref") or {}
    coverage_analysis_id = str(coverage_analysis_ref.get("analysis_bundle_id") or "")
    analysis_bundle_id = str(analysis_bundle.get("analysis_bundle_id") or "")
    if not coverage_analysis_id or coverage_analysis_id != analysis_bundle_id:
        raise ValueError(
            "analysis_bundle_id mismatch: "
            f"coverage_bundle.analysis_bundle_ref.analysis_bundle_id="
            f"{coverage_analysis_id!r}, "
            f"analysis_bundle.analysis_bundle_id={analysis_bundle_id!r}"
        )

    zone_key = str(coverage_bundle.get("zone_key") or "")
    return coverage_doc_id, zone_key


def resolve_private_audit_bundle_path(
    analysis_bundle_path: Path,
) -> Path | None:
    """Return sibling ``private_audit_bundle.json`` when present (optional input)."""
    candidate = analysis_bundle_path.parent / PRIVATE_AUDIT_BUNDLE_FILENAME
    if candidate.is_file():
        return candidate.resolve()
    return None


def discover_doc_meta_dir(
    *,
    filter_run_dir: Path,
    project_root: Path,
) -> Path:
    """
    Auto-discover the doc_meta run directory that matches *filter_run_dir*.

    Scans ``<project_root>/runs/doc_meta/`` for a per-doc directory whose
    ``run_summary.json`` references the same analysis bundle as the filter run.
    Returns the most recently-timestamped match (directory name descending).

    Raises ``ValueError`` with an actionable message when no match is found.
    """
    root = project_root.resolve()
    filter_dir = filter_run_dir.resolve()
    filter_summary = load_json(filter_dir / "run_summary.json")
    doc_id = str(filter_summary.get("doc_id") or "")
    if not doc_id:
        raise ValueError("filter run_summary.json missing doc_id")

    analysis_rel = (filter_summary.get("inputs") or {}).get("input_analysis_bundle")
    if not isinstance(analysis_rel, str) or not analysis_rel.strip():
        raise ValueError("filter run_summary.json missing inputs.input_analysis_bundle")
    analysis_path = _resolve_summary_path(analysis_rel, project_root=root).resolve()

    doc_meta_root = root / "runs" / "doc_meta"
    if not doc_meta_root.is_dir():
        raise ValueError(
            f"No doc_meta runs directory at {doc_meta_root}. "
            f"Run doc_meta_runner.py --analysis-bundle {analysis_rel!r} first."
        )

    candidates: list[Path] = []
    for ts_dir in sorted(doc_meta_root.iterdir(), reverse=True):
        if not ts_dir.is_dir():
            continue
        doc_dirs = [p for p in ts_dir.iterdir() if p.is_dir()]
        if not doc_dirs:
            legacy_doc_dir = ts_dir / doc_id
            if legacy_doc_dir.is_dir():
                doc_dirs = [legacy_doc_dir]
        for doc_dir in doc_dirs:
            if doc_dir.name != doc_id and not doc_dir.name.endswith(doc_id):
                # Prefer exact doc_id match when directory uses doc_ prefix convention.
                from runtime.run_layout import format_doc_run_dir_name

                if doc_dir.name != format_doc_run_dir_name(doc_id):
                    continue
            summary_path = doc_dir / "run_summary.json"
            if not summary_path.is_file():
                continue
            try:
                dm_summary = load_json(summary_path)
            except Exception:
                continue
            dm_inputs = dm_summary.get("inputs") or {}
            dm_rel = dm_inputs.get("analysis_bundle") or dm_inputs.get(
                "input_analysis_bundle"
            )
            if not isinstance(dm_rel, str) or not dm_rel.strip():
                continue
            try:
                dm_path = _resolve_summary_path(dm_rel, project_root=root).resolve()
            except ValueError:
                continue
            if dm_path == analysis_path:
                candidates.append(doc_dir)

    if not candidates:
        raise ValueError(
            f"No doc_meta run found for doc_id={doc_id!r} matching "
            f"analysis bundle {analysis_path.as_posix()!r}. "
            f"Run: doc_meta_runner.py --analysis-bundle {analysis_rel!r}"
        )
    return candidates[0]


def resolve_prepare_upstream_inputs_from_dirs(
    *,
    filter_run_dir: Path,
    doc_meta_dir: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """
    Discover ESP prepare upstream artifact paths from filter and doc_meta run dirs.

    Returns resolved paths plus ``doc_id`` and ``zone_key``.
    """
    root = (project_root or PATHS_BASE).resolve()
    filter_dir = filter_run_dir.resolve()
    doc_meta_path_dir = doc_meta_dir.resolve()

    if not filter_dir.is_dir():
        raise ValueError(f"--filter-run-dir must be a directory: {filter_run_dir}")
    if not doc_meta_path_dir.is_dir():
        raise ValueError(f"--doc-meta-dir must be a directory: {doc_meta_dir}")

    filter_summary_path = filter_dir / "run_summary.json"
    if not filter_summary_path.is_file():
        raise ValueError(
            f"filter run directory missing run_summary.json: {filter_summary_path}"
        )
    filter_summary = load_json(filter_summary_path)

    outputs = filter_summary.get("outputs") or {}
    coverage_name = outputs.get("coverage_bundle", COVERAGE_BUNDLE_FILENAME)
    if isinstance(coverage_name, str) and coverage_name.strip():
        coverage_bundle_path = _resolve_summary_path(
            coverage_name,
            project_root=root,
            relative_base=filter_dir,
        )
    else:
        coverage_bundle_path = _require_existing_file(
            filter_dir / COVERAGE_BUNDLE_FILENAME,
            label="coverage_bundle",
        )

    inputs = filter_summary.get("inputs") or {}
    analysis_rel = inputs.get("input_analysis_bundle")
    if not isinstance(analysis_rel, str) or not analysis_rel.strip():
        raise ValueError(
            "filter run_summary.json missing inputs.input_analysis_bundle"
        )
    analysis_bundle_path = _resolve_summary_path(analysis_rel, project_root=root)

    block_manifest_path = analysis_bundle_path.parent / BLOCK_MANIFEST_FILENAME
    block_manifest_path = _require_existing_file(
        block_manifest_path,
        label="block_manifest",
    )

    private_audit_bundle_path = resolve_private_audit_bundle_path(analysis_bundle_path)

    doc_meta_bundle_path = _require_existing_file(
        doc_meta_path_dir / DOC_META_BUNDLE_FILENAME,
        label="doc_meta_bundle",
    )

    doc_meta_summary_path = doc_meta_path_dir / "run_summary.json"
    if doc_meta_summary_path.is_file():
        doc_meta_summary = load_json(doc_meta_summary_path)
        doc_meta_inputs = doc_meta_summary.get("inputs") or {}
        doc_meta_analysis_path = _analysis_path_from_summary_inputs(
            doc_meta_inputs,
            project_root=root,
        )
        if doc_meta_analysis_path is not None:
            if doc_meta_analysis_path.resolve() != analysis_bundle_path.resolve():
                raise ValueError(
                    "analysis_bundle path mismatch between filter and doc_meta runs: "
                    f"filter={analysis_bundle_path.as_posix()}, "
                    f"doc_meta={doc_meta_analysis_path.as_posix()}"
                )

    coverage_bundle = load_json(coverage_bundle_path)
    block_manifest = load_json(block_manifest_path)
    doc_meta_bundle = load_json(doc_meta_bundle_path)
    analysis_bundle = load_json(analysis_bundle_path)

    doc_id, zone_key = _validate_prepare_upstream_bundle_refs(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
    )
    if not zone_key:
        zone_key = str(filter_summary.get("zone_key") or "")

    return {
        "coverage_bundle_path": coverage_bundle_path,
        "block_manifest_path": block_manifest_path,
        "doc_meta_bundle_path": doc_meta_bundle_path,
        "analysis_bundle_path": analysis_bundle_path,
        "private_audit_bundle_path": private_audit_bundle_path,
        "doc_id": doc_id,
        "zone_key": zone_key,
    }
