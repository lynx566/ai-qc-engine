"""Build the prepare_analysis private audit artifact from audit surfaces."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from artifacts.privacy_mapping import MAPPING_FILENAME

PRIVATE_AUDIT_BUNDLE_FILENAME = "private_audit_bundle.json"

PRIVATE_AUDIT_SCHEMA_VERSION = "0.3.0"
SUPPORTED_PRIVATE_AUDIT_SCHEMA_VERSIONS = frozenset({PRIVATE_AUDIT_SCHEMA_VERSION})
ARTIFACT_KIND = "prepare_analysis_private_audit_bundle"


def build_private_audit_bundle_id(*, analysis_bundle_id: str) -> str:
    return f"private_audit_{analysis_bundle_id}"


def _audit_surface_to_private_block_entry(surface: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "block_id": surface.get("block_id"),
        "kind": surface.get("kind"),
    }
    for field in (
        "normalized_text",
        "analysis_text",
        "sentences",
        "source_ref",
        "heading_path_extract",
        "meta_audit",
    ):
        if field in surface:
            entry[field] = deepcopy(surface[field])
    return entry


def build_private_audit_bundle_from_audit_surfaces(
    block_audit_surfaces: list[dict[str, Any]],
    *,
    doc_id: str,
    file_hash: str,
    analysis_bundle_id: str,
    privacy_audit_filename: str | None = "privacy_audit.json",
    mapping_filename: str | None = MAPPING_FILENAME,
) -> dict[str, Any]:
    """
    Build private audit from mask-stage block audit surfaces (PR2.1+ primary path).
    """
    if not isinstance(analysis_bundle_id, str) or not analysis_bundle_id.strip():
        raise ValueError("analysis_bundle_id is required")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError("doc_id is required")

    payload: dict[str, Any] = {
        "artifact_kind": ARTIFACT_KIND,
        "artifact_privacy_level": "private_raw_audit",
        "private_audit_schema_version": PRIVATE_AUDIT_SCHEMA_VERSION,
        "contains_raw_sensitive_data": True,
        "for_llm": False,
        "for_export": False,
        "for_user_review_default": False,
        "private_audit_bundle_id": build_private_audit_bundle_id(
            analysis_bundle_id=analysis_bundle_id,
        ),
        "doc_id": doc_id,
        "file_hash": file_hash,
        "analysis_bundle_ref": {
            "analysis_bundle_id": analysis_bundle_id,
        },
        "blocks": [
            _audit_surface_to_private_block_entry(surface)
            for surface in block_audit_surfaces
        ],
    }
    if privacy_audit_filename:
        payload["privacy_audit_ref"] = {"filename": privacy_audit_filename}
    if mapping_filename:
        payload["mapping_ref"] = {"filename": mapping_filename}
    return payload


def private_audit_blocks_by_id(
    private_audit_bundle: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index ``private_audit_bundle.blocks`` by ``block_id``."""
    out: dict[str, dict[str, Any]] = {}
    for block in private_audit_bundle.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_id = block.get("block_id")
        if block_id:
            out[str(block_id)] = block
    return out


def is_supported_private_audit_schema_version(version: object) -> bool:
    return isinstance(version, str) and version in SUPPORTED_PRIVATE_AUDIT_SCHEMA_VERSIONS


def assert_private_audit_bundle_shape(payload: dict[str, Any]) -> None:
    required = (
        "artifact_kind",
        "artifact_privacy_level",
        "private_audit_schema_version",
        "contains_raw_sensitive_data",
        "private_audit_bundle_id",
        "doc_id",
        "file_hash",
        "analysis_bundle_ref",
        "blocks",
    )
    for key in required:
        if key not in payload:
            raise ValueError(f"private_audit_bundle missing required key {key!r}")

    if payload.get("artifact_kind") != ARTIFACT_KIND:
        raise ValueError("private_audit_bundle.artifact_kind mismatch")

    schema_version = payload.get("private_audit_schema_version")
    if not is_supported_private_audit_schema_version(schema_version):
        raise ValueError(
            f"unsupported private_audit_schema_version: {schema_version!r}"
        )

    block_ids = [block.get("block_id") for block in payload.get("blocks") or []]
    if len(block_ids) != len(set(block_ids)):
        raise ValueError("private_audit_bundle.blocks contain duplicate block_id values")
