"""Slice 4 Route projected-sentence authority cutover regressions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.sentence_index import build_sentences
from operations.filter_output_projection.contracts import ProjectedSource
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from artifacts.routing.primary_sentence_contract import routed_body_text_from_sentences
from tests.projection_test_helpers import projected_sentence, raw_projected_source
from tests.route_test_fixtures import LINEAGE_FILE_HASH, _analysis_bundle_for_manifest

BLOCK_A = "B001"
BLOCK_B = "B003"


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


def _route_direct(
    *,
    projected_sources: list[ProjectedSource],
    manifest_blocks: list[dict[str, Any]],
    analysis_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": manifest_blocks,
        "table_blocks": [],
    }
    resolved_analysis_bundle = analysis_bundle or _analysis_bundle_for_manifest(manifest)
    routed = route_prepare_units_from_projected_sources(
        projected_sources=projected_sources,
        block_manifest=manifest,
        analysis_bundle=resolved_analysis_bundle,
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    return routed.units_by_route["aggregate"][0]


def test_direct_uses_projected_text_over_analysis_bundle_and_manifest() -> None:
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_A,
        sentences=(
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S001",
                text="Projected A",
                source_block_id=BLOCK_A,
            ),
        ),
    )
    unit = _route_direct(
        projected_sources=[projected_source],
        manifest_blocks=[
            _manifest_block(
                block_id=BLOCK_A,
                order=1,
                analysis_text="OLD BLOCK TEXT",
            )
        ],
        analysis_bundle={
            "analysis_bundle_id": "prepare_analysis_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "content_blocks": [
                {
                    "block_id": BLOCK_A,
                    "kind": "paragraph",
                    "analysis_text": "OLD / DIFFERENT A",
                    "sentences": [
                        {
                            "sentence_id": f"{BLOCK_A}:S001",
                            "analysis_text": "OLD / DIFFERENT A",
                        }
                    ],
                }
            ],
            "table_blocks": [],
        },
    )
    assert unit["sentences"][0]["text"] == "Projected A"
    assert routed_body_text_from_sentences(
        unit["sentences"],
        source_stage=unit["source_stage"],
    ) == "Projected A"


def test_direct_emits_sentences_when_manifest_analysis_text_empty() -> None:
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_A,
        sentences=(
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S001",
                text="Body from projection only.",
                source_block_id=BLOCK_A,
            ),
        ),
    )
    unit = _route_direct(
        projected_sources=[projected_source],
        manifest_blocks=[
            _manifest_block(block_id=BLOCK_A, order=1, analysis_text=""),
        ],
    )
    assert unit["sentences"][0]["text"] == "Body from projection only."


def test_direct_multi_sentence_block_preserves_order() -> None:
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_A,
        sentences=(
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S001",
                text="A。",
                source_block_id=BLOCK_A,
            ),
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S002",
                text="B。",
                source_block_id=BLOCK_A,
            ),
        ),
    )
    unit = _route_direct(
        projected_sources=[projected_source],
        manifest_blocks=[_manifest_block(block_id=BLOCK_A, order=1, analysis_text="A。B。")],
    )
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{BLOCK_A}:S001",
        f"{BLOCK_A}:S002",
    ]
    assert [sentence["text"] for sentence in unit["sentences"]] == ["A。", "B。"]


def test_case_merged_blocks_preserve_row_and_sentence_order() -> None:
    heading_path = ["12.病例叙述"]
    manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": [
            {
                "block_id": BLOCK_A,
                "kind": "paragraph",
                "order": 100,
                "heading_path": heading_path,
                "analysis_text": "",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": BLOCK_A,
                },
            },
            {
                "block_id": BLOCK_B,
                "kind": "paragraph",
                "order": 101,
                "heading_path": heading_path,
                "analysis_text": "",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": BLOCK_B,
                },
            },
        ],
        "table_blocks": [],
    }
    lineage = {"zone_key": "dsur_clinical_safety_zh", "zone_id": "Z1"}
    routed = route_prepare_units_from_projected_sources(
        projected_sources=[
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_A,
                heading_path=heading_path,
                lineage=lineage,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S001",
                        text="A1",
                        source_block_id=BLOCK_A,
                    ),
                    projected_sentence(
                        sentence_id=f"{BLOCK_A}:S002",
                        text="A2",
                        source_block_id=BLOCK_A,
                    ),
                ),
            ),
            raw_projected_source(
                semantic_module_id="clinical_safety",
                block_id=BLOCK_B,
                heading_path=heading_path,
                lineage=lineage,
                sentences=(
                    projected_sentence(
                        sentence_id=f"{BLOCK_B}:S001",
                        text="B1",
                        source_block_id=BLOCK_B,
                    ),
                ),
            ),
        ],
        block_manifest=manifest,
        analysis_bundle=_analysis_bundle_for_manifest(manifest),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    unit = routed.units_by_route["case"][0]
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{BLOCK_A}:S001",
        f"{BLOCK_A}:S002",
        f"{BLOCK_B}:S001",
    ]


def test_case_route_preserves_projected_sentence_order() -> None:
    heading_path = ["12.具体病例"]
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id="C0100",
        heading_path=heading_path,
        sentences=(
            projected_sentence(
                sentence_id="C0100:S001",
                text="病例第一句。",
                source_block_id="C0100",
            ),
            projected_sentence(
                sentence_id="C0100:S002",
                text="病例第二句。",
                source_block_id="C0100",
            ),
        ),
    )
    routed = route_prepare_units_from_projected_sources(
        projected_sources=[projected_source],
        block_manifest={
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "blocks": [
                {
                    "block_id": "C0100",
                    "kind": "paragraph",
                    "order": 100,
                    "heading_path": heading_path,
                    "analysis_text": "OLD",
                    "text_ref": {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": "C0100",
                    },
                }
            ],
            "table_blocks": [],
        },
        analysis_bundle={
            "analysis_bundle_id": "prepare_analysis_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "content_blocks": [
                {
                    "block_id": "C0100",
                    "kind": "paragraph",
                    "analysis_text": "OLD",
                    "sentences": [
                        {"sentence_id": "C0100:S001", "analysis_text": "WRONG"},
                        {"sentence_id": "C0100:S002", "analysis_text": "WRONG"},
                    ],
                }
            ],
            "table_blocks": [],
        },
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    unit = routed.units_by_route["case"][0]
    assert unit["route"] == "case"
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        "C0100:S001",
        "C0100:S002",
    ]
    assert unit["sentences"][0]["text"] == "病例第一句。"


def test_heading_structural_context_preserved_with_legacy_ctx_ids() -> None:
    heading_path = ["7.安全性"]
    projected_source = raw_projected_source(
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
    unit = _route_direct(
        projected_sources=[projected_source],
        manifest_blocks=[
            _manifest_block(
                block_id="H0001",
                order=1,
                block_kind="heading",
                heading_path=["7.安全性"],
                analysis_text="7.安全性",
            ),
            _manifest_block(
                block_id=BLOCK_A,
                order=2,
                heading_path=heading_path,
                analysis_text="",
            ),
        ],
    )
    assert unit["context_block_ids"] == ["H0001"]
    assert unit["heading_path"] == heading_path
    assert unit["sentences"][0]["sentence_id"] == f"{BLOCK_A}:S001"
    assert "context_sentences" not in unit


def test_provenance_fields_match_projected_sentences() -> None:
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_A,
        sentences=(
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S001",
                text="A。",
                source_block_id=BLOCK_A,
            ),
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S002",
                text="B。",
                source_block_id=BLOCK_A,
            ),
        ),
    )
    unit = _route_direct(
        projected_sources=[projected_source],
        manifest_blocks=[_manifest_block(block_id=BLOCK_A, order=1, analysis_text="")],
    )
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{BLOCK_A}:S001",
        f"{BLOCK_A}:S002",
    ]
    assert unit["source_block_ids"] == [BLOCK_A]
    assert all(
        sentence["source_block_id"] == BLOCK_A for sentence in unit["sentences"]
    )


def test_invalid_source_block_id_fails_closed() -> None:
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_A,
        sentences=(
            projected_sentence(
                sentence_id=f"{BLOCK_A}:S001",
                text="A。",
                source_block_id="B999",
            ),
        ),
    )
    with pytest.raises(ValueError, match="source_block_id"):
        _route_direct(
            projected_sources=[projected_source],
            manifest_blocks=[_manifest_block(block_id=BLOCK_A, order=1)],
        )
