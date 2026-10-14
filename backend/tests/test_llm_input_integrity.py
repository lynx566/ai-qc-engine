"""Tests for canonical routed-unit and aggregate_prepare integrity owners."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_prepare_integrity import (
    compact_unit_integrity_summary,
    validate_aggregate_prepare_handoff,
)
from artifacts.routing.unit_integrity import validate_routed_unit_structural_integrity
from tests.route_test_fixtures import _route_units

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


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


def _coverage_bundle(*rows: dict) -> dict:
    return {
        "coverage_bundle_id": "coverage_integrity_test",
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
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": block_id,
        },
    }


def _block_manifest(*blocks: dict) -> dict:
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": list(blocks),
        "table_blocks": [],
    }


def _build_valid_tag_prepare_outputs() -> tuple[dict, dict, dict, list[dict]]:
    coverage = _coverage_bundle(
        _coverage_row("C0001", 1, heading_path=["12 临床安全性", "12.3 不良事件概述"]),
        _coverage_row("C0002", 2, heading_path=["12 临床安全性", "12.3 不良事件概述"]),
    )
    manifest = _block_manifest(
        _block(
            "C0001",
            1,
            heading_path=["12 临床安全性", "12.3 不良事件概述"],
            analysis_text="First paragraph.",
        ),
        _block(
            "C0002",
            2,
            heading_path=["12 临床安全性", "12.3 不良事件概述"],
            analysis_text="Second paragraph.",
        ),
    )
    routed = _route_units(coverage=coverage, manifest=manifest)
    all_units = list(routed.all_units)
    llm_input_bundle = {"units": all_units}
    return coverage, manifest, llm_input_bundle, all_units


def test_structural_integrity_passes_for_normal_grouped_units() -> None:
    _coverage, manifest, llm_input_bundle, _units = _build_valid_tag_prepare_outputs()
    issues, summary = validate_routed_unit_structural_integrity(
        units=llm_input_bundle["units"],
        block_manifest=manifest,
    )
    assert issues == []
    assert summary["empty_primary_body_unit_count"] == 0
    assert summary["source_block_without_primary_sentence_count"] == 0


def test_structural_integrity_flags_source_block_without_primary_sentence() -> None:
    _coverage, manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    unit = dict(units[0])
    unit["unit_id"] = "TU0006"
    unit["source_block_ids"] = ["C0001", "C0041"]
    issues, summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    assert summary["source_block_without_primary_sentence_count"] == 1
    issue = next(
        item
        for item in issues
        if item["code"] == "unit_source_block_without_primary_sentence"
    )
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0006"
    assert issue["block_id"] == "C0041"


def test_structural_integrity_flags_empty_primary_body_unit() -> None:
    _coverage, manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    unit = dict(units[0])
    unit["unit_id"] = "TU0003"
    unit["sentences"] = [
        {
            "sentence_id": "S0001",
            "text": "   ",
            "source_block_id": str(unit["source_block_ids"][0]),
        }
    ]
    issues, summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    assert summary["empty_primary_body_unit_count"] == 1
    issue = next(item for item in issues if item["code"] == "empty_primary_body_unit")
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0003"


def test_structural_integrity_flags_missing_manifest_block() -> None:
    _coverage, manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    unit = dict(units[0])
    unit["unit_id"] = "TU0002"
    unit["source_block_ids"] = ["C0024"]
    unit["sentences"] = [
        {
            "sentence_id": "S0001",
            "text": "orphan block",
            "source_block_id": "C0024",
        }
    ]
    issues, summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    assert summary["manifest_missing_block_count"] == 1
    issue = next(item for item in issues if item["code"] == "manifest_block_missing")
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0002"
    assert issue["block_id"] == "C0024"


def test_structural_integrity_flags_empty_analysis_text() -> None:
    _coverage, _manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    manifest = _block_manifest(
        _block("C0024", 1, analysis_text="   "),
    )
    unit = dict(units[0])
    unit["unit_id"] = "TU0002"
    unit["source_block_ids"] = ["C0024"]
    unit["sentences"] = [
        {
            "sentence_id": "S0001",
            "text": "placeholder",
            "source_block_id": "C0024",
        }
    ]
    issues, summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    assert summary["manifest_empty_analysis_text_count"] == 1
    issue = next(
        item for item in issues if item["code"] == "manifest_block_empty_analysis_text"
    )
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0002"
    assert issue["block_id"] == "C0024"


def test_structural_integrity_flags_sentence_id_mismatch() -> None:
    _coverage, manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    unit = dict(units[0])
    unit["unit_id"] = "TU0004"
    unit["sentences"] = []
    issues, _summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    issue = next(item for item in issues if item["code"] == "empty_primary_body_unit")
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0004"


def test_structural_integrity_does_not_flag_heading_context_without_candidate_sentence() -> None:
    coverage = _coverage_bundle(
        _coverage_row("H0001", 1, block_kind="heading", heading_path=["Section"]),
        _coverage_row("C0001", 2, heading_path=["Section"]),
    )
    manifest = _block_manifest(
        _block("H0001", 1, kind="heading", analysis_text="Section", heading_path=["Section"]),
        _block("C0001", 2, analysis_text="Body", heading_path=["Section"]),
    )
    routed = _route_units(coverage=coverage, manifest=manifest)
    unit = routed.units_by_route["aggregate"][0]
    assert unit["context_block_ids"] == ["H0001"]
    assert unit["source_block_ids"] == ["C0001"]
    assert unit["context_block_ids"] == ["H0001"]
    issues, summary = validate_routed_unit_structural_integrity(
        units=routed.units_by_route["aggregate"],
        block_manifest=manifest,
    )
    assert summary["source_block_without_primary_sentence_count"] == 0
    assert not any(
        issue["code"] == "unit_source_block_without_primary_sentence"
        for issue in issues
    )


def test_structural_integrity_reports_aggregate_contract_violation() -> None:
    _coverage, manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    unit = dict(units[0])
    unit["unit_id"] = "TU0007"
    unit.pop("route_basis")
    issues, summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    assert summary["aggregate_unit_count"] == 1
    assert summary["aggregate_contract_violation_count"] == 1
    issue = next(
        item for item in issues if item["code"] == "aggregate_unit_contract_violation"
    )
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0007"


def test_structural_integrity_flags_multiple_source_component_ids() -> None:
    _coverage, manifest, _llm_input_bundle, units = _build_valid_tag_prepare_outputs()
    unit = dict(units[0])
    unit["unit_id"] = "TU0008"
    unit["source_component_ids"] = ["OVC_A", "OVC_B"]
    issues, summary = validate_routed_unit_structural_integrity(
        units=[unit],
        block_manifest=manifest,
    )
    assert summary["aggregate_provenance_violation_count"] >= 1
    issue = next(
        item
        for item in issues
        if item["code"] == "aggregate_multiple_source_component_ids"
    )
    assert issue["severity"] == "error"
    assert issue["unit_id"] == "TU0008"


def test_compact_unit_integrity_summary_uses_report_summary() -> None:
    from tests.test_assessment_input_compact import (
        _aggregate_unit,
        _compact_assessment_input_from_units,
    )

    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    report = validate_aggregate_prepare_handoff(
        assessment_input=assessment_input,
        runtime_context=runtime_context,
        aggregate_units=units,
    )
    compact = compact_unit_integrity_summary(report)
    assert compact["error_count"] == report["summary"]["error_count"]
    assert compact["warning_count"] == report["summary"]["warning_count"]
