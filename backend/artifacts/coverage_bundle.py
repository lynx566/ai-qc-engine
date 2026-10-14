"""
Persisted ``coverage_bundle.json`` contract.

``coverage_bundle`` is a per-block Filter **selection ledger** for one Filter job.
``selected_by_filter`` indicates whether the block was selected into at least one
matched zone for this job. It does not indicate semantic review completeness,
clinical relevance, or checked/not-checked status.

Selected rows use ``include_reason="matched_zone"`` (neutral selection code;
not a domain-specific reason string). ``exclude_reason`` for unselected rows is
``not_matched_by_zone_filter``.

Semantic row derivation belongs to ``steps.filter``; this module serializes
and validates the persisted artifact envelope only.
"""

from __future__ import annotations

from typing import Any

from core.document.doc_identity import require_bundle_file_hash

COVERAGE_BUNDLE_FILENAME = "coverage_bundle.json"

_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "analysis_text",
        "normalized_text",
        "span_map",
        "source_ref",
        "document_meta",
        "privacy_transforms",
        "sentences",
        "matched_heading_text",
        "matched_heading_text_stripped",
        "matched_heading_original_text",
        "heading_lineage",
        "nested_matched_headings",
        "checked",
        "not_checked",
        "reviewed",
        "unreviewed",
    }
)

EXCLUDE_REASON_NOT_MATCHED = "not_matched_by_zone_filter"


def build_coverage_bundle_id(*, filter_run_id: str) -> str:
    return f"coverage_{filter_run_id}"


def build_coverage_bundle(
    *,
    block_manifest: dict[str, Any],
    coverage: list[dict[str, Any]],
    zone_key: str,
    filter_run_id: str,
) -> dict[str, Any]:
    """
    Build the persisted coverage_bundle envelope from Step-derived ledger rows.

    Does not derive which blocks are selected; *coverage* must already reflect
    ``derive_block_selection_coverage`` output.
    """
    block_manifest_id = block_manifest.get("block_manifest_id")
    if not isinstance(block_manifest_id, str) or not block_manifest_id.strip():
        raise ValueError("block_manifest.block_manifest_id is required")

    doc_id = block_manifest.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError("block_manifest.doc_id is required")

    if not isinstance(zone_key, str) or not zone_key.strip():
        raise ValueError("zone_key is required")

    if not isinstance(coverage, list):
        raise ValueError("coverage must be a list")

    analysis_bundle_ref = block_manifest.get("analysis_bundle_ref") or {}
    analysis_bundle_id = analysis_bundle_ref.get("analysis_bundle_id")
    if not isinstance(analysis_bundle_id, str) or not analysis_bundle_id.strip():
        raise ValueError(
            "block_manifest.analysis_bundle_ref.analysis_bundle_id is required"
        )

    selected_blocks = sum(
        1 for row in coverage if isinstance(row, dict) and row.get("selected_by_filter")
    )
    total_blocks = len(coverage)

    payload = {
        "coverage_bundle_id": build_coverage_bundle_id(filter_run_id=filter_run_id),
        "doc_id": doc_id,
        "file_hash": require_bundle_file_hash(block_manifest, label="block_manifest"),
        "block_manifest_ref": {
            "block_manifest_id": block_manifest_id,
        },
        "analysis_bundle_ref": {
            "analysis_bundle_id": analysis_bundle_id,
        },
        "zone_key": zone_key,
        "coverage": coverage,
        "summary": {
            "total_blocks": total_blocks,
            "selected_blocks": selected_blocks,
            "excluded_blocks": total_blocks - selected_blocks,
        },
    }
    assert_coverage_bundle_safe(payload)
    return payload


def assert_coverage_bundle_safe(payload: dict[str, Any]) -> None:
    """Raise ``ValueError`` if *payload* contains forbidden text or debug fields."""

    def _walk(value: Any, *, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _FORBIDDEN_OUTPUT_KEYS:
                    raise ValueError(f"forbidden key {key!r} at {path}")
                _walk(item, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, path=f"{path}[{index}]")

    _walk(payload, path="coverage_bundle")
