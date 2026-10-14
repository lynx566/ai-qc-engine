"""Slice 5C unknown text-unit body contract closure regressions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing.route_bundles import build_routed_unit_bundle
from artifacts.routing.schema import ROUTE_SCHEMA_VERSION, validate_routed_unit_bundle
from operations.filter_output_projection.contracts import ProjectedSource
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from artifacts.routing.primary_sentence_contract import (
    PRIMARY_ROUTED_SENTENCE_KEYS,
    validate_text_unit_body_consistency,
)
from tests.projection_test_helpers import projected_sentence, raw_projected_source
from tests.route_test_fixtures import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_manifest,
    _block,
    _block_manifest,
    _coverage_bundle,
    _coverage_row,
    _route_units,
    _table_block,
)

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


def _route_unknown(
    *,
    projected_sources: list[ProjectedSource],
    manifest_blocks: list[dict[str, Any]],
    table_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": manifest_blocks,
        "table_blocks": table_blocks or [],
    }
    routed = route_prepare_units_from_projected_sources(
        projected_sources=projected_sources,
        block_manifest=manifest,
        analysis_bundle=_analysis_bundle_for_manifest(manifest),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    unknown_units = routed.units_by_route["unknown"]
    assert len(unknown_units) == 1
    return unknown_units[0]


def _assert_unknown_primary_body(unit: dict[str, Any]) -> None:
    assert unit["unit_kind"] == "text_unit"
    assert unit["route"] == "unknown"
    assert _RETIRED_BODY_KEYS.isdisjoint(unit)
    sentences = unit["sentences"]
    assert isinstance(sentences, list) and sentences
    for sentence in sentences:
        assert set(sentence) == set(PRIMARY_ROUTED_SENTENCE_KEYS)
    validate_text_unit_body_consistency(unit, unit_path="unit")


def test_figure_unknown_emits_canonical_sentences() -> None:
    heading = ["12 临床安全性"]
    block_id = "C0030"
    unit = _route_unknown(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=block_id,
                block_kind="figure",
                heading_path=heading,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text="Figure projected body",
                        source_block_id=block_id,
                    ),
                ),
            )
        ],
        manifest_blocks=[
            _manifest_block(
                block_id=block_id,
                order=30,
                block_kind="figure",
                heading_path=heading,
                analysis_text="manifest figure text",
            )
        ],
    )
    _assert_unknown_primary_body(unit)
    assert unit["sentences"][0]["text"] == "Figure projected body"


def test_unsupported_block_emits_canonical_sentences() -> None:
    block_id = "C0099"
    unit = _route_unknown(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=block_id,
                block_kind="unsupported",
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text="Unsupported projected body",
                        source_block_id=block_id,
                    ),
                ),
            )
        ],
        manifest_blocks=[
            _manifest_block(
                block_id=block_id,
                order=99,
                block_kind="unsupported",
                analysis_text="manifest unsupported text",
            )
        ],
    )
    _assert_unknown_primary_body(unit)
    assert unit["candidate_block_kinds"] == ["unsupported"]


def test_unknown_multi_sentence_preserves_order() -> None:
    block_id = "C0030"
    unit = _route_unknown(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=block_id,
                block_kind="figure",
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text="First",
                        source_block_id=block_id,
                    ),
                    projected_sentence(
                        sentence_id=f"{block_id}:S002",
                        text="Second",
                        source_block_id=block_id,
                    ),
                ),
            )
        ],
        manifest_blocks=[_manifest_block(block_id=block_id, order=30, block_kind="figure")],
    )
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{block_id}:S001",
        f"{block_id}:S002",
    ]
    assert [sentence["text"] for sentence in unit["sentences"]] == ["First", "Second"]


def test_unknown_prefers_projected_text_over_manifest() -> None:
    block_id = "C0030"
    unit = _route_unknown(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=block_id,
                block_kind="figure",
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text="PROJECTED",
                        source_block_id=block_id,
                    ),
                ),
            )
        ],
        manifest_blocks=[
            _manifest_block(
                block_id=block_id,
                order=30,
                block_kind="figure",
                analysis_text="MANIFEST",
            )
        ],
    )
    assert unit["sentences"][0]["text"] == "PROJECTED"


def test_unknown_emits_sentences_when_manifest_analysis_text_empty() -> None:
    block_id = "C0030"
    unit = _route_unknown(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=block_id,
                block_kind="figure",
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text="Projection only",
                        source_block_id=block_id,
                    ),
                ),
            )
        ],
        manifest_blocks=[
            _manifest_block(
                block_id=block_id,
                order=30,
                block_kind="figure",
                analysis_text="",
            )
        ],
    )
    assert unit["sentences"][0]["text"] == "Projection only"


def test_unknown_missing_projected_sentences_fail_closed() -> None:
    from plugins.clinical_trial_doc.routing.processor import _build_unknown_structure_unit

    block_id = "C0030"
    row = {
        "block_id": block_id,
        "block_kind": "figure",
        "heading_path": ["Section"],
        "text_ref": {"block_id": block_id},
    }
    with pytest.raises(ValueError, match="missing from projected sentence index"):
        _build_unknown_structure_unit(
            row,
            blocks_by_id={},
            projected_sentences_by_block_id={},
        )


def test_unknown_raw_source_without_sentences_fail_closed() -> None:
    block_id = "C0030"
    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": [_manifest_block(block_id=block_id, order=30, block_kind="figure")],
        "table_blocks": [],
    }
    with pytest.raises(ValueError, match="non-empty sentences"):
        route_prepare_units_from_projected_sources(
            projected_sources=[
                raw_projected_source(
                    semantic_module_id="clinical_safety",
                    block_id=block_id,
                    block_kind="figure",
                    sentences=(),
                )
            ],
            block_manifest=manifest,
            analysis_bundle=_analysis_bundle_for_manifest(manifest),
            expected_semantic_module_id="clinical_safety",
            doc_id="doc_test",
            file_hash=LINEAGE_FILE_HASH,
        )


def test_unknown_schema_0_6_0_validates() -> None:
    block_id = "C0030"
    manifest_blocks = [
        _manifest_block(
            block_id=block_id,
            order=30,
            block_kind="figure",
            analysis_text="manifest",
        )
    ]
    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": manifest_blocks,
        "table_blocks": [],
    }
    routed = route_prepare_units_from_projected_sources(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=block_id,
                block_kind="figure",
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text="Body",
                        source_block_id=block_id,
                    ),
                ),
            )
        ],
        block_manifest=manifest,
        analysis_bundle=_analysis_bundle_for_manifest(manifest),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    unit = routed.units_by_route["unknown"][0]
    bundle = build_routed_unit_bundle(
        route="unknown",
        units=[unit],
        route_input_envelope={
            "route_input_id": "projected_route_clinical_safety",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "zone_key": "",
            "projection_input_refs": [
                {
                    "filter_output_projection_bundle_id": "bundle_test",
                    "filter_job_id": "dsur_clinical_safety",
                    "zone_key": "dsur_clinical_safety_zh",
                }
            ],
        },
        block_manifest=manifest,
        doc_meta_bundle={
            "doc_meta_bundle_id": "doc_meta_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
        },
        analysis_bundle=_analysis_bundle_for_manifest(manifest),
    )
    validate_routed_unit_bundle(bundle, expected_route="unknown")
    assert bundle["schema_version"] == ROUTE_SCHEMA_VERSION
    assert "candidate_text" not in bundle["units"][0]


def test_aggregate_and_case_unchanged() -> None:
    heading_agg = ["12 临床安全性", "12.3 不良事件概述"]
    heading_case = ["12 临床安全性", "12.3.2 病例叙述"]
    routed = _route_units(
        coverage=_coverage_bundle(
            _coverage_row("C0100", 100, heading_path=heading_agg),
            _coverage_row("C0021", 20, heading_path=heading_case),
        ),
        manifest=_block_manifest(
            blocks=[
                _block("C0100", 100, heading_path=heading_agg, analysis_text="agg"),
                _block("C0021", 20, heading_path=heading_case, analysis_text="case"),
            ],
        ),
    )
    aggregate = routed.units_by_route["aggregate"][0]
    case = routed.units_by_route["case"][0]
    assert aggregate["sentences"]
    assert case["sentences"]
    assert _RETIRED_BODY_KEYS.isdisjoint(aggregate)
    assert _RETIRED_BODY_KEYS.isdisjoint(case)


def test_table_and_orphan_unchanged() -> None:
    heading = ["12 临床安全性"]
    coverage = _coverage_bundle(
        _coverage_row("C0010", 9, block_kind="table_caption", heading_path=heading),
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
    )
    manifest = _block_manifest(
        blocks=[
            _block("C0010", 9, kind="table_caption", heading_path=heading, analysis_text="表1"),
        ],
        table_blocks=[_table_block("T0001", 10, heading_path=heading)],
    )
    routed = _route_units(coverage=coverage, manifest=manifest)
    table = routed.units_by_route["table"][0]
    assert table["unit_kind"] == "table_unit"
    assert "components" in table
    assert "sentences" not in table

    orphan_coverage = _coverage_bundle(
        _coverage_row("C0020", 20, block_kind="table_note", heading_path=heading),
    )
    orphan_manifest = _block_manifest(
        blocks=[
            _block("C0020", 20, kind="table_note", heading_path=heading, analysis_text="note"),
        ],
    )
    orphan_routed = _route_units(coverage=orphan_coverage, manifest=orphan_manifest)
    orphan = orphan_routed.units_by_route["table"][0]
    assert orphan["unit_kind"] == "table_unit"
    assert orphan["components"]
