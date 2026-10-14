"""file_hash propagation across downstream artifacts (lineage metadata only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.doc_meta import metadata_result_to_doc_meta_bundle
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
    build_aggregate_evidence_assessment_input_envelope,
)
from core.metadata.schemas import MetadataField, MetadataResult
from steps.filter import extract_zones_from_bundle, to_public_filter_payload
from plugins.clinical_trial_doc.doc_meta.summary import (
    build_clinical_trial_doc_meta_summary,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    prepare_aggregate_evidence_semantic_result,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from runtime.run_summaries import (
    build_aggregate_evidence_assess_run_summary,
    build_aggregate_evidence_prepare_run_summary,
)
from tests.block_manifest_test_helpers import build_block_manifest
from tests.filter_test_helpers import build_test_coverage_bundle, resolved_filter_job
from tests.routing_test_helpers import build_current_route_artifacts_from_inputs

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
DOC_ID = "doc_lineage_test"


def _analysis_bundle() -> dict:
    return {
        "analysis_bundle_id": "prepare_analysis_lineage",
        "doc_id": DOC_ID,
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "masked_sample.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh", "source_path": None},
        "content_blocks": [
            {
                "block_id": "C0007",
                "kind": "heading",
                "order": 7,
                "meta": {"heading_level": 1, "heading_text_stripped": "临床安全性"},
                "analysis_text": "临床安全性",
            },
            {
                "block_id": "C0008",
                "kind": "paragraph",
                "order": 8,
                "meta": {},
                "analysis_text": "masked paragraph text",
            },
        ],
    }


def _metadata_result() -> MetadataResult:
    return MetadataResult(
        doc_id=DOC_ID,
        profile="clinical_trial_doc.doc_meta.profile_zh.v0_1",
        context_strategy="metadata_sources_v0_1",
        context_block_count=20,
        doc_type=MetadataField(value="IB", confidence="high"),
        fields={},
        warnings=[],
    )


def _doc_meta_bundle_from_result(result: MetadataResult) -> dict:
    base = result.to_dict()
    return metadata_result_to_doc_meta_bundle(
        result,
        doc_meta_bundle_id="doc_meta_lineage",
        summary=build_clinical_trial_doc_meta_summary(base),
        file_hash=LINEAGE_FILE_HASH,
    )


def _current_route_and_assessment_artifacts(
    *,
    analysis_bundle: dict,
    coverage_bundle: dict,
    block_manifest: dict,
    doc_meta_bundle: dict,
) -> tuple[dict, dict]:
    route_artifacts = build_current_route_artifacts_from_inputs(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
    )
    aggregate_bundle = route_artifacts["routed_bundles"]["aggregate"]
    semantic_result = prepare_aggregate_evidence_semantic_result(
        aggregate_bundle=aggregate_bundle,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        assessment_profile_ref=(
            CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref
        ),
        instructions=CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.instructions,
    )
    assessment_artifacts = build_aggregate_evidence_assessment_input_envelope(
        semantic_result=semantic_result,
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": aggregate_bundle["routed_unit_bundle_id"],
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": route_artifacts["routing_manifest"][
                "routing_manifest_id"
            ],
            "path": "routing_manifest.json",
        },
    )
    return route_artifacts, assessment_artifacts["assessment_input"]


def test_file_hash_propagates_through_pipeline_artifacts() -> None:
    analysis_bundle = _analysis_bundle()

    block_manifest = build_block_manifest(analysis_bundle)
    assert block_manifest["file_hash"] == LINEAGE_FILE_HASH

    zone_raw = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    zone_match = to_public_filter_payload(zone_raw)
    assert zone_match["file_hash"] == LINEAGE_FILE_HASH

    coverage_bundle = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_match,
        zone_key="ib_clinical_safety_zh",
        filter_run_id="filter_lineage_test",
    )
    assert coverage_bundle["file_hash"] == LINEAGE_FILE_HASH

    doc_meta_bundle = _doc_meta_bundle_from_result(_metadata_result())
    assert doc_meta_bundle["file_hash"] == LINEAGE_FILE_HASH

    route_artifacts, assessment_input = _current_route_and_assessment_artifacts(
        analysis_bundle=analysis_bundle,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
    )
    for routed_bundle in route_artifacts["routed_bundles"].values():
        assert routed_bundle["file_hash"] == LINEAGE_FILE_HASH
    assert route_artifacts["routing_manifest"]["source_refs"]
    assert assessment_input["file_hash"] == LINEAGE_FILE_HASH


def test_downstream_artifacts_forbid_source_path() -> None:
    analysis_bundle = _analysis_bundle()
    block_manifest = build_block_manifest(analysis_bundle)
    zone_raw = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    zone_match = to_public_filter_payload(zone_raw)
    coverage_bundle = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_match,
        zone_key="ib_clinical_safety_zh",
        filter_run_id="filter_lineage_test",
    )
    doc_meta_bundle = _doc_meta_bundle_from_result(_metadata_result())
    route_artifacts, assessment_input = _current_route_and_assessment_artifacts(
        analysis_bundle=analysis_bundle,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
    )

    for artifact in (
        block_manifest,
        to_public_filter_payload(zone_raw),
        coverage_bundle,
        doc_meta_bundle,
        *route_artifacts["routed_bundles"].values(),
        route_artifacts["routing_manifest"],
        assessment_input,
    ):
        serialized = json.dumps(artifact, ensure_ascii=False)
        assert "source_path" not in serialized


def test_run_summaries_include_file_hash_for_process_stages(tmp_path: Path) -> None:
    llm_input_bundle = {
        "llm_input_bundle_id": "llm_input_lineage",
        "doc_id": DOC_ID,
        "file_hash": LINEAGE_FILE_HASH,
        "zone_key": "ib_clinical_safety_zh",
        "units": [],
    }
    llm_input_path = tmp_path / "llm_input_bundle.json"
    llm_input_path.write_text(json.dumps(llm_input_bundle), encoding="utf-8")

    assess_summary = build_aggregate_evidence_assess_run_summary(
        run_id="evidence_source_preparation_assess_lineage",
        assessment_input=llm_input_bundle,
        assessment_input_path=llm_input_path,
        scope_assessments_path=None,
        scope_assessments=None,
        scope_assessment_review_path=None,
        scope_assessment_review=None,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        llm_mode="mock",
        zone_key="ib_clinical_safety_zh",
        phase="assess",
        completed_operation="aggregate_evidence.assess_heading_scopes",
    )
    assert assess_summary["file_hash"] == LINEAGE_FILE_HASH

    for name in (
        "coverage_bundle.json",
        "block_manifest.json",
        "doc_meta_bundle.json",
        "analysis_bundle.json",
        "routed_aggregate.json",
        "routing_manifest.json",
        "assessment_input.json",
        "assessment_input_preview.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    prepare_summary = build_aggregate_evidence_prepare_run_summary(
        run_id="evidence_source_preparation_prepare_lineage",
        doc_id=DOC_ID,
        zone_key="ib_clinical_safety_zh",
        coverage_bundle_path=tmp_path / "coverage_bundle.json",
        block_manifest_path=tmp_path / "block_manifest.json",
        doc_meta_bundle_path=tmp_path / "doc_meta_bundle.json",
        analysis_bundle_path=tmp_path / "analysis_bundle.json",
        routed_aggregate_bundle_path=tmp_path / "routed_aggregate.json",
        routing_manifest_path=tmp_path / "routing_manifest.json",
        assessment_input_path=tmp_path / "assessment_input.json",
        assessment_input_preview_path=tmp_path / "assessment_input_preview.json",
        assessment_input={
            "doc_id": DOC_ID,
            "file_hash": LINEAGE_FILE_HASH,
            "zone_key": "ib_clinical_safety_zh",
            "units": [],
        },
    )
    assert prepare_summary["file_hash"] == LINEAGE_FILE_HASH


def test_block_manifest_requires_analysis_bundle_file_hash() -> None:
    bundle = _analysis_bundle()
    bundle.pop("file_hash")
    with pytest.raises(ValueError, match="analysis_bundle.file_hash is required"):
        build_block_manifest(bundle)
