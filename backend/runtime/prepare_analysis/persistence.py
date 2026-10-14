"""Artifact construction and persistence for the Prepare Analysis runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from artifacts.block_manifest import (
    BLOCK_MANIFEST_FILENAME,
    assert_block_manifest_safe,
    build_block_manifest,
)
from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_FILENAME,
    FAILURE_FILENAME,
    PRIVACY_AUDIT_FILENAME,
    RUN_SUMMARY_FILENAME,
    PrepareAnalysisArtifactPaths,
    build_analysis_bundle_artifact,
)
from artifacts.privacy_mapping import (
    MAPPING_FILENAME,
    validate_privacy_mapping_artifact,
)
from artifacts.privacy_safety import assert_public_analysis_bundle_safe
from artifacts.private_audit_bundle import (
    PRIVATE_AUDIT_BUNDLE_FILENAME,
    assert_private_audit_bundle_shape,
    build_private_audit_bundle_from_audit_surfaces,
)
from core.document.doc_identity import require_bundle_file_hash
from runtime.io import save_json
from runtime.run_summaries import build_prepare_analysis_run_summary


@dataclass(frozen=True)
class PrepareAnalysisArtifactPayloads:
    analysis_bundle: dict[str, Any]
    block_manifest: dict[str, Any]
    privacy_audit: dict[str, Any] | None
    mapping: dict[str, Any] | None
    private_audit_bundle: dict[str, Any] | None


def build_prepare_analysis_artifacts(result: Any) -> PrepareAnalysisArtifactPayloads:
    """Package formal artifacts from an already-computed Step result."""

    analysis_bundle = build_analysis_bundle_artifact(result.analysis_bundle)
    if result.heading_projection is None:
        raise ValueError("prepare_analysis result.heading_projection is required")
    block_manifest = build_block_manifest(
        analysis_bundle,
        heading_projection=result.heading_projection,
    )
    assert_block_manifest_safe(block_manifest)

    audit_surfaces = list(result.block_audit_surfaces or [])
    mask_result = result.mask_result
    if mask_result is None:
        if audit_surfaces:
            raise ValueError(
                "prepare_analysis result.block_audit_surfaces must be empty "
                "when mask_result is absent"
            )
        return PrepareAnalysisArtifactPayloads(
            analysis_bundle=analysis_bundle,
            block_manifest=block_manifest,
            privacy_audit=None,
            mapping=None,
            private_audit_bundle=None,
        )

    assert_public_analysis_bundle_safe(analysis_bundle)
    privacy_audit = asdict(mask_result)
    mapping = dict(mask_result.mapping)
    validate_privacy_mapping_artifact(mapping)
    private_audit_bundle = None
    if audit_surfaces:
        private_audit_bundle = build_private_audit_bundle_from_audit_surfaces(
            audit_surfaces,
            doc_id=str(analysis_bundle.get("doc_id") or ""),
            file_hash=require_bundle_file_hash(analysis_bundle, label="analysis_bundle"),
            analysis_bundle_id=str(analysis_bundle.get("analysis_bundle_id") or ""),
            privacy_audit_filename=PRIVACY_AUDIT_FILENAME,
            mapping_filename=MAPPING_FILENAME,
        )
        assert_private_audit_bundle_shape(private_audit_bundle)
    return PrepareAnalysisArtifactPayloads(
        analysis_bundle=analysis_bundle,
        block_manifest=block_manifest,
        privacy_audit=privacy_audit,
        mapping=mapping,
        private_audit_bundle=private_audit_bundle,
    )


def persist_prepare_analysis_artifacts(
    *,
    payloads: PrepareAnalysisArtifactPayloads,
    out_dir: Path,
    run_id: str,
    bundle_dict: dict[str, Any],
    language: str,
    input_bundle: Path | None,
    source_docx: Path | None,
    write_bundle_copy: bool,
    privacy_profile_ref: str | None,
    privacy_detectors_configured: list[str],
    privacy_detectors_used: list[str],
    date_shift_offset_days: int,
    privacy_provenance_stats: Mapping[str, str],
    plugin_provenance: Mapping[str, Any] | None,
    git_provenance: dict[str, str | bool | None] | None,
    paths_base: Path,
) -> PrepareAnalysisArtifactPaths:
    """Persist one document's formal artifacts and run summary."""

    out_dir.mkdir(parents=True, exist_ok=True)
    output_bundle_path: Path | None = None
    if write_bundle_copy:
        output_bundle_path = out_dir / "bundle.json"
        save_json(output_bundle_path, bundle_dict)

    analysis_bundle_path = out_dir / ANALYSIS_BUNDLE_FILENAME
    block_manifest_path = out_dir / BLOCK_MANIFEST_FILENAME
    save_json(analysis_bundle_path, payloads.analysis_bundle)
    save_json(block_manifest_path, payloads.block_manifest)

    privacy_audit_path: Path | None = None
    mapping_path: Path | None = None
    private_audit_path: Path | None = None
    if payloads.privacy_audit is not None:
        privacy_audit_path = out_dir / PRIVACY_AUDIT_FILENAME
        mapping_path = out_dir / MAPPING_FILENAME
        save_json(privacy_audit_path, payloads.privacy_audit)
        save_json(mapping_path, payloads.mapping or {})
    if payloads.private_audit_bundle is not None:
        private_audit_path = out_dir / PRIVATE_AUDIT_BUNDLE_FILENAME
        save_json(private_audit_path, payloads.private_audit_bundle)

    summary = build_prepare_analysis_run_summary(
        run_id=run_id,
        bundle_dict=bundle_dict,
        language=language,
        input_bundle=input_bundle,
        output_bundle_path=output_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        privacy_audit_path=privacy_audit_path,
        mapping_path=mapping_path,
        private_audit_path=private_audit_path,
        privacy_transform_applied=payloads.privacy_audit is not None,
        privacy_detectors_configured=privacy_detectors_configured,
        privacy_detectors_used=privacy_detectors_used,
        privacy_transform_slot="after_extract",
        date_shift_offset_days=date_shift_offset_days,
        analysis_block_count=sum(
            len(payloads.analysis_bundle.get(group) or [])
            for group in (
                "front_matter_blocks",
                "content_blocks",
                "table_blocks",
                "format_blocks",
            )
        ),
        privacy_provenance_stats=privacy_provenance_stats,
        privacy_profile_ref=privacy_profile_ref,
        session_segment=privacy_profile_ref,
        plugin_provenance=plugin_provenance,
        git_provenance=git_provenance,
        paths_base=paths_base,
    )
    summary_path = out_dir / RUN_SUMMARY_FILENAME
    save_json(summary_path, summary)
    return PrepareAnalysisArtifactPaths(
        analysis_bundle=analysis_bundle_path,
        block_manifest=block_manifest_path,
        run_summary=summary_path,
        privacy_audit=privacy_audit_path,
        mapping=mapping_path,
        private_audit_bundle=private_audit_path,
    )


def persist_prepare_analysis_failure(
    *,
    output_dir: Path,
    run_id: str | None,
    error: BaseException,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / FAILURE_FILENAME
    save_json(
        path,
        {
            "stage": "prepare_analysis",
            "status": "failed",
            "run_id": run_id,
            "error": {"type": type(error).__name__, "message": str(error)},
        },
    )
    return path


__all__ = [
    "PrepareAnalysisArtifactPayloads",
    "build_prepare_analysis_artifacts",
    "persist_prepare_analysis_artifacts",
    "persist_prepare_analysis_failure",
]
