"""Slice 5B routed body contract + ESP cutover regressions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing.primary_sentence_contract import (
    PRIMARY_ROUTED_SENTENCE_KEYS,
    routed_body_text_from_sentences,
    validate_text_unit_body_consistency,
)
from artifacts.routing.schema import ROUTE_SCHEMA_VERSION, validate_routed_unit_bundle
from operations.filter_output_projection.contracts import ProjectedSource
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    build_unit_assessment_evidence_text,
    compact_sentences_from_aggregate_unit,
)
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from tests.projection_test_helpers import (
    assembled_projected_source,
    projected_sentence,
    raw_projected_source,
)
from tests.route_test_fixtures import LINEAGE_FILE_HASH, _analysis_bundle_for_manifest

BLOCK_A = "B001"
_RETIRED_BODY_KEYS = frozenset({"candidate_sentences", "candidate_text", "source_sentence_ids"})


def _manifest_block(
    *,
    block_id: str,
    order: int,
    analysis_text: str = "",
    heading_path: list[str] | None = None,
    block_kind: str = "paragraph",
) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": block_kind,
        "order": order,
        "heading_path": heading_path or ["Section"],
        "analysis_text": analysis_text,
        "text_ref": {
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": block_id,
        },
    }


def _route(
    *,
    projected_sources: list[ProjectedSource],
    manifest_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": manifest_blocks,
        "table_blocks": [],
    }
    return route_prepare_units_from_projected_sources(
        projected_sources=projected_sources,
        block_manifest=manifest,
        analysis_bundle=_analysis_bundle_for_manifest(manifest),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )


def _assert_primary_only_body(unit: dict[str, Any]) -> None:
    assert _RETIRED_BODY_KEYS.isdisjoint(unit)
    for sentence in unit["sentences"]:
        assert set(sentence) == set(PRIMARY_ROUTED_SENTENCE_KEYS)
    validate_text_unit_body_consistency(unit, unit_path="unit")


def test_direct_aggregate_emits_primary_sentences_only() -> None:
    unit = _route(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_A,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S001",
                        text="Body A",
                        source_block_id=BLOCK_A,
                    ),
                ),
            )
        ],
        manifest_blocks=[_manifest_block(block_id=BLOCK_A, order=1)],
    ).units_by_route["aggregate"][0]
    _assert_primary_only_body(unit)


def test_direct_case_emits_primary_sentences_only() -> None:
    heading_path = ["12.病例叙述"]
    unit = _route(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_A,
                heading_path=heading_path,
                lineage={"zone_key": "dsur_clinical_safety_zh", "zone_id": "Z1"},
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S001",
                        text="Case body",
                        source_block_id=BLOCK_A,
                    ),
                ),
            )
        ],
        manifest_blocks=[
            _manifest_block(
                block_id=BLOCK_A,
                order=100,
                heading_path=heading_path,
            )
        ],
    ).units_by_route["case"][0]
    _assert_primary_only_body(unit)


def test_overview_emits_primary_sentences_only() -> None:
    unit = _route(
        projected_sources=[
            assembled_projected_source(
                semantic_module_id="clinical_safety",
                heading_path=["执行概要"],
                lineage={"zone_key": "dsur_overview_zh", "filter_job_id": "dsur_overview"},
                sentences=(
                    projected_sentence(
                        sentence_id="C0006:S001",
                        text="Shared context body",
                        source_block_id="C0006",
                    ),
                    projected_sentence(
                        sentence_id="C0007:S001",
                        text="Substantive body",
                        source_block_id="C0007",
                    ),
                ),
            )
        ],
        manifest_blocks=[],
    ).units_by_route["aggregate"][0]
    _assert_primary_only_body(unit)
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        "C0006:S001",
        "C0007:S001",
    ]


def test_routed_body_text_roundtrip_single_and_overview() -> None:
    single = [{"sentence_id": "S0001", "text": "单句文本。"}]
    assert routed_body_text_from_sentences(single) == "单句文本。"
    multi = [
        {"sentence_id": "S0001", "text": "第一句。"},
        {"sentence_id": "S0002", "text": "第二句。"},
    ]
    assert routed_body_text_from_sentences(multi) == "第一句。第二句。"
    overview = [
        {"sentence_id": "S0001", "text": "Alpha。"},
        {"sentence_id": "S0002", "text": "Beta。"},
    ]
    assert (
        routed_body_text_from_sentences(
            overview,
            source_stage="overview_decompose",
        )
        == "Alpha。\nBeta。"
    )


def test_route_schema_version_is_0_7_0() -> None:
    assert ROUTE_SCHEMA_VERSION == "0.7.0"


def test_validator_rejects_retired_body_duplicate_fields() -> None:
    unit = {
        "unit_kind": "text_unit",
        "source_stage": "filter_projection",
        "sentences": [
            {
                "sentence_id": f"{BLOCK_A}:S001",
                "text": "A",
                "source_block_id": BLOCK_A,
            }
        ],
        "candidate_sentences": [],
    }
    with pytest.raises(ValueError, match="retired routed body field"):
        validate_text_unit_body_consistency(unit, unit_path="unit")


def test_esp_compact_reads_primary_sentences() -> None:
    unit = {
        "unit_id": "TU0001",
        "sentences": [
            {"sentence_id": "S003", "text": "A", "source_block_id": BLOCK_A},
            {"sentence_id": "S001", "text": "B", "source_block_id": BLOCK_A},
            {"sentence_id": "S002", "text": "C", "source_block_id": BLOCK_A},
        ],
        "source_stage": "filter_projection",
    }
    compact = compact_sentences_from_aggregate_unit(unit)
    assert [sentence["text"] for sentence in compact] == ["A", "B", "C"]


def test_evidence_ignores_retired_context_sentences() -> None:
    unit = {
        "unit_id": "TU0001",
        "source_stage": "filter_projection",
        "sentences": [
            {"sentence_id": "S001", "text": "BODY", "source_block_id": BLOCK_A},
        ],
    }
    assert build_unit_assessment_evidence_text(unit) == "BODY"


def test_duplicate_text_preserved_in_evidence_join() -> None:
    unit = {
        "unit_id": "TU0001",
        "source_stage": "filter_projection",
        "sentences": [
            {"sentence_id": "S001", "text": "Same", "source_block_id": BLOCK_A},
            {"sentence_id": "S002", "text": "Same", "source_block_id": BLOCK_A},
        ],
    }
    assert build_unit_assessment_evidence_text(unit) == "SameSame"


def test_heading_structure_preserved_without_ctx_in_primary() -> None:
    heading_path = ["7.安全性"]
    unit = _route(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_A,
                heading_path=heading_path,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S001",
                        text="正文。",
                        source_block_id=BLOCK_A,
                    ),
                ),
            )
        ],
        manifest_blocks=[
            _manifest_block(
                block_id="H0001",
                order=1,
                block_kind="heading",
                heading_path=heading_path,
                analysis_text="7.安全性",
            ),
            _manifest_block(
                block_id=BLOCK_A,
                order=2,
                heading_path=heading_path,
            ),
        ],
    ).units_by_route["aggregate"][0]
    assert unit["context_block_ids"] == ["H0001"]
    assert unit["heading_path"] == heading_path
    assert all(
        not sentence["sentence_id"].startswith("CTX") for sentence in unit["sentences"]
    )


def test_route_bundle_rejects_retired_context_sentences() -> None:
    routed = _route(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_A,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S001",
                        text="Body",
                        source_block_id=BLOCK_A,
                    ),
                ),
            )
        ],
        manifest_blocks=[_manifest_block(block_id=BLOCK_A, order=1)],
    )
    unit = dict(routed.units_by_route["aggregate"][0])
    unit["context_sentences"] = [
        {
            "sentence_id": "CTX0001",
            "kind": "heading",
            "text": "Legacy",
            "source_block_id": "H0001",
        }
    ]
    from artifacts.routing.route_bundles import build_routed_unit_bundle

    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": [_manifest_block(block_id=BLOCK_A, order=1)],
        "table_blocks": [],
    }
    envelope = {
        "route_input_id": "projected_route_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "zone_key": "dsur_clinical_safety_zh",
        "projection_input_refs": [
            {
                "filter_output_projection_bundle_id": "fop_test",
                "filter_job_id": "dsur_clinical_safety",
                "zone_key": "dsur_clinical_safety_zh",
            }
        ],
    }
    with pytest.raises(ValueError, match="context_sentences"):
        build_routed_unit_bundle(
            route="aggregate",
            units=[unit],
            route_input_envelope=envelope,
            block_manifest=manifest,
            doc_meta_bundle={
                "doc_meta_bundle_id": "doc_meta_test",
                "doc_id": "doc_test",
                "file_hash": LINEAGE_FILE_HASH,
            },
            analysis_bundle=_analysis_bundle_for_manifest(manifest),
        )


def test_table_unit_unchanged() -> None:
    routed = _route(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id="T0001",
                block_kind="table",
                source_group="table_blocks",
                sentences=(
                    projected_sentence(
                        sentence_id="T0001:S001",
                        text="table body",
                        source_block_id="T0001",
                    ),
                ),
            )
        ],
        manifest_blocks=[
            {
                "block_id": "T0001",
                "kind": "table",
                "order": 1,
                "heading_path": ["Tables"],
                "analysis_text": "table body",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "T0001",
                },
            }
        ],
    )
    table_unit = routed.units_by_route["table"][0]
    assert table_unit["unit_kind"] == "table_unit"
    assert "sentences" not in table_unit


def test_routed_bundle_validates_primary_contract() -> None:
    from artifacts.routing.route_bundles import build_routed_unit_bundle

    routed = _route(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_A,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S001",
                        text="A",
                        source_block_id=BLOCK_A,
                    ),
                ),
            )
        ],
        manifest_blocks=[_manifest_block(block_id=BLOCK_A, order=1)],
    )
    bundle = build_routed_unit_bundle(
        route="aggregate",
        units=routed.units_by_route["aggregate"],
        route_input_envelope={
            "route_input_id": "coverage_route_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "zone_key": "dsur_clinical_safety_zh",
        },
        block_manifest={
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "blocks": [_manifest_block(block_id=BLOCK_A, order=1)],
            "table_blocks": [],
        },
        doc_meta_bundle={
            "doc_meta_bundle_id": "doc_meta_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
        },
        analysis_bundle=_analysis_bundle_for_manifest(
            {
                "block_manifest_id": "block_manifest_test",
                "doc_id": "doc_test",
                "file_hash": LINEAGE_FILE_HASH,
                "blocks": [_manifest_block(block_id=BLOCK_A, order=1)],
                "table_blocks": [],
            }
        ),
    )
    validate_routed_unit_bundle(bundle, expected_route="aggregate")
    assert bundle["schema_version"] == "0.7.0"
    assert _RETIRED_BODY_KEYS.isdisjoint(bundle["units"][0])
