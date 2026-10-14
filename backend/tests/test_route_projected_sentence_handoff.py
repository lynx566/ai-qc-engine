"""Route primary sentence handoff from ProjectedSource.sentences[] to routed sentences[]."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.sentence_index import build_sentences
from operations.filter_output_projection.contracts import ProjectedSource
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from tests.block_manifest_test_helpers import build_block_manifest
from tests.projection_test_helpers import projected_sentence, raw_projected_source
from tests.route_test_fixtures import LINEAGE_FILE_HASH

BLOCK_ID = "C0016"
TWO_SENTENCE_TEXT = "第一句。第二句。"


def _analysis_block(*, block_id: str, analysis_text: str) -> dict[str, Any]:
    sentences = build_sentences(
        block_id,
        "paragraph",
        raw_text=analysis_text,
        normalized_text=analysis_text,
    )
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "analysis_text": analysis_text,
        "normalized_text": analysis_text,
        "sentences": [
            {
                "sentence_id": built.sentence_id,
                "analysis_text": built.normalized_text,
            }
            for built in sentences
        ],
    }


def test_block_manifest_blocks_have_no_sentence_selectors() -> None:
    block = _analysis_block(block_id=BLOCK_ID, analysis_text=TWO_SENTENCE_TEXT)
    manifest = build_block_manifest(
        {
            "analysis_bundle_id": "prepare_analysis_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "content_blocks": [{**block, "order": 16}],
        }
    )
    manifest_block = next(item for item in manifest["blocks"] if item["block_id"] == BLOCK_ID)
    assert "sentence_selectors" not in manifest_block


def test_route_primary_sentences_follow_projected_source() -> None:
    heading_path = ["Section"]
    analysis_block = _analysis_block(block_id=BLOCK_ID, analysis_text=TWO_SENTENCE_TEXT)
    built_sentences = analysis_block["sentences"]
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_ID,
        heading_path=heading_path,
        sentences=tuple(
            projected_sentence(
                sentence_id=item["sentence_id"],
                text=item["analysis_text"],
                source_block_id=BLOCK_ID,
            )
            for item in built_sentences
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
                    "block_id": BLOCK_ID,
                    "kind": "paragraph",
                    "order": 16,
                    "heading_path": heading_path,
                    "analysis_text": TWO_SENTENCE_TEXT,
                    "text_ref": {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": BLOCK_ID,
                    },
                }
            ],
            "table_blocks": [],
        },
        analysis_bundle={
            "analysis_bundle_id": "prepare_analysis_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "content_blocks": [analysis_block],
            "table_blocks": [],
        },
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    unit = routed.units_by_route["aggregate"][0]
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{BLOCK_ID}:S001",
        f"{BLOCK_ID}:S002",
    ]


def test_route_primary_sentences_ignore_empty_analysis_bundle() -> None:
    heading_path = ["Section"]
    projected_source = raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=BLOCK_ID,
        heading_path=heading_path,
        sentences=(
            projected_sentence(
                sentence_id=f"{BLOCK_ID}:S001",
                text="第一句。",
                source_block_id=BLOCK_ID,
            ),
            projected_sentence(
                sentence_id=f"{BLOCK_ID}:S002",
                text="第二句。",
                source_block_id=BLOCK_ID,
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
                    "block_id": BLOCK_ID,
                    "kind": "paragraph",
                    "order": 16,
                    "heading_path": heading_path,
                    "analysis_text": TWO_SENTENCE_TEXT,
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
                    "block_id": BLOCK_ID,
                    "kind": "paragraph",
                    "analysis_text": TWO_SENTENCE_TEXT,
                    "sentences": [],
                }
            ],
            "table_blocks": [],
        },
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    unit = routed.units_by_route["aggregate"][0]
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{BLOCK_ID}:S001",
        f"{BLOCK_ID}:S002",
    ]
