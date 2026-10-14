"""Cross-artifact structural validation for filter/route upstream inputs."""

from __future__ import annotations

from typing import Any

from core.document.doc_identity import require_bundle_file_hash


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def validate_coverage_block_manifest_doc_meta_upstream(
    *,
    coverage_bundle: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
) -> None:
    """Fail fast on identity/ref mismatches across coverage, block_manifest, and doc_meta."""
    coverage_doc_id = _require_str(coverage_bundle.get("doc_id"), field="coverage_bundle.doc_id")
    manifest_doc_id = _require_str(
        block_manifest.get("doc_id"),
        field="block_manifest.doc_id",
    )
    meta_doc_id = _require_str(doc_meta_bundle.get("doc_id"), field="doc_meta_bundle.doc_id")

    if coverage_doc_id != manifest_doc_id:
        raise ValueError(
            f"doc_id mismatch: coverage_bundle={coverage_doc_id!r} "
            f"block_manifest={manifest_doc_id!r}"
        )
    if coverage_doc_id != meta_doc_id:
        raise ValueError(
            f"doc_id mismatch: coverage_bundle={coverage_doc_id!r} "
            f"doc_meta_bundle={meta_doc_id!r}"
        )

    coverage_file_hash = require_bundle_file_hash(
        coverage_bundle,
        label="coverage_bundle",
    )
    manifest_file_hash = require_bundle_file_hash(block_manifest, label="block_manifest")
    if coverage_file_hash != manifest_file_hash:
        raise ValueError(
            f"file_hash mismatch: coverage_bundle={coverage_file_hash!r} "
            f"block_manifest={manifest_file_hash!r}"
        )
    meta_hash_raw = doc_meta_bundle.get("file_hash")
    if isinstance(meta_hash_raw, str) and meta_hash_raw.strip():
        if meta_hash_raw.strip() != coverage_file_hash:
            raise ValueError(
                f"file_hash mismatch: coverage_bundle={coverage_file_hash!r} "
                f"doc_meta_bundle={meta_hash_raw.strip()!r}"
            )

    coverage_manifest_ref = coverage_bundle.get("block_manifest_ref") or {}
    coverage_manifest_id = _require_str(
        coverage_manifest_ref.get("block_manifest_id"),
        field="coverage_bundle.block_manifest_ref.block_manifest_id",
    )
    block_manifest_id = _require_str(
        block_manifest.get("block_manifest_id"),
        field="block_manifest.block_manifest_id",
    )
    if coverage_manifest_id != block_manifest_id:
        raise ValueError(
            "block_manifest_id mismatch between coverage_bundle and block_manifest"
        )

    coverage_analysis_ref = coverage_bundle.get("analysis_bundle_ref") or {}
    coverage_analysis_id = _require_str(
        coverage_analysis_ref.get("analysis_bundle_id"),
        field="coverage_bundle.analysis_bundle_ref.analysis_bundle_id",
    )
    manifest_analysis_ref = block_manifest.get("analysis_bundle_ref") or {}
    manifest_analysis_id = _require_str(
        manifest_analysis_ref.get("analysis_bundle_id"),
        field="block_manifest.analysis_bundle_ref.analysis_bundle_id",
    )
    if coverage_analysis_id != manifest_analysis_id:
        raise ValueError(
            "analysis_bundle_id mismatch between coverage_bundle and block_manifest"
        )

    if not isinstance(doc_meta_bundle.get("summary"), dict):
        raise ValueError("doc_meta_bundle.summary is required")

    _require_str(
        doc_meta_bundle.get("doc_meta_bundle_id"),
        field="doc_meta_bundle.doc_meta_bundle_id",
    )
    _require_str(
        coverage_bundle.get("coverage_bundle_id"),
        field="coverage_bundle.coverage_bundle_id",
    )
    _require_str(coverage_bundle.get("zone_key"), field="coverage_bundle.zone_key")

    blocks = block_manifest.get("blocks") or []
    if not isinstance(blocks, list):
        raise ValueError("block_manifest.blocks must be a list")
    table_blocks = block_manifest.get("table_blocks") or []
    if not isinstance(table_blocks, list):
        raise ValueError("block_manifest.table_blocks must be a list")
    block_ids = {
        str(block.get("block_id"))
        for block in (*blocks, *table_blocks)
        if isinstance(block, dict) and block.get("block_id")
    }

    coverage_rows = coverage_bundle.get("coverage") or []
    if not isinstance(coverage_rows, list):
        raise ValueError("coverage_bundle.coverage must be a list")

    for index, row in enumerate(coverage_rows):
        if not isinstance(row, dict):
            continue
        text_ref = row.get("text_ref") or {}
        block_id = text_ref.get("block_id")
        if not block_id:
            raise ValueError(
                f"coverage_bundle.coverage[{index}].text_ref.block_id is required"
            )
        if str(block_id) not in block_ids:
            raise ValueError(
                f"coverage_bundle.coverage[{index}] references unknown block_id "
                f"{block_id!r} (not in block_manifest blocks or table_blocks)"
            )
