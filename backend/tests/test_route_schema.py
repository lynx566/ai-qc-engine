"""Route artifact schema validation tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing.route_bundles import build_routed_unit_bundle
from artifacts.routing.schema import (
    ROUTE_SCHEMA_VERSION,
    ROUTE_STAGE,
    validate_route_routing_manifest,
    validate_routed_unit_bundle,
)
from tests.route_test_fixtures import (
    LINEAGE_FILE_HASH,
    _block,
    _block_manifest,
    _coverage_bundle,
    _coverage_row,
    _minimal_doc_meta,
    _route_input_envelope_from_coverage_bundle,
    _route_units,
)

_ANALYSIS_BUNDLE = {
    "analysis_bundle_id": "prepare_analysis_test",
    "doc_id": "doc_test",
    "file_hash": LINEAGE_FILE_HASH,
}


def _valid_aggregate_bundle(*, units: list | None = None) -> dict:
    coverage = _coverage_bundle(_coverage_row("C0100", 100))
    manifest = _block_manifest(blocks=[_block("C0100", 100)])
    routed = _route_units(coverage=coverage, manifest=manifest)
    envelope = _route_input_envelope_from_coverage_bundle(coverage)
    return build_routed_unit_bundle(
        route="aggregate",
        units=units if units is not None else routed.units_by_route["aggregate"],
        route_input_envelope=envelope,
        block_manifest=manifest,
        doc_meta_bundle=_minimal_doc_meta(),
        analysis_bundle=_ANALYSIS_BUNDLE,
    )


def test_aggregate_bundle_validates() -> None:
    bundle = _valid_aggregate_bundle()
    validate_routed_unit_bundle(bundle, expected_route="aggregate")
    assert bundle["schema_version"] == ROUTE_SCHEMA_VERSION
    assert bundle["stage"] == ROUTE_STAGE
    assert bundle["source_refs"]["route_input_id"] == "coverage_route_test"
    assert bundle["source_refs"]["doc_meta_bundle_id"] == "doc_meta_test"
    assert "coverage_bundle_id" not in bundle["source_refs"]


def test_empty_case_table_unknown_bundles_valid() -> None:
    coverage = _coverage_bundle(_coverage_row("C0100", 100))
    manifest = _block_manifest(blocks=[_block("C0100", 100)])
    envelope = _route_input_envelope_from_coverage_bundle(coverage)
    for route in ("case", "table", "unknown"):
        bundle = build_routed_unit_bundle(
            route=route,  # type: ignore[arg-type]
            units=[],
            route_input_envelope=envelope,
            block_manifest=manifest,
            doc_meta_bundle=_minimal_doc_meta(),
            analysis_bundle=_ANALYSIS_BUNDLE,
        )
        validate_routed_unit_bundle(bundle, expected_route=route)  # type: ignore[arg-type]
        assert bundle["units"] == []


def test_bundle_route_unit_route_mismatch_raises() -> None:
    bundle = _valid_aggregate_bundle()
    bundle["units"] = (
        [{**bundle["units"][0], "route": "case"}]
        if bundle["units"]
        else [{"unit_id": "TU0001", "route": "case"}]
    )
    with pytest.raises(ValueError, match="does not match bundle route"):
        validate_routed_unit_bundle(bundle, expected_route="aggregate")


def test_duplicate_unit_ids_raises() -> None:
    bundle = _valid_aggregate_bundle()
    if not bundle["units"]:
        bundle["units"] = [
            {"unit_id": "TU0001", "route": "aggregate"},
            {"unit_id": "TU0001", "route": "aggregate"},
        ]
    else:
        bundle["units"] = [bundle["units"][0], {**bundle["units"][0]}]
    with pytest.raises(ValueError, match="duplicate unit_id"):
        validate_routed_unit_bundle(bundle, expected_route="aggregate")


def test_invalid_route_raises() -> None:
    bundle = _valid_aggregate_bundle()
    bundle["route"] = "not_a_route"
    with pytest.raises(ValueError, match="invalid route"):
        validate_routed_unit_bundle(bundle)


def test_source_identity_mismatch_raises() -> None:
    bundle = _valid_aggregate_bundle()
    with pytest.raises(ValueError, match="doc_id mismatch"):
        validate_routed_unit_bundle(
            bundle,
            expected_doc_id="doc_other",
        )


def test_route_artifact_rejects_llm_fields() -> None:
    bundle = _valid_aggregate_bundle()
    bundle["instructions"] = "do not tag"
    with pytest.raises(ValueError, match="must not contain"):
        validate_routed_unit_bundle(bundle)


def test_routing_manifest_validates() -> None:
    from artifacts.routing.route_bundles import build_route_stage_artifacts

    coverage = _coverage_bundle(_coverage_row("C0100", 100))
    manifest = _block_manifest(blocks=[_block("C0100", 100)])
    routed = _route_units(coverage=coverage, manifest=manifest)
    artifacts = build_route_stage_artifacts(
        routed=routed,
        route_input_envelope=_route_input_envelope_from_coverage_bundle(coverage),
        block_manifest=manifest,
        doc_meta_bundle=_minimal_doc_meta(),
        analysis_bundle=_ANALYSIS_BUNDLE,
    )
    validate_route_routing_manifest(artifacts["routing_manifest"])
    assert "route_artifact_files" in artifacts["routing_manifest"]
    assert "route_input_files" not in artifacts["routing_manifest"]
    assert artifacts["routing_manifest"]["source_refs"]["route_input_id"] == (
        "coverage_route_test"
    )


def test_route_bundle_rejects_retired_context_sentences() -> None:
    bundle = _valid_aggregate_bundle()
    assert bundle["units"], "fixture must contain aggregate units"
    unit = dict(bundle["units"][0])
    unit["context_sentences"] = [
        {
            "sentence_id": "CTX0001",
            "kind": "heading",
            "text": "Legacy",
            "source_block_id": "H0001",
        }
    ]
    with pytest.raises(ValueError, match="context_sentences"):
        validate_routed_unit_bundle(
            {**bundle, "units": [unit]},
            expected_route="aggregate",
        )
