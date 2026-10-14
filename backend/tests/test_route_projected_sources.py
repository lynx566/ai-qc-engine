"""Canonical Route entry from projected sources."""

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
from artifacts.routing import ROUTES
from artifacts.routing.types import RoutedUnitSet
from operations.filter_output_projection.contracts import (
    ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
    CanonicalSourceRef,
    ProjectedSource,
)
from operations.filter_output_projection.fan_in import (
    select_projected_sources_for_semantic_module,
)
from steps.route import run_from_projected_sources
from plugins.clinical_trial_doc.routing.projected_sources import (
    route_prepare_units_from_projected_sources,
    validate_projected_sources_semantic_module,
)
from tests.projection_test_helpers import (
    assembled_projected_source,
    projected_sentence,
    raw_projected_source,
)
from tests.route_test_fixtures import (
    _analysis_bundle_for_manifest,
    _minimal_doc_meta,
    _projection_fan_in_input_for_step_result,
    _projection_input_refs_dicts,
)
from tests.test_filter_output_projection_direct import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_zone_match,
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
)
from tests.test_filter_output_projection_overview import (
    _assessment_response,
    _paragraph_block,
    _run_overview,
    _zone_match_bundle,
)

PROJECTED_SOURCES_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "routing"
    / "projected_sources.py"
)


def _analysis_bundle(
    *,
    doc_id: str,
    block_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if block_manifest is not None:
        bundle = _analysis_bundle_for_manifest(block_manifest)
        bundle["doc_id"] = doc_id
        return bundle
    return {
        "analysis_bundle_id": "prepare_analysis_regression",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "content_blocks": [],
        "table_blocks": [],
    }


def _routed_unit_set(route_artifacts: dict[str, Any]) -> RoutedUnitSet:
    units_by_route = route_artifacts["units_by_route"]
    return RoutedUnitSet(
        units_by_route={route: list(units_by_route[route]) for route in ROUTES},
        route_counts=dict(route_artifacts["route_counts"]),
        all_units=tuple(
            unit for route in ROUTES for unit in units_by_route[route]
        ),
    )


def _route_from_projected_sources(
    *,
    projected_sources: tuple[ProjectedSource, ...],
    block_manifest: dict[str, Any],
    projection_input_refs: tuple[dict[str, str], ...] | None = None,
) -> RoutedUnitSet:
    doc_id = str(block_manifest["doc_id"])
    file_hash = str(block_manifest.get("file_hash") or LINEAGE_FILE_HASH)
    refs = projection_input_refs or (
        {
            "filter_output_projection_bundle_id": (
                "filter_output_projection_ib_clinical_safety_test_route"
            ),
            "filter_job_id": "ib_clinical_safety",
            "zone_key": "ib_clinical_safety_zh",
        },
    )
    result = run_from_projected_sources(
        projected_sources=projected_sources,
        block_manifest=block_manifest,
        doc_meta_bundle=_minimal_doc_meta(doc_id=doc_id),
        analysis_bundle=_analysis_bundle(
            doc_id=doc_id,
            block_manifest=block_manifest,
        ),
        expected_semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        route_executor=build_clinical_trial_doc_consistency_qc_application_composition().projected_source_route_executor,
        projection_input_refs=refs,
        projection_doc_id=doc_id,
        projection_file_hash=file_hash,
    )
    return _routed_unit_set(result.route_artifacts)


def test_overview_table_origin_assembled_source_routes_aggregate_not_table() -> None:
    source = assembled_projected_source(
        semantic_module_id="clinical_safety",
        sentences=(
            projected_sentence(
                sentence_id="T0001:S001",
                text="表格正文",
                source_block_id="T0001",
            ),
        ),
        source_refs=(
            CanonicalSourceRef(
                refs={"block_id": "T0001", "source_group": "table_blocks"}
            ),
        ),
        heading_path=["表格"],
    )
    routed = _route_prepare(
        projected_sources=[source],
        block_manifest={
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "blocks": [],
            "table_blocks": [
                {
                    "block_id": "T0001",
                    "kind": "table",
                    "analysis_text": "表格正文",
                    "heading_path": ["表格"],
                }
            ],
        },
    )
    aggregate_units = routed.units_by_route["aggregate"]
    table_units = routed.units_by_route["table"]
    assert len(aggregate_units) == 1
    assert table_units == []
    assert aggregate_units[0]["route_basis"] == "projected_assembled_semantic"


def test_module_mismatch_rejected_at_route_boundary() -> None:
    source = raw_projected_source(
        semantic_module_id="efficacy",
        block_id="C0001",
    )
    with pytest.raises(ValueError, match="does not match expected"):
        validate_projected_sources_semantic_module(
            [source],
            expected_semantic_module_id="clinical_safety",
        )


def test_projected_route_processor_does_not_branch_on_producer_identity() -> None:
    forbidden_patterns = (
        "overview_semantic_decomposition",
        "filter_job_id ==",
        "strategy_id ==",
        'source_stage == "overview"',
    )
    text = PROJECTED_SOURCES_PATH.read_text(encoding="utf-8")
    for pattern in forbidden_patterns:
        assert pattern not in text


def test_overview_and_direct_sources_both_survive_fan_in_route() -> None:
    from steps.project_filter_output import run as run_project_filter_output
    from plugins.clinical_trial_doc.filter_output_projection import (
        DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
        build_overview_semantic_decomposition_facade,
    )
    from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    )
    from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
        IB_OVERVIEW_FILTER_PROFILE_ZH,
    )
    from tests.test_filter_output_projection_overview import (
        FakeOverviewProvider,
        _assessment_response,
        _paragraph_block,
        _zone_match_bundle,
    )

    safety_profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    overview_profile = IB_OVERVIEW_FILTER_PROFILE_ZH
    safety_zone, _safety_coverage, block_manifest, safety_analysis = _filter_artifacts_for_profile(
        safety_profile
    )
    overview_zone = _zone_match_bundle(
        blocks=[_paragraph_block("C2000", "概述安全性。")]
    )
    overview_zone["doc_id"] = safety_zone["doc_id"]
    overview_zone["file_hash"] = LINEAGE_FILE_HASH
    overview_analysis = _analysis_bundle_for_zone_match(overview_zone)

    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    direct_result = run_project_filter_output(
        projection_input=_projection_input_for_profile(safety_profile, safety_zone),
        analysis_bundle=safety_analysis,
        job=composition.resolve_filter_output_projection_job(safety_profile.filter_job_id),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    prepared_alias = "O001"
    overview_result = run_project_filter_output(
        projection_input=_projection_input_for_profile(overview_profile, overview_zone),
        analysis_bundle=overview_analysis,
        job=composition.resolve_filter_output_projection_job(overview_profile.filter_job_id),
        facade=build_overview_semantic_decomposition_facade(
            llm_provider=FakeOverviewProvider(
                response_text=_assessment_response(
                    [(prepared_alias, ["clinical_safety"])]
                )
            )
        ),
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _projection_fan_in_input_for_step_result(
                direct_result,
                run_id="fan_in_direct",
            ),
            _projection_fan_in_input_for_step_result(
                overview_result,
                run_id="fan_in_overview",
            ),
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert len(selection.selected_projected_sources) >= 2
    routed = _route_from_projected_sources(
        projected_sources=selection.selected_projected_sources,
        block_manifest=block_manifest,
        projection_input_refs=_projection_input_refs_dicts(selection),
    )
    route_bases = {unit.get("route_basis") for unit in routed.all_units}
    assert "projected_assembled_semantic" in route_bases
    assert routed.route_counts["total_routed_unit_count"] >= 2


def _block_manifest(
    *,
    blocks: list[dict[str, Any]] | None = None,
    table_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": list(blocks or []),
        "table_blocks": table_blocks or [],
    }


def _route_prepare(
    *,
    projected_sources: list[ProjectedSource],
    block_manifest: dict[str, Any],
) -> RoutedUnitSet:
    return route_prepare_units_from_projected_sources(
        projected_sources=projected_sources,
        block_manifest=block_manifest,
        analysis_bundle=_analysis_bundle_for_manifest(block_manifest),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )


def test_overview_retained_block_count_equals_assembled_route_tu_count() -> None:
    blocks = [
        _paragraph_block("C4000", "上下文。", heading_path=["执行概要"]),
        _paragraph_block("C4001", "安全性一。", heading_path=["执行概要"]),
        _paragraph_block("C4002", "安全性二。", heading_path=["执行概要"]),
    ]
    projection = _run_overview(
        _zone_match_bundle(blocks=blocks),
        _assessment_response(
            [
                ("O001", ["shared_context"]),
                ("O002", ["clinical_safety"]),
                ("O003", ["clinical_safety"]),
            ]
        ),
    )

    routed = _route_prepare(
        projected_sources=list(projection.projected_sources),
        block_manifest=_block_manifest(blocks=blocks),
    )

    assert len(projection.projected_sources) == len(routed.all_units) == 3
    assert all(
        len({sentence["source_block_id"] for sentence in unit["sentences"]}) == 1
        for unit in routed.all_units
    )


def test_canonical_signature_does_not_accept_zone_key() -> None:
    import inspect

    parameters = inspect.signature(run_from_projected_sources).parameters
    assert "zone_key" not in parameters
    assert "projected_sources" in parameters
    assert "expected_semantic_module_id" in parameters
    assert "route_executor" in parameters


def test_assembled_source_missing_sentences_fails_closed() -> None:
    source = ProjectedSource(
        semantic_module_id="clinical_safety",
        source_refs=(
            CanonicalSourceRef(refs={"block_id": "C0001", "source_group": "blocks"}),
        ),
        representation_kind=ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
        sentences=(),
        payload={},
    )
    manifest = _block_manifest()
    with pytest.raises(ValueError, match="sentences"):
        _route_prepare(projected_sources=[source], block_manifest=manifest)


def test_unknown_representation_kind_rejected_at_contract() -> None:
    with pytest.raises(ValueError, match="representation_kind"):
        ProjectedSource(
            semantic_module_id="clinical_safety",
            source_refs=(
                CanonicalSourceRef(refs={"block_id": "C0001", "source_group": "blocks"}),
            ),
            representation_kind="unknown_representation",
            sentences=(
                projected_sentence(
                    sentence_id="C0001:S001",
                    text="正文",
                    source_block_id="C0001",
                ),
            ),
        )


def test_raw_source_payload_key_does_not_force_assembled() -> None:
    source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id="C0001",
        heading_path=["摘要"],
        sentences=(
            projected_sentence(
                sentence_id="C0001:S001",
                text="正文",
                source_block_id="C0001",
            ),
        ),
    )
    manifest = _block_manifest(
        blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "正文",
                "heading_path": ["摘要"],
            }
        ]
    )
    routed = _route_prepare(projected_sources=[source], block_manifest=manifest)
    assert all(
        unit.get("route_basis") != "projected_assembled_semantic"
        for unit in routed.all_units
    )


def test_representation_independent_of_producer_lineage() -> None:
    assembled = assembled_projected_source(
        semantic_module_id="clinical_safety",
        sentences=(
            projected_sentence(
                sentence_id="C0001:S001",
                text="正文",
                source_block_id="C0001",
            ),
        ),
        heading_path=["摘要"],
        lineage={"zone_key": "some_other_zone"},
    )
    routed = _route_prepare(
        projected_sources=[assembled],
        block_manifest=_block_manifest(),
    )
    aggregate_units = routed.units_by_route["aggregate"]
    assert len(aggregate_units) == 1
    assert aggregate_units[0]["route_basis"] == "projected_assembled_semantic"
    assert aggregate_units[0]["source_zone_key"] == "some_other_zone"

    raw = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id="C0001",
        heading_path=["摘要"],
        lineage={"zone_key": "ib_overview_zh"},
        sentences=(
            projected_sentence(
                sentence_id="C0001:S001",
                text="正文",
                source_block_id="C0001",
            ),
        ),
    )
    manifest = _block_manifest(
        blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "正文",
                "heading_path": ["摘要"],
            }
        ]
    )
    routed_raw = _route_prepare(projected_sources=[raw], block_manifest=manifest)
    assert all(
        unit.get("route_basis") != "projected_assembled_semantic"
        for unit in routed_raw.all_units
    )


def test_mixed_origin_zone_provenance_preserved() -> None:
    direct = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id="C0001",
        heading_path=["安全性"],
        lineage={"filter_job_id": "ib_clinical_safety", "zone_key": "clinical_safety_zone"},
        sentences=(
            projected_sentence(
                sentence_id="C0001:S001",
                text="安全性正文",
                source_block_id="C0001",
            ),
        ),
    )
    overview = assembled_projected_source(
        semantic_module_id="clinical_safety",
        sentences=(
            projected_sentence(
                sentence_id="C2000:S001",
                text="概述安全性",
                source_block_id="C2000",
            ),
        ),
        heading_path=["概述"],
        lineage={"filter_job_id": "ib_overview", "zone_key": "overview_zone"},
    )
    routed = _route_from_projected_sources(
        projected_sources=(direct, overview),
        block_manifest=_block_manifest(
            blocks=[
                {
                    "block_id": "C0001",
                    "kind": "paragraph",
                    "analysis_text": "安全性正文",
                    "heading_path": ["安全性"],
                },
                {
                    "block_id": "C2000",
                    "kind": "paragraph",
                    "analysis_text": "概述安全性",
                    "heading_path": ["概述"],
                },
            ]
        ),
    )
    zone_keys = {unit.get("source_zone_key") for unit in routed.all_units}
    assert "clinical_safety_zone" in zone_keys
    assert "overview_zone" in zone_keys
    assert routed.route_counts["total_routed_unit_count"] >= 2


def test_raw_adapter_preserves_manifest_order_for_case_merge() -> None:
    heading_case = ["12 临床安全性", "12.3.2 病例叙述"]
    manifest = _block_manifest(
        blocks=[
            {
                "block_id": "CH001",
                "kind": "heading",
                "order": 1,
                "heading_path": heading_case,
                "analysis_text": "12.3.2 病例叙述",
            },
            {
                "block_id": "CP001",
                "kind": "paragraph",
                "order": 2,
                "heading_path": heading_case,
                "analysis_text": "case one",
            },
            {
                "block_id": "CP002",
                "kind": "paragraph",
                "order": 3,
                "heading_path": heading_case,
                "analysis_text": "case two",
            },
        ]
    )
    projected_sources = (
        raw_projected_source(
            semantic_module_id="clinical_safety",
            block_id="CP001",
            heading_path=heading_case,
            lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z1"},
        ),
        raw_projected_source(
            semantic_module_id="clinical_safety",
            block_id="CP002",
            heading_path=heading_case,
            lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z1"},
        ),
    )
    routed = _route_prepare(projected_sources=projected_sources, block_manifest=manifest)
    case_units = routed.units_by_route["case"]
    assert len(case_units) == 1
    assert case_units[0]["source_block_ids"] == ["CP001", "CP002"]


def test_raw_adapter_enriches_heading_context_from_block_manifest() -> None:
    heading = ["Section A"]
    manifest = _block_manifest(
        blocks=[
            {
                "block_id": "CHA001",
                "kind": "heading",
                "order": 1,
                "heading_path": heading,
                "analysis_text": "Section A",
            },
            {
                "block_id": "PA001",
                "kind": "paragraph",
                "order": 2,
                "heading_path": heading,
                "analysis_text": "paragraph one",
            },
        ]
    )
    source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id="PA001",
        heading_path=heading,
        lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z1"},
    )
    routed = _route_prepare(projected_sources=[source], block_manifest=manifest)
    aggregate_units = routed.units_by_route["aggregate"]
    assert len(aggregate_units) == 1
    assert aggregate_units[0]["context_block_ids"] == ["CHA001"]


def test_raw_adapter_zone_id_mapping_controls_case_merge() -> None:
    heading_case = ["12 临床安全性", "12.3.2 病例叙述"]
    manifest = _block_manifest(
        blocks=[
            {
                "block_id": "CH001",
                "kind": "heading",
                "order": 1,
                "heading_path": heading_case,
                "analysis_text": "12.3.2 病例叙述",
            },
            {
                "block_id": "CP001",
                "kind": "paragraph",
                "order": 2,
                "heading_path": heading_case,
                "analysis_text": "case one",
            },
            {
                "block_id": "CP002",
                "kind": "paragraph",
                "order": 3,
                "heading_path": heading_case,
                "analysis_text": "case two",
            },
        ]
    )
    same_zone_sources = (
        raw_projected_source(
            semantic_module_id="clinical_safety",
            block_id="CP001",
            heading_path=heading_case,
            lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z1"},
        ),
        raw_projected_source(
            semantic_module_id="clinical_safety",
            block_id="CP002",
            heading_path=heading_case,
            lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z1"},
        ),
    )
    merged = _route_prepare(projected_sources=same_zone_sources, block_manifest=manifest)
    assert len(merged.units_by_route["case"]) == 1

    mixed_zone_sources = (
        raw_projected_source(
            semantic_module_id="clinical_safety",
            block_id="CP001",
            heading_path=heading_case,
            lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z1"},
        ),
        raw_projected_source(
            semantic_module_id="clinical_safety",
            block_id="CP002",
            heading_path=heading_case,
            lineage={"zone_key": "ib_clinical_safety_zh", "zone_id": "Z2"},
        ),
    )
    split = _route_prepare(projected_sources=mixed_zone_sources, block_manifest=manifest)
    assert len(split.units_by_route["case"]) == 2
