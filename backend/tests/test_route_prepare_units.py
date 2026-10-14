"""Unit tests for route unit preparation via projected sources."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing import routing_manifest_units
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    canonicalize_aggregate_route_units,
)
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from tests.route_test_fixtures import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_manifest,
    _block,
    _block_manifest,
    _coverage_bundle,
    _coverage_row,
    _minimal_doc_meta,
    _projected_sources_from_coverage_bundle,
    _route_units,
    _table_block,
)


def test_aggregate_heading_routes_to_aggregate() -> None:
    heading = ["12 临床安全性", "12.3 不良事件概述"]
    routed = _route_units(
        coverage=_coverage_bundle(_coverage_row("C0100", 100, heading_path=heading)),
        manifest=_block_manifest(
            blocks=[_block("C0100", 100, heading_path=heading, analysis_text="agg")],
        ),
    )
    assert routed.route_counts["aggregate_unit_count"] == 1
    assert routed.route_counts["case_unit_count"] == 0
    unit = routed.units_by_route["aggregate"][0]
    assert unit["route"] == "aggregate"
    assert unit["source_block_ids"] == ["C0100"]


def test_case_heading_routes_to_case() -> None:
    heading = ["12 临床安全性", "12.3.2 病例叙述"]
    routed = _route_units(
        coverage=_coverage_bundle(_coverage_row("C0021", 20, heading_path=heading)),
        manifest=_block_manifest(
            blocks=[_block("C0021", 20, heading_path=heading, analysis_text="case body")],
        ),
    )
    assert routed.route_counts["case_unit_count"] == 1
    unit = routed.units_by_route["case"][0]
    assert unit["route"] == "case"
    assert unit["unit_id"] == "CU0001"


def test_table_unit_routes_to_table() -> None:
    heading = ["12 临床安全性"]
    routed = _route_units(
        coverage=_coverage_bundle(
            _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
        ),
        manifest=_block_manifest(
            blocks=[],
            table_blocks=[_table_block("T0001", 10, heading_path=heading)],
        ),
    )
    assert routed.route_counts["table_unit_count"] == 1
    unit = routed.units_by_route["table"][0]
    assert unit["unit_kind"] == "table_unit"
    assert unit["route"] == "table"
    assert unit["source_table_ids"] == ["T0001"]


def test_unknown_structure_routes_to_unknown() -> None:
    heading = ["12 临床安全性"]
    routed = _route_units(
        coverage=_coverage_bundle(
            _coverage_row("C0030", 30, block_kind="figure", heading_path=heading),
        ),
        manifest=_block_manifest(
            blocks=[_block("C0030", 30, kind="figure", heading_path=heading)],
        ),
    )
    assert routed.route_counts["unknown_unit_count"] == 1
    unit = routed.units_by_route["unknown"][0]
    assert unit["route"] == "unknown"
    assert unit["unit_id"] == "UU0001"
    assert unit["sentences"]
    assert "candidate_text" not in unit


def test_mixed_routes_counts_order_and_no_duplicates() -> None:
    heading_agg = ["12 临床安全性", "12.3 不良事件概述"]
    heading_case = ["12 临床安全性", "病例叙述"]
    heading_table = ["12 临床安全性", "汇总表"]
    coverage = _coverage_bundle(
        _coverage_row("C0100", 100, heading_path=heading_agg),
        _coverage_row("C0200", 200, heading_path=heading_case),
        _coverage_row("T0001", 300, block_kind="table", heading_path=heading_table),
        _coverage_row("C0030", 400, block_kind="figure", heading_path=["12 临床安全性"]),
    )
    manifest = _block_manifest(
        blocks=[
            _block("C0100", 100, heading_path=heading_agg, analysis_text="agg"),
            _block("C0200", 200, heading_path=heading_case, analysis_text="case"),
            _block("C0030", 400, kind="figure", heading_path=["12 临床安全性"]),
        ],
        table_blocks=[_table_block("T0001", 300, heading_path=heading_table)],
    )
    routed = _route_units(coverage=coverage, manifest=manifest)

    assert routed.route_counts["aggregate_unit_count"] == 1
    assert routed.route_counts["case_unit_count"] == 1
    assert routed.route_counts["table_unit_count"] == 1
    assert routed.route_counts["unknown_unit_count"] == 1
    assert routed.route_counts["total_routed_unit_count"] == 4

    unit_ids = [unit["unit_id"] for unit in routed.all_units]
    assert len(unit_ids) == len(set(unit_ids))
    assert unit_ids == ["TU0001", "TTU0001", "CU0001", "UU0001"]

    manifest_units = routing_manifest_units(routed.units_by_route)
    assert [entry["unit_id"] for entry in manifest_units] == unit_ids


def test_provenance_fields_preserved_through_routing() -> None:
    heading = ["12 临床安全性", "12.3 不良事件"]
    coverage = _coverage_bundle(
        _coverage_row("C0009", 8, heading_path=heading),
        _coverage_row("C0010", 9, block_kind="table_caption", heading_path=heading),
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
    )
    manifest = _block_manifest(
        blocks=[
            _block("C0009", 8, heading_path=heading, analysis_text="aggregate body"),
            _block("C0010", 9, kind="table_caption", heading_path=heading, analysis_text="表1"),
        ],
        table_blocks=[_table_block("T0001", 10, heading_path=heading)],
    )
    routed = _route_units(coverage=coverage, manifest=manifest)

    aggregate = routed.units_by_route["aggregate"][0]
    table = routed.units_by_route["table"][0]
    assert aggregate["source_block_ids"] == ["C0009"]
    assert aggregate["source_zone_key"] == "ib_clinical_safety_zh"
    assert aggregate["route_basis"] == "route_matched_terms"
    assert "不良事件" in aggregate["route_matched_terms"]
    assert table["source_table_ids"] == ["T0001"]
    assert table["source_block_ids"] == ["C0010"]


_ROUTING_PROVENANCE_KEYS = (
    "route",
    "route_basis",
    "route_matched_terms",
    "heading_path",
    "source_block_ids",
    "source_zone_key",
    "source_stage",
    "source_component_ids",
    "overview_decompose_bundle_id",
)


def _routing_provenance_slice(unit: dict) -> dict:
    return {key: unit.get(key) for key in _ROUTING_PROVENANCE_KEYS}


def test_canonicalization_preserves_routing_and_provenance_fields() -> None:
    heading_agg = ["12 临床安全性", "12.3 不良事件概述"]
    coverage = _coverage_bundle(_coverage_row("C0100", 100, heading_path=heading_agg))
    manifest = _block_manifest(
        blocks=[_block("C0100", 100, heading_path=heading_agg, analysis_text="agg")],
    )
    routed = _route_units(coverage=coverage, manifest=manifest)
    before = routed.units_by_route["aggregate"][0]
    after = canonicalize_aggregate_route_units(routed.units_by_route)["aggregate"][0]

    assert _routing_provenance_slice(before) == _routing_provenance_slice(after)
    assert after["unit_id"] == before["unit_id"]


def test_canonical_entry_is_route_prepare_units_from_projected_sources() -> None:
    heading = ["12 临床安全性", "12.3 不良事件概述"]
    coverage = _coverage_bundle(_coverage_row("C0100", 100, heading_path=heading))
    manifest = _block_manifest(
        blocks=[_block("C0100", 100, heading_path=heading, analysis_text="agg")],
    )
    routed = route_prepare_units_from_projected_sources(
        projected_sources=_projected_sources_from_coverage_bundle(coverage),
        block_manifest=manifest,
        analysis_bundle=_analysis_bundle_for_manifest(manifest),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    assert routed.route_counts["aggregate_unit_count"] == 1
