"""Direct clinical-safety Filter-output projection regression tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
    ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
    build_analysis_bundle_artifact,
)
from artifacts.zone_match_bundle import build_zone_match_bundle
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionInput,
    ResolvedFilterOutputProjectionJob,
)
from steps.filter import extract_zones_from_bundle, to_public_filter_payload
from steps.project_filter_output import run as run_project_filter_output
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    project_direct_filter_output,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.block_manifest_test_helpers import build_block_manifest
from tests.filter_test_helpers import build_test_coverage_bundle, resolved_filter_job
from core.document.sentence_index import build_sentences

DIRECT_PLUGIN_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "filter_output_projection"
    / "direct.py"
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)

SEMANTIC_MODULE_ID = CLINICAL_SAFETY_SEMANTIC_MODULE_ID


def _heading(block_id: str, text: str, *, level: int, doc_order_index: int) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": "heading",
        "text": text,
        "doc_order_index": doc_order_index,
        "meta": {
            "heading_level": level,
            "heading_text_stripped": text,
        },
    }


def _paragraph(
    block_id: str,
    text: str,
    *,
    doc_order_index: int,
) -> dict[str, Any]:
    built_sentences = build_sentences(
        block_id,
        "paragraph",
        raw_text=text,
        normalized_text=text,
    )
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "text": text,
        "normalized_text": text,
        "analysis_text": text,
        "span_map": [],
        "doc_order_index": doc_order_index,
        "sentences": [
            {
                "sentence_id": sentence.sentence_id,
                "analysis_text": sentence.normalized_text,
            }
            for sentence in built_sentences
        ],
    }


def _table_block(block_id: str, *, doc_order_index: int) -> dict[str, Any]:
    text = "事件 | 例数\nSAE | 2"
    return {
        "block_id": block_id,
        "kind": "table",
        "analysis_text": text,
        "doc_order_index": doc_order_index,
        "sentences": [
            {
                "sentence_id": f"{block_id}:S001",
                "analysis_text": text,
            }
        ],
        "meta": {
            "row_count": 2,
            "column_count": 2,
        },
    }


def _safety_analysis_bundle() -> dict[str, Any]:
    return build_analysis_bundle_artifact(
        {
            "doc_id": "doc_regression",
            "file_name": "sample.docx",
            "source_type": "docx",
            "file_hash": LINEAGE_FILE_HASH,
            "analysis_bundle_id": "prepare_analysis_regression",
            "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
            "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
            "stage": "prepare_analysis",
            "pipeline": ["extract", "prepare_analysis"],
            "privacy_enabled": True,
            "privacy_transforms": {"after_extract": {"applied": True}},
            "front_matter_blocks": [],
            "content_blocks": [
                {
                    "block_id": "H0001",
                    "kind": "heading",
                    "analysis_text": "7 安全性",
                    "sentences": [
                        {
                            "sentence_id": "H0001:S001",
                            "analysis_text": "7 安全性",
                        }
                    ],
                },
                _paragraph("C0001", "不良事件概述。", doc_order_index=1),
            ],
            "table_blocks": [
                _table_block("T0001", doc_order_index=2),
            ],
            "format_blocks": [],
        }
    )


def _analysis_bundle_for_zone_match(zone_match_bundle: dict[str, Any]) -> dict[str, Any]:
    """Build a valid public analysis_bundle covering Filter-selected blocks."""
    content_blocks: list[dict[str, Any]] = []
    table_blocks: list[dict[str, Any]] = []
    for zone in zone_match_bundle.get("matched_zones") or []:
        if not isinstance(zone, dict):
            continue
        for block in zone.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("block_id") or "").strip()
            if not block_id:
                continue
            analysis_text = block.get("analysis_text")
            if not isinstance(analysis_text, str):
                analysis_text = str(block.get("text") or "")
            sentences = block.get("sentences")
            if not isinstance(sentences, list):
                sentences = [
                    {
                        "sentence_id": f"{block_id}:S001",
                        "analysis_text": analysis_text,
                    }
                ]
            else:
                sentences = [
                    {
                        "sentence_id": str(item["sentence_id"]),
                        "analysis_text": str(item["analysis_text"]),
                    }
                    for item in sentences
                    if isinstance(item, dict)
                    and isinstance(item.get("sentence_id"), str)
                    and isinstance(item.get("analysis_text"), str)
                ]
            content_blocks.append(
                {
                    "block_id": block_id,
                    "kind": block.get("kind") or "paragraph",
                    "analysis_text": analysis_text,
                    "sentences": sentences,
                }
            )
        for block in zone.get("table_blocks") or []:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("block_id") or "").strip()
            if not block_id:
                continue
            analysis_text = block.get("analysis_text")
            if not isinstance(analysis_text, str):
                analysis_text = str(block.get("text") or "")
            table_blocks.append(
                {
                    "block_id": block_id,
                    "kind": "table",
                    "analysis_text": analysis_text,
                    "sentences": [
                        {
                            "sentence_id": f"{block_id}:S001",
                            "analysis_text": analysis_text,
                        }
                    ],
                }
            )
    return build_analysis_bundle_artifact(
        {
            "doc_id": str(zone_match_bundle.get("doc_id") or "doc_test"),
            "file_name": "sample.docx",
            "source_type": "docx",
            "file_hash": str(zone_match_bundle.get("file_hash") or LINEAGE_FILE_HASH),
            "analysis_bundle_id": "prepare_analysis_projection_test",
            "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
            "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
            "stage": "prepare_analysis",
            "pipeline": ["extract", "prepare_analysis"],
            "privacy_enabled": True,
            "privacy_transforms": {"after_extract": {"applied": True}},
            "front_matter_blocks": [],
            "content_blocks": content_blocks,
            "table_blocks": table_blocks,
            "format_blocks": [],
        }
    )


def _filter_artifacts_for_profile(profile: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    analysis_bundle = _safety_analysis_bundle()
    block_manifest = build_block_manifest(analysis_bundle)
    zones_raw = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(profile),
    )
    public_filter = to_public_filter_payload(
        zones_raw,
        block_manifest=block_manifest,
    )
    zone_match_bundle = build_zone_match_bundle(public_filter)
    coverage_bundle = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_match_bundle,
        zone_key=profile.zone_config_name,
        filter_run_id=f"regression_{profile.filter_job_id}",
    )
    return zone_match_bundle, coverage_bundle, block_manifest, analysis_bundle


def _projection_input_for_profile(
    profile: Any,
    zone_match_bundle: dict[str, Any],
) -> FilterOutputProjectionInput:
    return FilterOutputProjectionInput(
        filter_job_id=profile.filter_job_id,
        doc_id=str(zone_match_bundle["doc_id"]),
        file_hash=LINEAGE_FILE_HASH,
        zone_key=profile.zone_config_name,
        zone_match_bundle=zone_match_bundle,
    )


def _resolved_direct_job(profile: Any) -> ResolvedFilterOutputProjectionJob:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    return composition.resolve_filter_output_projection_job(profile.filter_job_id)


def test_direct_projection_happy_path_uses_configured_semantic_module() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, _, analysis_bundle = _filter_artifacts_for_profile(profile)
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)
    job = _resolved_direct_job(profile)

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=job,
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )

    assert result.projected_sources
    assert all(
        source.semantic_module_id == SEMANTIC_MODULE_ID
        for source in result.projected_sources
    )
    assert result.semantic_outcomes == ()


def test_direct_projection_projects_all_matched_sources_without_omission() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, coverage_bundle, _, analysis_bundle = _filter_artifacts_for_profile(profile)
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )

    projected_ids = {
        ref.refs["block_id"]
        for source in result.projected_sources
        for ref in source.source_refs
    }
    selected_ids = {
        str(row["block_id"])
        for row in coverage_bundle["coverage"]
        if row.get("selected_by_filter") is True
    }
    assert projected_ids == selected_ids


def test_direct_projection_includes_matched_table_source() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, _, analysis_bundle = _filter_artifacts_for_profile(profile)
    zone_match_bundle["matched_zones"][0]["table_blocks"].append(
        {
            "block_id": "T0001",
            "kind": "table",
            "heading_path": ["7 安全性"],
            "analysis_text": "事件 | 例数\nSAE | 2",
        }
    )
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )

    table_sources = [
        source
        for source in result.projected_sources
        if source.source_refs[0].refs.get("source_group") == "table_blocks"
    ]
    assert len(table_sources) == 1
    assert table_sources[0].source_refs[0].refs["block_id"] == "T0001"


def test_direct_projection_does_not_import_coverage_contracts() -> None:
    tree = ast.parse(
        DIRECT_PLUGIN_PATH.read_text(encoding="utf-8"),
        filename=str(DIRECT_PLUGIN_PATH),
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = (
        "artifacts.coverage_bundle",
        "steps.filter",
    )
    for module in forbidden:
        assert module not in imported


def test_direct_projection_uses_projection_source_text_not_zone_match_copy() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, _, analysis_bundle = _filter_artifacts_for_profile(profile)
    zone_match_bundle["matched_zones"][0]["blocks"][0]["analysis_text"] = (
        "OLD / DIFFERENT"
    )
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )

    paragraph_source = next(
        source
        for source in result.projected_sources
        if source.source_refs[0].refs.get("block_id") == "C0001"
    )
    assert paragraph_source.sentences[0].text == "不良事件概述。"
    assert "analysis_text" not in paragraph_source.payload


def test_direct_projection_rejects_missing_semantic_module_config() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, _, _ = _filter_artifacts_for_profile(profile)
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)
    job = ResolvedFilterOutputProjectionJob(
        filter_job_id=profile.filter_job_id,
        strategy_id=DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        strategy_config={},
    )

    with pytest.raises(ValueError, match="semantic_module_id"):
        project_direct_filter_output(
            projection_input=projection_input,
            job=job,
        )
