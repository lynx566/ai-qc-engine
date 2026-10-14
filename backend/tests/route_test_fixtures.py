"""Shared Route test fixtures and canonical projected-source routing helpers."""

from __future__ import annotations

from typing import Any

from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from artifacts.routing.types import ROUTES, RoutedUnitSet
from operations.filter_output_projection.contracts import (
    CanonicalSourceRef,
    FilterOutputProjectionStepResult,
    ProjectedSource,
)
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from tests.projection_test_helpers import projected_sentence, raw_projected_source

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)

DEFAULT_SEMANTIC_MODULE_ID = CLINICAL_SAFETY_SEMANTIC_MODULE_ID
ANALYSIS_BUNDLE_ID = "prepare_analysis_test"


def _whole_block_sentences(block_id: str, analysis_text: str) -> list[dict[str, str]]:
    text = str(analysis_text or "").strip()
    if not text:
        return []
    return [{"sentence_id": f"{block_id}:S001", "analysis_text": text}]


def _analysis_bundle_for_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    content_blocks: list[dict[str, Any]] = []
    for block in manifest.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("block_id") or "")
        analysis_text = str(block.get("analysis_text") or "")
        content_blocks.append(
            {
                "block_id": block_id,
                "kind": block.get("kind"),
                "order": block.get("order"),
                "analysis_text": analysis_text,
                "sentences": _whole_block_sentences(block_id, analysis_text),
            }
        )
    table_blocks: list[dict[str, Any]] = []
    for block in manifest.get("table_blocks") or []:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("block_id") or "")
        analysis_text = str(block.get("analysis_text") or block.get("text") or "")
        table_blocks.append(
            {
                "block_id": block_id,
                "kind": "table",
                "order": block.get("order"),
                "analysis_text": analysis_text,
                "sentences": _whole_block_sentences(block_id, analysis_text),
            }
        )
    return {
        "analysis_bundle_id": ANALYSIS_BUNDLE_ID,
        "doc_id": str(manifest.get("doc_id") or "doc_test"),
        "file_hash": str(manifest.get("file_hash") or LINEAGE_FILE_HASH),
        "content_blocks": content_blocks,
        "table_blocks": table_blocks,
    }


def _minimal_doc_meta(*, doc_id: str = "doc_test") -> dict:
    return {
        "doc_meta_bundle_id": "doc_meta_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "summary": {"doc_type": "IB", "study_drug": "StudyDrug_001"},
    }


def _coverage_row(
    block_id: str,
    order: int,
    *,
    block_kind: str = "paragraph",
    heading_path: list[str] | None = None,
    selected: bool = True,
    zone_id: str = "Z1",
) -> dict:
    return {
        "block_id": block_id,
        "block_kind": block_kind,
        "order": order,
        "heading_path": heading_path or [],
        "selected_by_filter": selected,
        "zone_match": {"zone_id": zone_id},
        "text_ref": {
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": block_id,
        },
    }


def _route_input_envelope(
    *,
    route_input_id: str = "coverage_route_test",
    doc_id: str = "doc_test",
    file_hash: str = LINEAGE_FILE_HASH,
    zone_key: str = "ib_clinical_safety_zh",
) -> dict:
    return {
        "route_input_id": route_input_id,
        "doc_id": doc_id,
        "file_hash": file_hash,
        "zone_key": zone_key,
    }


def _route_input_envelope_from_coverage_bundle(coverage_bundle: dict[str, Any]) -> dict:
    return {
        "route_input_id": str(coverage_bundle["coverage_bundle_id"]),
        "doc_id": str(coverage_bundle["doc_id"]),
        "file_hash": str(
            coverage_bundle.get("file_hash") or LINEAGE_FILE_HASH
        ),
        "zone_key": str(coverage_bundle.get("zone_key") or ""),
    }


def _coverage_bundle(*rows: dict) -> dict:
    return {
        "coverage_bundle_id": "coverage_route_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "block_manifest_ref": {"block_manifest_id": "block_manifest_test"},
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "zone_key": "ib_clinical_safety_zh",
        "coverage": list(rows),
    }


def _block(
    block_id: str,
    order: int,
    *,
    kind: str = "paragraph",
    heading_path: list[str] | None = None,
    analysis_text: str = "body text",
) -> dict:
    return {
        "block_id": block_id,
        "kind": kind,
        "order": order,
        "heading_path": heading_path or [],
        "analysis_text": analysis_text,
        "text_ref": {
            "analysis_bundle_id": ANALYSIS_BUNDLE_ID,
            "block_id": block_id,
        },
    }


def _table_block(
    block_id: str,
    order: int,
    *,
    heading_path: list[str] | None = None,
    analysis_text: str = "A | B\n1 | 2",
) -> dict:
    return {
        "block_id": block_id,
        "kind": "table",
        "order": order,
        "heading_path": heading_path or [],
        "analysis_text": analysis_text,
        "text_ref": {
            "analysis_bundle_id": ANALYSIS_BUNDLE_ID,
            "block_id": block_id,
        },
    }


def _block_manifest(*, blocks: list[dict], table_blocks: list[dict] | None = None) -> dict:
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": ANALYSIS_BUNDLE_ID},
        "blocks": list(blocks),
        "table_blocks": table_blocks or [],
    }


def _source_group_for_block_kind(block_kind: str) -> str:
    if block_kind == "table":
        return "table_blocks"
    return "blocks"


def _projected_source_from_coverage_row(
    row: dict[str, Any],
    *,
    zone_key: str,
    semantic_module_id: str = DEFAULT_SEMANTIC_MODULE_ID,
) -> ProjectedSource:
    block_id = str(row.get("block_id") or "")
    block_kind = str(row.get("block_kind") or "paragraph")
    heading_path = row.get("heading_path")
    if not isinstance(heading_path, list):
        heading_path = []
    lineage: dict[str, str] = {}
    if zone_key:
        lineage["zone_key"] = zone_key
    zone_match = row.get("zone_match")
    if isinstance(zone_match, dict):
        zone_id = zone_match.get("zone_id")
        if isinstance(zone_id, str) and zone_id.strip():
            lineage["zone_id"] = zone_id.strip()
    return raw_projected_source(
        semantic_module_id=semantic_module_id,
        block_id=block_id,
        block_kind=block_kind,
        source_group=_source_group_for_block_kind(block_kind),
        heading_path=[str(item) for item in heading_path],
        lineage=lineage,
        sentences=(
            projected_sentence(
                sentence_id=f"{block_id}:S001",
                text="sample text",
                source_block_id=block_id,
            ),
        ),
    )


def _projected_sources_from_coverage_bundle(
    coverage_bundle: dict[str, Any],
    *,
    semantic_module_id: str = DEFAULT_SEMANTIC_MODULE_ID,
) -> tuple[ProjectedSource, ...]:
    zone_key = str(coverage_bundle.get("zone_key") or "")
    projected_sources: list[ProjectedSource] = []
    for row in coverage_bundle.get("coverage") or []:
        if not isinstance(row, dict):
            continue
        if row.get("selected_by_filter") is not True:
            continue
        projected_sources.append(
            _projected_source_from_coverage_row(
                row,
                zone_key=zone_key,
                semantic_module_id=semantic_module_id,
            )
        )
    return tuple(projected_sources)


def _route_units(
    *,
    coverage: dict[str, Any],
    manifest: dict[str, Any],
    analysis_bundle: dict[str, Any] | None = None,
    semantic_module_id: str = DEFAULT_SEMANTIC_MODULE_ID,
) -> RoutedUnitSet:
    doc_id = str(coverage.get("doc_id") or manifest.get("doc_id") or "doc_test")
    file_hash = str(
        coverage.get("file_hash") or manifest.get("file_hash") or LINEAGE_FILE_HASH
    )
    resolved_analysis_bundle = analysis_bundle or _analysis_bundle_for_manifest(manifest)
    return route_prepare_units_from_projected_sources(
        projected_sources=_projected_sources_from_coverage_bundle(
            coverage,
            semantic_module_id=semantic_module_id,
        ),
        block_manifest=manifest,
        analysis_bundle=resolved_analysis_bundle,
        expected_semantic_module_id=semantic_module_id,
        doc_id=doc_id,
        file_hash=file_hash,
    )


def _projection_fan_in_input_for_step_result(
    step_result: FilterOutputProjectionStepResult,
    *,
    run_id: str = "test_projection_run",
):
    from artifacts.filter_output_projection_bundle import (
        build_filter_output_projection_bundle_id,
    )
    from operations.filter_output_projection.fan_in import ProjectionFanInInput

    return ProjectionFanInInput(
        step_result=step_result,
        filter_output_projection_bundle_id=build_filter_output_projection_bundle_id(
            filter_job_id=step_result.filter_job_id,
            run_id=run_id,
        ),
    )


def _projection_input_refs_dicts(selection) -> tuple[dict[str, str], ...]:
    return tuple(ref.to_dict() for ref in selection.projection_input_refs)
