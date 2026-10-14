"""Route Direct-path canonical sentence handoff regression tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing.route_bundles import build_route_stage_artifacts
from artifacts.routing.schema import validate_routed_unit_bundle
from core.document.sentence_index import build_sentences
from operations.filter_output_projection.contracts import ProjectedSource
from plugins.clinical_trial_doc.routing import route_prepare_units_from_projected_sources
from tests.projection_test_helpers import projected_sentence, raw_projected_source
from tests.route_test_fixtures import LINEAGE_FILE_HASH

BLOCK_ID = "C0016"
MULTI_SENTENCE_TEXT = (
    "本报告周期内，基于累计安全性资料，申办者拟对《研究者手册》中的安全性参考信息进行更新，"
    "将感染性肺炎及药物诱导的肝损伤纳入VT8802预期严重不良反应列表。"
    "该安全性参考信息变更见第4节。"
)
SIMILAR_SENTENCE_TEXT = "相同文本。相同文本。"


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
        "sentences": [
            {
                "sentence_id": built.sentence_id,
                "analysis_text": built.normalized_text,
            }
            for built in sentences
        ],
    }


def _manifest_block_from_analysis_block(analysis_block: dict[str, Any]) -> dict[str, Any]:
    return {
        "block_id": analysis_block["block_id"],
        "kind": analysis_block["kind"],
        "order": 16,
        "heading_path": ["3.报告周期内因安全性原因而采取的措施"],
        "analysis_text": analysis_block["analysis_text"],
        "text_ref": {
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": analysis_block["block_id"],
        },
    }


def _analysis_bundle(*, analysis_block: dict[str, Any]) -> dict[str, Any]:
    return {
        "analysis_bundle_id": "prepare_analysis_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "content_blocks": [analysis_block],
        "table_blocks": [],
    }


def _direct_projected_source(
    *,
    block_id: str,
    analysis_text: str,
    heading_path: list[str],
    analysis_block: dict[str, Any] | None = None,
) -> ProjectedSource:
    resolved_block = analysis_block or _analysis_block(
        block_id=block_id,
        analysis_text=analysis_text,
    )
    return raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=block_id,
        heading_path=heading_path,
        lineage={"zone_key": "dsur_clinical_safety_zh", "zone_id": "Z0001"},
        sentences=tuple(
            projected_sentence(
                sentence_id=item["sentence_id"],
                text=item["analysis_text"],
                source_block_id=block_id,
            )
            for item in resolved_block["sentences"]
        ),
    )


def _route_direct_unit(
    *,
    analysis_text: str,
    block_id: str = BLOCK_ID,
    manifest_block: dict[str, Any] | None = None,
    analysis_block: dict[str, Any] | None = None,
    wrong_selectors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    heading_path = ["3.报告周期内因安全性原因而采取的措施"]
    resolved_analysis_block = analysis_block or _analysis_block(
        block_id=block_id,
        analysis_text=analysis_text,
    )
    resolved_manifest_block = manifest_block or _manifest_block_from_analysis_block(
        resolved_analysis_block
    )
    if wrong_selectors is not None:
        resolved_manifest_block = {
            **resolved_manifest_block,
            "sentence_selectors": wrong_selectors,
        }
    routed = route_prepare_units_from_projected_sources(
        projected_sources=(
            _direct_projected_source(
                block_id=block_id,
                analysis_text=analysis_text,
                heading_path=heading_path,
                analysis_block=resolved_analysis_block,
            ),
        ),
        block_manifest={
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "blocks": [resolved_manifest_block],
            "table_blocks": [],
        },
        analysis_bundle=_analysis_bundle(analysis_block=resolved_analysis_block),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    units = routed.units_by_route["aggregate"]
    assert len(units) == 1
    return units[0]


def test_direct_multi_sentence_paragraph_uses_canonical_sentence_ids() -> None:
    unit = _route_direct_unit(analysis_text=MULTI_SENTENCE_TEXT)

    sentences = unit["sentences"]
    assert len(sentences) == 2
    assert sentences[0]["sentence_id"] == f"{BLOCK_ID}:S001"
    assert sentences[0]["source_block_id"] == BLOCK_ID
    assert sentences[0]["text"] == MULTI_SENTENCE_TEXT[:77]
    assert sentences[1]["sentence_id"] == f"{BLOCK_ID}:S002"
    assert sentences[1]["text"] == MULTI_SENTENCE_TEXT[77:]
    assert [sentence["sentence_id"] for sentence in unit["sentences"]] == [
        f"{BLOCK_ID}:S001",
        f"{BLOCK_ID}:S002",
    ]
    assert "canonical_sentence_id" not in sentences[0]
    assert "source_item_index" not in sentences[0]
    assert "char_start" not in sentences[0]


def test_direct_similar_sentences_keep_distinct_canonical_ids() -> None:
    unit = _route_direct_unit(
        analysis_text=SIMILAR_SENTENCE_TEXT,
        block_id="C0099",
    )

    sentences = unit["sentences"]
    assert len(sentences) == 2
    assert sentences[0]["text"] == sentences[1]["text"] == "相同文本。"
    assert sentences[0]["sentence_id"] == "C0099:S001"
    assert sentences[1]["sentence_id"] == "C0099:S002"


def test_route_validator_requires_primary_sentence_fields() -> None:
    unit = _route_direct_unit(analysis_text=MULTI_SENTENCE_TEXT)
    routed = route_prepare_units_from_projected_sources(
        projected_sources=(
            _direct_projected_source(
                block_id=BLOCK_ID,
                analysis_text=MULTI_SENTENCE_TEXT,
                heading_path=["3.报告周期内因安全性原因而采取的措施"],
                analysis_block=_analysis_block(
                    block_id=BLOCK_ID,
                    analysis_text=MULTI_SENTENCE_TEXT,
                ),
            ),
        ),
        block_manifest={
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
            "blocks": [
                _manifest_block_from_analysis_block(
                    _analysis_block(block_id=BLOCK_ID, analysis_text=MULTI_SENTENCE_TEXT)
                )
            ],
            "table_blocks": [],
        },
        analysis_bundle=_analysis_bundle(
            analysis_block=_analysis_block(block_id=BLOCK_ID, analysis_text=MULTI_SENTENCE_TEXT)
        ),
        expected_semantic_module_id="clinical_safety",
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
    )
    bundle = build_route_stage_artifacts(
        routed=routed,
        route_input_envelope={
            "route_input_id": "route_input_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
        },
        block_manifest={
            "block_manifest_id": "block_manifest_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
        },
        doc_meta_bundle={
            "doc_meta_bundle_id": "doc_meta_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
        },
        analysis_bundle={
            "analysis_bundle_id": "prepare_analysis_test",
            "doc_id": "doc_test",
            "file_hash": LINEAGE_FILE_HASH,
        },
    )["routed_bundles"]["aggregate"]
    validate_routed_unit_bundle(bundle, expected_route="aggregate")
    del unit

    broken = dict(bundle)
    broken_units = [dict(unit) for unit in bundle["units"]]
    broken_sentences = [dict(s) for s in broken_units[0]["sentences"]]
    broken_sentences[0].pop("sentence_id")
    broken_units[0]["sentences"] = broken_sentences
    broken["units"] = broken_units
    with pytest.raises(ValueError, match="sentence_id"):
        validate_routed_unit_bundle(broken, expected_route="aggregate")


def test_route_ignores_stale_manifest_sentence_selectors() -> None:
    unit = _route_direct_unit(
        analysis_text=MULTI_SENTENCE_TEXT,
        wrong_selectors=[
            {
                "source_item_index": "1",
                "char_start": "0",
                "char_end": "1",
                "canonical_sentence_id": f"{BLOCK_ID}:S999",
            }
        ],
    )
    assert unit["sentences"][0]["sentence_id"] == f"{BLOCK_ID}:S001"


def test_privacy_masked_analysis_text_handoff_without_selector_coordinates() -> None:
    masked_first = "代号：StudyDrug_001"
    masked_second = "第二句masked。"
    analysis_text = f"{masked_first}{masked_second}"
    analysis_block = {
        "block_id": BLOCK_ID,
        "kind": "paragraph",
        "analysis_text": analysis_text,
        "sentences": [
            {"sentence_id": f"{BLOCK_ID}:S001", "analysis_text": masked_first},
            {"sentence_id": f"{BLOCK_ID}:S002", "analysis_text": masked_second},
        ],
    }
    unit = _route_direct_unit(
        analysis_text=analysis_text,
        analysis_block=analysis_block,
    )
    assert unit["sentences"][0]["text"] == masked_first
    assert unit["sentences"][1]["text"] == masked_second


def test_no_route_local_sentence_alias_generated() -> None:
    unit = _route_direct_unit(analysis_text=MULTI_SENTENCE_TEXT)
    for sentence in unit["sentences"]:
        assert not str(sentence["sentence_id"]).startswith("S0")
