"""Effective candidate scope override and builder regression tests."""

from __future__ import annotations

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
from artifacts.candidate_scope_override import assert_candidate_scope_override_safe
from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
    ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
    build_analysis_bundle_artifact,
)
from artifacts.zone_match_bundle import build_zone_match_bundle
from core.document.sentence_index import build_sentences
from operations.filter_output_projection.contracts import FilterOutputProjectionInput
from steps.effective_candidate_scope import (
    RESOLVED_CANDIDATE_SCOPE_INPUT_STAGE,
    RESOLVED_CANDIDATE_SCOPE_PIPELINE,
    RESOLVED_CANDIDATE_SCOPE_STAGE,
    build_effective_candidate_scope,
    build_resolved_candidate_scope,
    canonicalize_ancestor_descendant_zones,
)
from steps.filter import extract_zones_from_bundle, to_public_filter_payload
from steps.project_filter_output import run as run_project_filter_output
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy import (
    evaluate_heading_scope_eligibility,
)
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    build_overview_semantic_decomposition_facade,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.clinical_safety_zh import (
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.dsur_overview_zh import (
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
)
from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)
from tests.block_manifest_test_helpers import build_block_manifest
from tests.filter_test_helpers import resolved_filter_job

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
DOC_ID = "doc_showcase"
FILTER_RUN_ID = "filter_test_run"
EFFECTIVE_RUN_ID = "candidate_scope_test_run"


def _sentence(block_id: str, text: str) -> dict[str, str]:
    built = build_sentences(block_id, "paragraph", raw_text=text, normalized_text=text)
    sentence = built[0]
    return {"sentence_id": sentence.sentence_id, "analysis_text": sentence.normalized_text}


def _heading(
    block_id: str,
    text: str,
    *,
    level: int,
    doc_order_index: int,
) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": "heading",
        "text": text,
        "analysis_text": text,
        "doc_order_index": doc_order_index,
        "meta": {
            "heading_level": level,
            "heading_text_stripped": text,
        },
        "sentences": [_sentence(block_id, text)],
    }


def _paragraph(block_id: str, text: str, *, doc_order_index: int) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "text": text,
        "analysis_text": text,
        "doc_order_index": doc_order_index,
        "sentences": [_sentence(block_id, text)],
    }


def _table(block_id: str, *, doc_order_index: int) -> dict[str, Any]:
    text = "风险 | 例数\n肺炎 | 3"
    return {
        "block_id": block_id,
        "kind": "table",
        "analysis_text": text,
        "doc_order_index": doc_order_index,
        "sentences": [{"sentence_id": f"{block_id}:S001", "analysis_text": text}],
        "meta": {"row_count": 2, "column_count": 2},
    }


def _showcase_analysis_bundle() -> dict[str, Any]:
    return build_analysis_bundle_artifact(
        {
            "doc_id": DOC_ID,
            "file_name": "showcase.docx",
            "source_type": "docx",
            "file_hash": LINEAGE_FILE_HASH,
            "analysis_bundle_id": "prepare_analysis_showcase",
            "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
            "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
            "stage": "prepare_analysis",
            "pipeline": ["extract", "prepare_analysis"],
            "privacy_enabled": True,
            "privacy_transforms": {"after_extract": {"applied": True}},
            "front_matter_blocks": [],
            "content_blocks": [
                _heading("C0029", "4. 临床安全性", level=1, doc_order_index=40),
                _heading("C0030", "4.1 总体不良事件概览", level=2, doc_order_index=41),
                _paragraph("C0031", "4.1 body one.", doc_order_index=42),
                _paragraph("C0032", "4.1 body two.", doc_order_index=43),
                _heading("C0033", "4.2 严重不良事件与重要风险", level=2, doc_order_index=44),
                _paragraph("C0034", "4.2 body one.", doc_order_index=45),
                _paragraph("C0035", "4.2 body two.", doc_order_index=46),
                _heading("C0038", "4.3 其他安全性观察", level=2, doc_order_index=47),
                _paragraph("C0039", "4.3 body.", doc_order_index=48),
                _heading("C0040", "4.3.1 安全性参考信息的一致性", level=3, doc_order_index=49),
                _paragraph("C0041", "4.3.1 body.", doc_order_index=50),
            ],
            "table_blocks": [
                _table("T0002", doc_order_index=46),
            ],
            "format_blocks": [],
        }
    )


def _automatic_public_bundle(
    analysis_bundle: dict[str, Any],
    *,
    profile: Any = DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
) -> dict[str, Any]:
    block_manifest = build_block_manifest(analysis_bundle)
    raw = extract_zones_from_bundle(analysis_bundle, resolved_filter_job(profile))
    public = to_public_filter_payload(raw, block_manifest=block_manifest)
    return build_zone_match_bundle(public)


def _override(
    operations: dict[str, str],
    *,
    filter_job_id: str = "dsur_clinical_safety",
) -> dict[str, Any]:
    return {
        "doc_id": DOC_ID,
        "filter_job_id": filter_job_id,
        "base_filter_run_id": FILTER_RUN_ID,
        "operations": [
            {"anchor_block_id": anchor, "op": op}
            for anchor, op in operations.items()
        ],
    }


def _resolution_input(
    operations: dict[str, str] | None = None,
    *,
    filter_job_id: str = "dsur_clinical_safety",
) -> dict[str, Any]:
    return {
        "doc_id": DOC_ID,
        "filter_job_id": filter_job_id,
        "base_filter_run_id": FILTER_RUN_ID,
        "operations": [
            {"anchor_block_id": anchor, "op": op}
            for anchor, op in (operations or {}).items()
        ],
    }


def _anchor_ids(bundle: dict[str, Any]) -> list[str]:
    anchors: list[str] = []
    for zone in bundle.get("matched_zones") or []:
        match = zone.get("match") or {}
        anchor = match.get("matched_heading_block_id")
        if anchor:
            anchors.append(str(anchor))
    return anchors


def _build_effective(
    *,
    automatic: dict[str, Any],
    analysis_bundle: dict[str, Any],
    override: dict[str, Any],
) -> Any:
    block_manifest = build_block_manifest(analysis_bundle)
    return build_effective_candidate_scope(
        automatic_zone_match_bundle=automatic,
        candidate_scope_override=override,
        block_manifest=block_manifest,
        analysis_bundle=analysis_bundle,
        effective_run_id=EFFECTIVE_RUN_ID,
    )


def test_zero_operation_resolution_preserves_canonical_anchors_and_identity() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)
    automatic_anchors = _anchor_ids(automatic)

    result = build_resolved_candidate_scope(
        automatic_zone_match_bundle=automatic,
        candidate_scope_resolution_input=_resolution_input(),
        block_manifest=build_block_manifest(analysis_bundle),
        analysis_bundle=analysis_bundle,
        effective_run_id=EFFECTIVE_RUN_ID,
    )
    resolved = result.effective_zone_match_bundle
    assert _anchor_ids(resolved) == automatic_anchors
    assert resolved["stage"] == RESOLVED_CANDIDATE_SCOPE_STAGE
    assert resolved["input_stage"] == RESOLVED_CANDIDATE_SCOPE_INPUT_STAGE
    assert resolved["pipeline"] == RESOLVED_CANDIDATE_SCOPE_PIPELINE
    assert resolved["doc_id"] == DOC_ID
    assert resolved["file_hash"] == LINEAGE_FILE_HASH
    assert resolved["zone_config_name"] == automatic["zone_config_name"]
    assert resolved["zone_config_version"] == automatic["zone_config_version"]
    assert resolved["language"] == automatic["language"]


def test_remove_automatic_zone() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)
    assert _anchor_ids(automatic) == ["C0030", "C0033", "C0040"]

    result = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0033": "remove"}),
    )
    assert _anchor_ids(result.effective_zone_match_bundle) == ["C0030", "C0040"]


def test_add_previously_unmatched_heading() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)

    result = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0038": "add"}),
    )

    anchors = _anchor_ids(result.effective_zone_match_bundle)
    assert "C0038" in anchors
    zone = next(
        zone
        for zone in result.effective_zone_match_bundle["matched_zones"]
        if (zone.get("match") or {}).get("matched_heading_block_id") == "C0038"
    )
    match = zone["match"]
    assert match["match_type"] == "manual"
    assert match["match_mode"] == "user_override"
    block_ids = {block["block_id"] for block in zone.get("blocks") or []}
    assert block_ids >= {"C0038", "C0039", "C0040", "C0041"}


def test_ancestor_descendant_canonicalization() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)
    assert _anchor_ids(automatic) == ["C0030", "C0033", "C0040"]

    result = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0038": "add"}),
    )
    assert _anchor_ids(result.effective_zone_match_bundle) == ["C0030", "C0033", "C0038"]

    ancestor = next(
        zone
        for zone in result.effective_zone_match_bundle["matched_zones"]
        if (zone.get("match") or {}).get("matched_heading_block_id") == "C0038"
    )
    block_ids = {block["block_id"] for block in ancestor.get("blocks") or []}
    assert "C0040" in block_ids
    assert "C0041" in block_ids


def test_combined_edit_remove_add_canonicalizes() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)

    result = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0033": "remove", "C0038": "add"}),
    )
    assert _anchor_ids(result.effective_zone_match_bundle) == ["C0030", "C0038"]
    zone_ids = [zone["zone_id"] for zone in result.effective_zone_match_bundle["matched_zones"]]
    assert zone_ids == ["Z0001", "Z0002"]


def test_coverage_sync_with_effective_zones() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)

    result = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0033": "remove", "C0038": "add"}),
    )
    coverage = result.effective_coverage_bundle
    selected = {
        row["block_id"]
        for row in coverage["coverage"]
        if row.get("selected_by_filter") is True
    }
    effective_block_ids: set[str] = set()
    for zone in result.effective_zone_match_bundle["matched_zones"]:
        for group in ("blocks", "table_blocks"):
            for block in zone.get(group) or []:
                effective_block_ids.add(str(block["block_id"]))

    assert selected == effective_block_ids
    assert "C0034" not in selected
    assert "C0039" in selected
    assert coverage["coverage_bundle_id"] == f"coverage_{EFFECTIVE_RUN_ID}"


def test_effective_bundle_runs_direct_projection_without_changes() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)
    effective = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0033": "remove", "C0038": "add"}),
    ).effective_zone_match_bundle

    app_composition = build_clinical_trial_doc_consistency_qc_application_composition()
    resolved_job = app_composition.resolve_filter_output_projection_job("dsur_clinical_safety")
    projection_input = FilterOutputProjectionInput(
        filter_job_id="dsur_clinical_safety",
        doc_id=DOC_ID,
        file_hash=LINEAGE_FILE_HASH,
        zone_key="dsur_clinical_safety_zh",
        zone_match_bundle=effective,
    )
    step_result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
        job=resolved_job,
    )
    assert step_result.projected_sources
    assert all(
        source.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
        for source in step_result.projected_sources
    )


def test_overview_heading_override_reruns_semantic_projection() -> None:
    overview_bundle = build_analysis_bundle_artifact(
        {
            "doc_id": DOC_ID,
            "file_name": "overview.docx",
            "source_type": "docx",
            "file_hash": LINEAGE_FILE_HASH,
            "analysis_bundle_id": "prepare_analysis_overview",
            "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
            "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
            "stage": "prepare_analysis",
            "pipeline": ["extract", "prepare_analysis"],
            "privacy_enabled": True,
            "privacy_transforms": {"after_extract": {"applied": True}},
            "front_matter_blocks": [],
            "content_blocks": [
                _heading("C0010", "1. 执行概要", level=1, doc_order_index=10),
                _paragraph("C0011", "overview safety sentence.", doc_order_index=11),
                _heading("C0012", "2. 背景介绍", level=1, doc_order_index=12),
                _paragraph("C0013", "background body.", doc_order_index=13),
            ],
            "table_blocks": [],
            "format_blocks": [],
        }
    )
    automatic = _automatic_public_bundle(
        overview_bundle,
        profile=DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    )
    assert _anchor_ids(automatic) == ["C0010"]

    effective = _build_effective(
        automatic=automatic,
        analysis_bundle=overview_bundle,
        override=_override({"C0012": "add"}, filter_job_id="dsur_overview"),
    ).effective_zone_match_bundle
    assert _anchor_ids(effective) == ["C0010", "C0012"]

    overview_composition = build_clinical_trial_doc_consistency_qc_application_composition()
    resolved_job = overview_composition.resolve_filter_output_projection_job("dsur_overview")
    projection_input = FilterOutputProjectionInput(
        filter_job_id="dsur_overview",
        doc_id=DOC_ID,
        file_hash=LINEAGE_FILE_HASH,
        zone_key="dsur_overview_zh",
        zone_match_bundle=effective,
    )
    overview_facade = build_overview_semantic_decomposition_facade(
        llm_provider=OverviewStandaloneMockProvider(),
    )
    step_result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=overview_bundle,
        facade=overview_facade,
        job=resolved_job,
    )
    assert step_result.projected_sources
    assert step_result.semantic_outcomes


def test_invalid_anchor_rejected() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)

    with pytest.raises(ValueError, match="not found"):
        _build_effective(
            automatic=automatic,
            analysis_bundle=analysis_bundle,
            override=_override({"C9999": "add"}),
        )

    with pytest.raises(ValueError, match="not a heading"):
        _build_effective(
            automatic=automatic,
            analysis_bundle=analysis_bundle,
            override=_override({"C0031": "add"}),
        )


def test_manual_candidate_scope_does_not_bypass_eligibility() -> None:
    manual_scope = {
        "scope_id": "HS0001",
        "heading_path": ["4.3 其他安全性观察"],
        "unit_form": "aggregate",
        "route_qc": {
            "route_mismatch": False,
            "suggested_route": "aggregate",
            "reason": None,
        },
        "safety_role": "primary_safety_finding",
        "product_context_role": "non_target_product",
        "match_type": "manual",
    }
    result = evaluate_heading_scope_eligibility(scope_assessment=manual_scope)
    assert result["status"] == "excluded_non_target_product"


def test_remove_unselected_anchor_is_no_op() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)
    result = _build_effective(
        automatic=automatic,
        analysis_bundle=analysis_bundle,
        override=_override({"C0038": "remove"}),
    )
    assert _anchor_ids(result.effective_zone_match_bundle) == _anchor_ids(automatic)


def test_duplicate_anchor_operation_rejected() -> None:
    payload = {
        "doc_id": DOC_ID,
        "filter_job_id": "dsur_clinical_safety",
        "base_filter_run_id": FILTER_RUN_ID,
        "operations": [
            {"anchor_block_id": "C0033", "op": "remove"},
            {"anchor_block_id": "C0033", "op": "remove"},
        ],
    }
    with pytest.raises(ValueError, match="duplicate"):
        assert_candidate_scope_override_safe(payload)


def test_canonicalize_unit_drops_descendant_when_ancestor_present() -> None:
    analysis_bundle = _showcase_analysis_bundle()
    automatic = _automatic_public_bundle(analysis_bundle)
    zones = list(automatic["matched_zones"])
    raw_added = build_effective_candidate_scope(
        automatic_zone_match_bundle=automatic,
        candidate_scope_override=_override({"C0038": "add"}),
        block_manifest=build_block_manifest(analysis_bundle),
        analysis_bundle=analysis_bundle,
        effective_run_id=EFFECTIVE_RUN_ID,
    ).effective_zone_match_bundle["matched_zones"]
    ancestor = next(z for z in raw_added if _anchor_ids({"matched_zones": [z]}) == ["C0038"])
    descendant = next(z for z in zones if _anchor_ids({"matched_zones": [z]}) == ["C0040"])
    canonical = canonicalize_ancestor_descendant_zones([ancestor, descendant])
    assert _anchor_ids({"matched_zones": canonical}) == ["C0038"]
