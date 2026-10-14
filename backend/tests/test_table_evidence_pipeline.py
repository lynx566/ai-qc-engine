from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from steps.filter import extract_zones_from_bundle
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.block_manifest_test_helpers import build_block_manifest
from tests.clinical_program_fixtures import canonical_clinical_program_fields
from tests.extract_test_helpers import extract_docx_for_test
from tests.filter_test_helpers import build_test_coverage_bundle, resolved_filter_job
from tests.route_test_fixtures import _route_units

SAFETY_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "legacy_ib_v1_0"
    / "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15.docx"
)

ZONE_KEY = "ib_clinical_safety_zh"
FILTER_RUN_ID = "filter_test_table_evidence"


def _minimal_doc_meta(*, doc_id: str, file_hash: str) -> dict:
    return {
        "doc_meta_bundle_id": "doc_meta_test",
        "doc_id": doc_id,
        "file_hash": file_hash,
        "summary": {"doc_type": "IB"},
    }


def _coverage_row(coverage: list[dict], block_id: str) -> dict:
    for row in coverage:
        if row.get("block_id") == block_id:
            return row
    raise AssertionError(f"missing coverage row {block_id!r}")


def test_table_evidence_end_to_end_from_safety_sample() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    analysis = prepare_analysis_bundle(
        asdict(bundle),
        profile=None,
        language="zh",
        **canonical_clinical_program_fields(),
    )
    analysis_bundle = dict(analysis.analysis_bundle)
    analysis_bundle["analysis_bundle_id"] = "prepare_analysis_test"

    block_manifest = build_block_manifest(analysis_bundle)
    zone_result = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    coverage_bundle = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    t0001 = _coverage_row(coverage_bundle["coverage"], "T0001")
    assert t0001["block_kind"] == "table"
    assert t0001["selected_by_filter"] is True
    assert t0001.get("doc_order_index") is not None
    assert t0001.get("heading_path")

    routed = _route_units(coverage=coverage_bundle, manifest=block_manifest)

    table_unit_ids = [
        unit.get("source_table_ids", [None])[0]
        for unit in routed.units_by_route["table"]
        if unit.get("unit_kind") == "table_unit"
    ]
    assert "T0001" in table_unit_ids
    table_unit = next(
        unit
        for unit in routed.units_by_route["table"]
        if unit.get("source_table_ids") == ["T0001"]
    )
    assert table_unit["unit_kind"] == "table_unit"
    assert table_unit["route"] == "table"
    body = next(
        component
        for component in table_unit["components"]
        if component["component_role"] == "table_body"
    )
    assert body.get("text")

    aggregate_block_ids = {
        block_id
        for unit in routed.units_by_route["aggregate"]
        for block_id in unit.get("source_block_ids") or []
    }
    assert "C0009" in aggregate_block_ids
    assert "T0001" not in aggregate_block_ids


def test_table_outside_zone_excluded_from_coverage_and_table_units() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    analysis = prepare_analysis_bundle(
        asdict(bundle),
        profile=None,
        language="zh",
        **canonical_clinical_program_fields(),
    )
    analysis_bundle = dict(analysis.analysis_bundle)
    analysis_bundle["analysis_bundle_id"] = "prepare_analysis_test"

    block_manifest = build_block_manifest(analysis_bundle)
    zone_result = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    for zone in zone_result["matched_zones"]:
        zone["table_blocks"] = [
            block
            for block in zone.get("table_blocks") or []
            if block.get("block_id") != "T0001"
        ]

    coverage_bundle = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    t0001 = _coverage_row(coverage_bundle["coverage"], "T0001")
    assert t0001["selected_by_filter"] is False

    routed = _route_units(coverage=coverage_bundle, manifest=block_manifest)
    assert routed.units_by_route["table"] == []
