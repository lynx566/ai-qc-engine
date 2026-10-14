"""Stable doc_meta run / bundle id resolution."""

from __future__ import annotations

from pathlib import Path

from runtime.run_provenance import load_upstream_run_summary


def resolve_doc_meta_bundle_id(
    *,
    run_id: str | None = None,
    analysis_bundle_path: Path | None = None,
    output_dir: Path | None = None,
) -> str:
    """
    Resolve ``doc_meta_bundle_id`` — same value as ``run_summary.run_id``.

    Prefer explicit *run_id*; else derive from upstream prepare_analysis run;
    else fall back to ``doc_meta_<output_dir.parent.name>``.
    """
    if run_id is not None:
        return run_id
    if analysis_bundle_path is not None:
        upstream = load_upstream_run_summary(analysis_bundle_path)
        if upstream and upstream.get("run_id"):
            return f"doc_meta_{upstream['run_id']}"
    if output_dir is not None:
        return f"doc_meta_{Path(output_dir).resolve().parent.name}"
    raise ValueError(
        "Cannot resolve doc_meta_bundle_id: provide run_id, "
        "analysis_bundle_path, or output_dir"
    )
