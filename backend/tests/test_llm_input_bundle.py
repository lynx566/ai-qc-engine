from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import (
    build_aggregate_evidence_assessment_input_envelope,
    build_assessment_input_preview,
)
from artifacts.routing.primary_sentence_contract import routed_body_text_from_sentences
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    prepare_aggregate_evidence_semantic_result,
)
from tests.route_test_fixtures import _route_units
from tests.routing_test_helpers import build_current_route_artifacts_from_inputs

_FORBIDDEN_SUBSTRINGS = (
    "normalized_text",
    "span_map",
    "source_ref",
    "document_meta",
    "privacy_transforms",
    "matched_rule",
    "evidence",
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _blocks_by_id(blocks: list[dict]) -> dict[str, dict]:
    return {str(block["block_id"]): block for block in blocks}


def _unit_sentences(unit: dict) -> list[dict]:
    return list(unit.get("sentences") or [])


def _unit_body_text(unit: dict) -> str:
    return routed_body_text_from_sentences(
        _unit_sentences(unit),
        source_stage=str(unit.get("source_stage") or "") or None,
    )


def _context_heading_texts(unit: dict, blocks_by_id: dict[str, dict]) -> set[str]:
    return {
        str(blocks_by_id[block_id].get("analysis_text") or "").strip()
        for block_id in (unit.get("context_block_ids") or [])
        if block_id in blocks_by_id
        and str(blocks_by_id[block_id].get("analysis_text") or "").strip()
    }


def _minimal_doc_meta_bundle(*, doc_id: str = "doc_test") -> dict:
    return {
        "doc_meta_bundle_id": "doc_meta_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "summary": {
            "doc_type": "IB",
            "study_drug": "StudyDrug_001",
            "sponsor": None,
            "investigator": None,
            "protocol_ids": [],
            "version": None,
            "document_date": None,
            "cutoff_date": None,
            "reporting_period": None,
        },
    }


def _current_route_artifacts(
    *,
    coverage_bundle: dict,
    block_manifest: dict,
    doc_meta_bundle: dict,
) -> dict:
    return build_current_route_artifacts_from_inputs(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
    )


def _aggregate_route_bundle(
    *,
    coverage_bundle: dict,
    block_manifest: dict,
    doc_meta_bundle: dict,
) -> dict:
    return _current_route_artifacts(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
    )["routed_bundles"]["aggregate"]


def _current_assessment_input(
    *,
    route_artifacts: dict,
    coverage_bundle: dict,
    block_manifest: dict,
    doc_meta_bundle: dict,
) -> dict:
    aggregate_bundle = route_artifacts["routed_bundles"]["aggregate"]
    semantic_result = prepare_aggregate_evidence_semantic_result(
        aggregate_bundle=aggregate_bundle,
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        assessment_profile_ref=(
            CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref
        ),
        instructions=CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.instructions,
    )
    envelope = build_aggregate_evidence_assessment_input_envelope(
        semantic_result=semantic_result,
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": aggregate_bundle["routed_unit_bundle_id"],
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": route_artifacts["routing_manifest"][
                "routing_manifest_id"
            ],
            "path": "routing_manifest.json",
        },
    )
    return envelope["assessment_input"]


def _minimal_block_manifest(*, doc_id: str = "doc_test") -> dict:
    blocks = [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "heading_path": [],
                "analysis_text": "block one",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0001",
                },
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "order": 2,
                "heading_path": [],
                "analysis_text": "block two",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0002",
                },
            },
            {
                "block_id": "C0003",
                "kind": "paragraph",
                "order": 3,
                "heading_path": [],
                "analysis_text": "gap block",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0003",
                },
            },
            {
                "block_id": "C0004",
                "kind": "paragraph",
                "order": 4,
                "heading_path": [],
                "analysis_text": "not selected",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0004",
                },
            },
            {
                "block_id": "C0005",
                "kind": "paragraph",
                "order": 5,
                "heading_path": ["Section B"],
                "analysis_text": "block five",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0005",
                },
            },
    ]
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": blocks,
    }


def _minimal_coverage_bundle(*, doc_id: str = "doc_test") -> dict:
    def _row(
        block_id: str,
        order: int,
        *,
        selected: bool,
        heading_path: list[str] | None = None,
        zone_id: str | None = None,
    ) -> dict:
        row = {
            "block_id": block_id,
            "block_kind": "paragraph",
            "order": order,
            "heading_path": heading_path or [],
            "selected_by_filter": selected,
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": block_id,
            },
        }
        if zone_id is not None:
            row["zone_match"] = {"zone_id": zone_id}
        return row

    return {
        "coverage_bundle_id": "coverage_filter_test_zone",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "block_manifest_ref": {"block_manifest_id": "block_manifest_test"},
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "zone_key": "ib_clinical_safety_zh",
        "coverage": [
            _row("C0001", 1, selected=True),
            _row("C0002", 2, selected=True),
            _row("C0003", 3, selected=False),
            _row("C0004", 4, selected=False),
            _row("C0005", 5, selected=True, heading_path=["Section B"]),
        ],
    }


def _overview_decompose_bundle_for_tests() -> dict:
    return {
        "overview_decompose_bundle_id": "20260628_224106_dsur_overview_zh",
        "doc_id": "doc_test",
        "source_zone_key": "dsur_overview_zh",
        "components": [
            {
                "component_id": "OVC_MATCH_001",
                "component_type": "safety_overview",
                "status": "active",
                "route_to": "clinical_safety_tag",
                "target_route": "aggregate",
                "source_format": "paragraph",
                "heading_path": ["执行概要"],
                "source_block_ids": ["C7001"],
                "component_text": "overview safety text",
                "component_sentences": [
                    {
                        "sentence_id": "OVC_MATCH_001:S0001",
                        "text": "overview safety sentence",
                        "source_block_id": "C7001",
                        "heading_path": ["执行概要"],
                    }
                ],
                "text_refs": [
                    {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": "C7001",
                    }
                ],
            },
            {
                "component_id": "OVC_MATCH_002",
                "component_type": "conclusion_overview",
                "status": "active",
                "route_to": "clinical_safety_tag",
                "target_route": "aggregate",
                "source_format": "paragraph",
                "heading_path": ["执行概要"],
                "source_block_ids": ["C7002"],
                "component_text": "overview conclusion text",
                "component_sentences": [
                    {
                        "sentence_id": "OVC_MATCH_002:S0001",
                        "text": "overview conclusion sentence",
                        "source_block_id": "C7002",
                        "heading_path": ["执行概要"],
                    }
                ],
                "text_refs": [
                    {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": "C7002",
                    }
                ],
            },
            {
                "component_id": "OVC_MATCH_003",
                "component_type": "safety_guidance_overview",
                "status": "active",
                "route_to": "clinical_safety_tag",
                "target_route": "aggregate",
                "source_format": "paragraph",
                "heading_path": ["执行概要"],
                "source_block_ids": ["C7003"],
                "component_text": "overview guidance text",
                "component_sentences": [
                    {
                        "sentence_id": "OVC_MATCH_003:S0001",
                        "text": "overview guidance sentence",
                        "source_block_id": "C7003",
                        "heading_path": ["执行概要"],
                    }
                ],
                "text_refs": [
                    {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": "C7003",
                    }
                ],
            },
            {
                "component_id": "OVC_MATCH_004",
                "component_type": "conclusion_overview",
                "status": "active",
                "route_to": "clinical_safety_tag",
                "target_route": "aggregate",
                "source_format": "paragraph",
                "heading_path": ["20.结论"],
                "source_block_ids": ["C7004"],
                "component_text": "overview section conclusion text",
                "component_sentences": [
                    {
                        "sentence_id": "OVC_MATCH_004:S0001",
                        "text": "overview section conclusion sentence",
                        "source_block_id": "C7004",
                        "heading_path": ["20.结论"],
                    }
                ],
                "text_refs": [
                    {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": "C7004",
                    }
                ],
            },
            {
                "component_id": "OVC_SKIP_STATUS",
                "component_type": "safety_overview",
                "status": "deferred",
                "route_to": "clinical_safety_tag",
                "target_route": "aggregate",
            },
            {
                "component_id": "OVC_SKIP_ROUTE_TO",
                "component_type": "safety_overview",
                "status": "active",
                "route_to": "other_stage",
                "target_route": "aggregate",
            },
            {
                "component_id": "OVC_SKIP_TARGET",
                "component_type": "safety_overview",
                "status": "active",
                "route_to": "clinical_safety_tag",
                "target_route": "table",
            },
        ],
    }


def test_filter_text_units_default_source_stage_is_filter_projection() -> None:
    outputs = _current_route_artifacts(
        coverage_bundle=_minimal_coverage_bundle(),
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    aggregate_units = outputs["routed_bundles"]["aggregate"]["units"]
    assert aggregate_units
    for unit in aggregate_units:
        assert unit["source_stage"] == "filter_projection"


def test_filter_text_units_use_canonical_projected_source_stage() -> None:
    coverage = _minimal_coverage_bundle()
    for row in coverage["coverage"]:
        if row.get("selected_by_filter") is True:
            row["source_stage"] = "manual_input"

    outputs = _current_route_artifacts(
        coverage_bundle=coverage,
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    aggregate_units = outputs["routed_bundles"]["aggregate"]["units"]
    assert aggregate_units
    for unit in aggregate_units:
        assert unit["source_stage"] == "filter_projection"


def test_minimal_fixture_builds_one_paragraph_per_unit() -> None:
    coverage = _minimal_coverage_bundle()
    manifest = _minimal_block_manifest()
    doc_meta = _minimal_doc_meta_bundle()
    artifacts = _current_route_artifacts(
        coverage_bundle=coverage,
        block_manifest=manifest,
        doc_meta_bundle=doc_meta,
    )
    bundle = artifacts["routed_bundles"]["aggregate"]

    assert bundle["routed_unit_bundle_id"]
    assert bundle["route"] == "aggregate"
    assert len(bundle["units"]) == 3
    assert bundle["units"][0]["unit_id"] == "TU0001"
    assert bundle["units"][0]["source_block_ids"] == ["C0001"]
    assert bundle["units"][0]["context_block_ids"] == []
    assert bundle["units"][0]["all_source_block_ids"] == ["C0001"]
    assert bundle["units"][0]["candidate_block_kinds"] == ["paragraph"]
    assert bundle["units"][0]["route"] == "aggregate"
    assert _unit_body_text(bundle["units"][0]) == "sample text"
    assert [s["sentence_id"] for s in _unit_sentences(bundle["units"][0])] == [
        "C0001:S001",
    ]
    assert "context_sentences" not in bundle["units"][0]
    assert len(_unit_sentences(bundle["units"][0])) == 1
    assert _unit_sentences(bundle["units"][0])[0]["source_block_id"] == "C0001"
    assert bundle["units"][1]["unit_id"] == "TU0002"
    assert bundle["units"][1]["source_block_ids"] == ["C0002"]
    assert _unit_body_text(bundle["units"][1]) == "sample text"
    assert bundle["units"][2]["unit_id"] == "TU0003"
    assert bundle["units"][2]["source_block_ids"] == ["C0005"]
    assert bundle["units"][2]["heading_path"] == ["Section B"]
    assert bundle["units"][0]["route_basis"] == "selected_zone_default_text"

    assessment_input = _current_assessment_input(
        route_artifacts=artifacts,
        coverage_bundle=coverage,
        block_manifest=manifest,
        doc_meta_bundle=doc_meta,
    )
    assert assessment_input["doc_meta"]["study_drug"] == "StudyDrug_001"
    assert (
        assessment_input["assessment_profile_ref"]
        == "clinical_safety_aggregate_heading_scope_assessment_zh"
    )
    assert "tag_profile_ref" not in assessment_input




def test_heading_path_lcp_single_heading() -> None:
    """A unit whose single candidate row carries a path returns that path unchanged."""
    coverage = _minimal_coverage_bundle()
    block_manifest = _minimal_block_manifest()
    target_path = ["Section A", "Sub 1"]
    for row in coverage["coverage"]:
        if row["selected_by_filter"]:
            row["heading_path"] = list(target_path)
            block_id = str(row["block_id"])
            for block in block_manifest["blocks"]:
                if str(block.get("block_id") or "") == block_id:
                    block["heading_path"] = list(target_path)
    bundle = _aggregate_route_bundle(
        coverage_bundle=coverage,
        block_manifest=block_manifest,
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    for unit in bundle["units"]:
        assert unit["heading_path"] == target_path


def test_sibling_subheadings_keep_full_heading_path_per_paragraph() -> None:
    """Sibling sub-headings each produce a separate TU with its own full path."""
    coverage = _minimal_coverage_bundle()
    rows = coverage["coverage"]
    selected = [r for r in rows if r["selected_by_filter"]]
    selected[0]["heading_path"] = ["Chapter", "1.1"]
    selected[1]["heading_path"] = ["Chapter", "1.2"]
    bundle = _aggregate_route_bundle(
        coverage_bundle=coverage,
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    assert bundle["units"][0]["heading_path"] == ["Chapter", "1.1"]
    assert bundle["units"][1]["heading_path"] == ["Chapter", "1.2"]


def test_unit_single_paragraph_preserves_sentence_heading_path() -> None:
    """Each paragraph TU keeps its source block heading path on every sentence."""
    coverage = _minimal_coverage_bundle()
    rows = coverage["coverage"]
    selected = [r for r in rows if r["selected_by_filter"]]
    selected[0]["heading_path"] = ["Chapter", "1.1"]
    selected[1]["heading_path"] = ["Chapter", "1.2"]
    bundle = _aggregate_route_bundle(
        coverage_bundle=coverage,
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )

    unit_one, unit_two = bundle["units"][:2]
    assert unit_one["heading_path"] == ["Chapter", "1.1"]
    assert _unit_sentences(unit_one)[0]["source_block_id"] == "C0001"
    assert unit_two["heading_path"] == ["Chapter", "1.2"]
    assert _unit_sentences(unit_two)[0]["source_block_id"] == "C0002"


def test_different_top_level_paths_stay_on_separate_units() -> None:
    """Top-level chapter changes produce separate TUs with distinct paths."""
    coverage = _minimal_coverage_bundle()
    rows = coverage["coverage"]
    selected = [r for r in rows if r["selected_by_filter"]]
    selected[0]["heading_path"] = ["Chapter A"]
    selected[1]["heading_path"] = ["Chapter B"]
    bundle = _aggregate_route_bundle(
        coverage_bundle=coverage,
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    assert bundle["units"][0]["heading_path"] == ["Chapter A"]
    assert bundle["units"][1]["heading_path"] == ["Chapter B"]


def test_empty_heading_path_on_single_paragraph_unit() -> None:
    """When a paragraph row has no heading path the unit heading_path is empty."""
    coverage = _minimal_coverage_bundle()
    for row in coverage["coverage"]:
        row["heading_path"] = []
    bundle = _aggregate_route_bundle(
        coverage_bundle=coverage,
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    assert bundle["units"][0]["heading_path"] == []


def test_mixed_empty_and_nonempty_paths_stay_on_separate_units() -> None:
    """Empty and non-empty paths on consecutive paragraphs stay separate TUs."""
    coverage = _minimal_coverage_bundle()
    rows = coverage["coverage"]
    selected = [r for r in rows if r["selected_by_filter"]]
    selected[0]["heading_path"] = []
    selected[1]["heading_path"] = ["Chapter", "Sub"]
    bundle = _aggregate_route_bundle(
        coverage_bundle=coverage,
        block_manifest=_minimal_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    assert bundle["units"][0]["heading_path"] == []
    assert "context_sentences" not in bundle["units"][0]
    assert bundle["units"][1]["heading_path"] == ["Chapter", "Sub"]


def test_build_assessment_input_preview_truncates_text_only_in_preview() -> None:
    coverage = _minimal_coverage_bundle()
    manifest = _minimal_block_manifest()
    doc_meta = _minimal_doc_meta_bundle()
    route_artifacts = _current_route_artifacts(
        coverage_bundle=coverage,
        block_manifest=manifest,
        doc_meta_bundle=doc_meta,
    )
    assessment_input = _current_assessment_input(
        route_artifacts=route_artifacts,
        coverage_bundle=coverage,
        block_manifest=manifest,
        doc_meta_bundle=doc_meta,
    )
    assessment_input_before = json.loads(json.dumps(assessment_input))
    preview = build_assessment_input_preview(assessment_input, text_preview_chars=5)

    aggregate_preview = preview["route_previews"]["aggregate"]
    assert preview["route_counts"]["aggregate"] == 3
    first_unit = assessment_input["heading_scopes"][0]["units"][0]
    assert aggregate_preview[0]["sentence_count"] == len(first_unit["sentences"])
    assert aggregate_preview[0]["sentence_count"] > 0
    assert aggregate_preview[0]["text_preview"].endswith("…")
    assert len(first_unit["sentences"][0]["text"]) > len(
        aggregate_preview[0]["text_preview"]
    )
    assert assessment_input == assessment_input_before


def _safety_context_candidate_coverage_bundle() -> dict:
    def _row(
        block_id: str,
        order: int,
        *,
        block_kind: str,
        heading_path: list[str],
    ) -> dict:
        return {
            "block_id": block_id,
            "block_kind": block_kind,
            "order": order,
            "heading_path": heading_path,
            "selected_by_filter": True,
            "zone_match": {"zone_id": "Z1"},
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": block_id,
            },
        }

    heading_path = ["六、临床安全性", "6.1 StudyDrug_001"]
    return {
        "coverage_bundle_id": "coverage_safety_context_candidate",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "block_manifest_ref": {"block_manifest_id": "block_manifest_test"},
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "zone_key": "ib_clinical_safety_zh",
        "coverage": [
            _row("C0007", 7, block_kind="heading", heading_path=["六、临床安全性"]),
            _row("C0008", 8, block_kind="heading", heading_path=heading_path),
            _row("C0009", 9, block_kind="paragraph", heading_path=heading_path),
            _row("C0010", 10, block_kind="table_caption", heading_path=heading_path),
            _row("C0011", 11, block_kind="table_note", heading_path=heading_path),
        ],
    }


def _safety_context_candidate_block_manifest() -> dict:
    heading_path = ["六、临床安全性", "6.1 StudyDrug_001"]
    c0009_text = "共有31例（77.5%）试验参与者发生168例次不良事件（AE）。"
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": [
            {
                "block_id": "C0007",
                "kind": "heading",
                "order": 7,
                "heading_path": ["六、临床安全性"],
                "analysis_text": "六、临床安全性",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0007",
                },
            },
            {
                "block_id": "C0008",
                "kind": "heading",
                "order": 8,
                "heading_path": heading_path,
                "analysis_text": "6.1 StudyDrug_001",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0008",
                },
            },
            {
                "block_id": "C0009",
                "kind": "paragraph",
                "order": 9,
                "heading_path": heading_path,
                "analysis_text": c0009_text,
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0009",
                },
            },
            {
                "block_id": "C0010",
                "kind": "table_caption",
                "order": 10,
                "heading_path": heading_path,
                "analysis_text": "表1 StudyDrug_001治疗后不良反应发生情况汇总",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0010",
                },
            },
            {
                "block_id": "C0011",
                "kind": "table_note",
                "order": 11,
                "heading_path": heading_path,
                "analysis_text": "注：数据截至2023年12月17日。",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0011",
                },
            },
        ],
    }


def test_context_candidate_split_keeps_heading_context_for_aggregate_unit() -> None:
    tag_prepare_outputs = _current_route_artifacts(
        coverage_bundle=_safety_context_candidate_coverage_bundle(),
        block_manifest=_safety_context_candidate_block_manifest(),
        doc_meta_bundle=_minimal_doc_meta_bundle(),
    )
    bundle = tag_prepare_outputs["routed_bundles"]["aggregate"]

    unit = bundle["units"][0]
    assert len(unit["context_block_ids"]) == 2
    assert len(_unit_sentences(unit)) == 1
    assert _unit_sentences(unit)[0]["source_block_id"] == "C0009"
    assert unit["source_block_ids"] == ["C0009"]
    assert unit["context_block_ids"] == ["C0007", "C0008"]
    assert unit["all_source_block_ids"] == ["C0007", "C0008", "C0009"]
    assert unit["heading_path"] == ["六、临床安全性", "6.1 StudyDrug_001"]
    assert unit["route"] == "aggregate"
    assert unit["route_basis"] == "selected_zone_default_text"
    assert "context_sentences" not in unit

    table_units = tag_prepare_outputs["routed_bundles"]["table"]["units"]
    assert len(table_units) == 2
    caption_note_ids = {
        block_id
        for table_unit in table_units
        for block_id in table_unit.get("source_block_ids") or []
    }
    assert caption_note_ids == {"C0010", "C0011"}


def _grouping_row(
    block_id: str,
    order: int,
    *,
    block_kind: str,
    heading_path: list[str],
    zone_id: str = "Z1",
) -> dict:
    return {
        "block_id": block_id,
        "block_kind": block_kind,
        "order": order,
        "heading_path": heading_path,
        "selected_by_filter": True,
        "zone_match": {"zone_id": zone_id},
        "text_ref": {
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": block_id,
        },
    }


def _grouping_block(
    block_id: str,
    order: int,
    *,
    kind: str,
    heading_path: list[str],
    analysis_text: str,
) -> dict:
    block = {
        "block_id": block_id,
        "kind": kind,
        "order": order,
        "heading_path": heading_path,
        "analysis_text": analysis_text,
        "text_ref": {
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": block_id,
        },
    }
    return block


def _build_grouping_outputs(rows: list[dict], blocks: list[dict]):
    coverage_bundle = {
        "coverage_bundle_id": "coverage_grouping_regression",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "block_manifest_ref": {"block_manifest_id": "block_manifest_test"},
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "zone_key": "ib_clinical_safety_zh",
        "coverage": rows,
    }
    block_manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": blocks,
        "table_blocks": [],
    }
    return _route_units(coverage=coverage_bundle, manifest=block_manifest)


def test_grouping_mixed_route_regression_heading_no_longer_bridges_routes() -> None:
    heading_agg = ["六、临床安全性", "不良事件总体概述"]
    heading_table = ["六、临床安全性", "各试验参与者不良事件列表"]
    rows = [
        _grouping_row("C1001", 1, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("C1002", 2, block_kind="heading", heading_path=heading_table),
        _grouping_row("C1003", 3, block_kind="paragraph", heading_path=heading_table),
        _grouping_row("C1004", 4, block_kind="heading", heading_path=heading_agg),
        _grouping_row("C1005", 5, block_kind="paragraph", heading_path=heading_agg),
    ]
    blocks = [
        _grouping_block(
            "C1001",
            1,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate paragraph",
        ),
        _grouping_block(
            "C1002",
            2,
            kind="heading",
            heading_path=heading_table,
            analysis_text="各试验参与者不良事件列表",
        ),
        _grouping_block(
            "C1003",
            3,
            kind="paragraph",
            heading_path=heading_table,
            analysis_text="table paragraph",
        ),
        _grouping_block(
            "C1004",
            4,
            kind="heading",
            heading_path=heading_agg,
            analysis_text="不良事件总体概述",
        ),
        _grouping_block(
            "C1005",
            5,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate paragraph 2",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)

    aggregate_units = outputs.units_by_route["aggregate"]
    table_units = outputs.units_by_route["table"]
    assert len(aggregate_units) == 2
    assert len(table_units) == 1
    assert outputs.route_counts["total_routed_unit_count"] == 3
    assert aggregate_units[0]["source_block_ids"] == ["C1001"]
    assert table_units[0]["source_block_ids"] == ["C1003"]
    assert aggregate_units[1]["source_block_ids"] == ["C1005"]
    assert all(unit["route"] == "aggregate" for unit in aggregate_units)
    assert table_units[0]["route"] == "table"


def test_grouping_heading_attaches_to_following_unit_context_only() -> None:
    heading_table = ["六、临床安全性", "各试验参与者不良事件列表"]
    rows = [
        _grouping_row("C2001", 1, block_kind="heading", heading_path=heading_table),
        _grouping_row("C2002", 2, block_kind="paragraph", heading_path=heading_table),
    ]
    blocks = [
        _grouping_block(
            "C2001",
            1,
            kind="heading",
            heading_path=heading_table,
            analysis_text="各试验参与者不良事件列表",
        ),
        _grouping_block(
            "C2002",
            2,
            kind="paragraph",
            heading_path=heading_table,
            analysis_text="table paragraph",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    table_unit = outputs.units_by_route["table"][0]

    assert table_unit["context_block_ids"] == ["C2001"]
    assert [sentence["source_block_id"] for sentence in _unit_sentences(table_unit)] == [
        "C2002"
    ]
    assert "C2001" not in table_unit["source_block_ids"]
    assert table_unit["context_block_ids"] == ["C2001"]


def test_grouping_heading_splits_same_route_units() -> None:
    heading_agg = ["六、临床安全性", "不良事件总体概述"]
    heading_sub = ["六、临床安全性", "6.1.1 安全性概要"]
    rows = [
        _grouping_row("C3001", 1, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("C3002", 2, block_kind="heading", heading_path=heading_sub),
        _grouping_row("C3003", 3, block_kind="paragraph", heading_path=heading_sub),
    ]
    blocks = [
        _grouping_block(
            "C3001",
            1,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate paragraph 1",
        ),
        _grouping_block(
            "C3002",
            2,
            kind="heading",
            heading_path=heading_sub,
            analysis_text="6.1.1 安全性概要",
        ),
        _grouping_block(
            "C3003",
            3,
            kind="paragraph",
            heading_path=heading_sub,
            analysis_text="aggregate paragraph 2",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    aggregate_units = outputs.units_by_route["aggregate"]

    assert len(aggregate_units) == 2
    assert aggregate_units[0]["source_block_ids"] == ["C3001"]
    assert aggregate_units[1]["source_block_ids"] == ["C3003"]


def test_grouping_consecutive_paragraphs_stay_separate_units() -> None:
    heading_agg = ["六、临床安全性", "不良事件总体概述"]
    heading_sub = ["六、临床安全性", "6.1.1 安全性概要"]
    rows = [
        _grouping_row("C4001", 1, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("C4002", 2, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("C4003", 3, block_kind="heading", heading_path=heading_sub),
        _grouping_row("C4004", 4, block_kind="paragraph", heading_path=heading_sub),
    ]
    blocks = [
        _grouping_block(
            "C4001",
            1,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate paragraph 1",
        ),
        _grouping_block(
            "C4002",
            2,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate paragraph 2",
        ),
        _grouping_block(
            "C4003",
            3,
            kind="heading",
            heading_path=heading_sub,
            analysis_text="6.1.1 安全性概要",
        ),
        _grouping_block(
            "C4004",
            4,
            kind="paragraph",
            heading_path=heading_sub,
            analysis_text="aggregate paragraph 3",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    aggregate_units = outputs.units_by_route["aggregate"]

    assert len(aggregate_units) == 3
    assert aggregate_units[0]["source_block_ids"] == ["C4001"]
    assert aggregate_units[1]["source_block_ids"] == ["C4002"]
    assert aggregate_units[2]["source_block_ids"] == ["C4004"]
    assert aggregate_units[0]["context_block_ids"] == []
    assert aggregate_units[1]["context_block_ids"] == []
    assert aggregate_units[2]["context_block_ids"] == ["C4003"]


def test_grouping_trailing_heading_does_not_create_empty_unit() -> None:
    heading_agg = ["六、临床安全性", "不良事件总体概述"]
    heading_tail = ["六、临床安全性", "6.9 仅标题尾部"]
    rows = [
        _grouping_row("C5001", 1, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("C5002", 2, block_kind="heading", heading_path=heading_tail),
    ]
    blocks = [
        _grouping_block(
            "C5001",
            1,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate paragraph",
        ),
        _grouping_block(
            "C5002",
            2,
            kind="heading",
            heading_path=heading_tail,
            analysis_text="6.9 仅标题尾部",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    aggregate_units = outputs.units_by_route["aggregate"]

    assert len(aggregate_units) == 1
    assert aggregate_units[0]["source_block_ids"] == ["C5001"]
    assert _unit_sentences(aggregate_units[0])


def test_grouping_drops_sibling_heading_from_context_before_candidate() -> None:
    heading_parent = ["12.2 不良事件"]
    heading_prev_sibling = ["12.2 不良事件", "12.2.2 不良事件的列出"]
    heading_current = ["12.2 不良事件", "12.2.3 不良事件分析"]
    rows = [
        _grouping_row("C6001", 1, block_kind="heading", heading_path=heading_parent),
        _grouping_row("C6002", 2, block_kind="heading", heading_path=heading_prev_sibling),
        _grouping_row("C6003", 3, block_kind="heading", heading_path=heading_current),
        _grouping_row("C6004", 4, block_kind="paragraph", heading_path=heading_current),
    ]
    blocks = [
        _grouping_block(
            "C6001",
            1,
            kind="heading",
            heading_path=heading_parent,
            analysis_text="12.2 不良事件",
        ),
        _grouping_block(
            "C6002",
            2,
            kind="heading",
            heading_path=heading_prev_sibling,
            analysis_text="12.2.2 不良事件的列出",
        ),
        _grouping_block(
            "C6003",
            3,
            kind="heading",
            heading_path=heading_current,
            analysis_text="12.2.3 不良事件分析",
        ),
        _grouping_block(
            "C6004",
            4,
            kind="paragraph",
            heading_path=heading_current,
            analysis_text="发生率≥10%的TEAE包括贫血、乏力和恶心。",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    aggregate_units = outputs.units_by_route["aggregate"]

    assert len(aggregate_units) == 1
    unit = aggregate_units[0]
    assert unit["source_block_ids"] == ["C6004"]
    assert unit["context_block_ids"] == ["C6001", "C6003"]
    context_texts = _context_heading_texts(unit, _blocks_by_id(blocks))
    assert "12.2 不良事件" in context_texts
    assert "12.2.3 不良事件分析" in context_texts
    assert "12.2.2 不良事件的列出" not in context_texts


def test_grouping_keeps_only_current_heading_for_sibling_chapters() -> None:
    heading_124 = ["12.4 临床实验室评估"]
    heading_125 = ["12.5 生命体征、体格检查发现和其他安全性相关观察结果"]
    heading_126 = ["12.6 安全性结论"]
    rows = [
        _grouping_row("C7001", 1, block_kind="heading", heading_path=heading_124),
        _grouping_row("C7002", 2, block_kind="heading", heading_path=heading_125),
        _grouping_row("C7003", 3, block_kind="heading", heading_path=heading_126),
        _grouping_row("C7004", 4, block_kind="paragraph", heading_path=heading_126),
    ]
    blocks = [
        _grouping_block(
            "C7001",
            1,
            kind="heading",
            heading_path=heading_124,
            analysis_text="12.4 临床实验室评估",
        ),
        _grouping_block(
            "C7002",
            2,
            kind="heading",
            heading_path=heading_125,
            analysis_text="12.5 生命体征、体格检查发现和其他安全性相关观察结果",
        ),
        _grouping_block(
            "C7003",
            3,
            kind="heading",
            heading_path=heading_126,
            analysis_text="12.6 安全性结论",
        ),
        _grouping_block(
            "C7004",
            4,
            kind="paragraph",
            heading_path=heading_126,
            analysis_text="总体而言，StudyDrug_001安全性可接受。",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    aggregate_units = outputs.units_by_route["aggregate"]

    assert len(aggregate_units) == 1
    unit = aggregate_units[0]
    assert unit["source_block_ids"] == ["C7004"]
    assert unit["context_block_ids"] == ["C7003"]
    context_texts = _context_heading_texts(unit, _blocks_by_id(blocks))
    assert "12.6 安全性结论" in context_texts
    assert "12.4 临床实验室评估" not in context_texts
    assert "12.5 生命体征、体格检查发现和其他安全性相关观察结果" not in context_texts


def test_grouping_keeps_ancestor_and_current_heading_context() -> None:
    heading_parent = ["12.2 不良事件"]
    heading_current = ["12.2 不良事件", "12.2.3 不良事件分析"]
    rows = [
        _grouping_row("C8001", 1, block_kind="heading", heading_path=heading_parent),
        _grouping_row("C8002", 2, block_kind="heading", heading_path=heading_current),
        _grouping_row("C8003", 3, block_kind="paragraph", heading_path=heading_current),
    ]
    blocks = [
        _grouping_block(
            "C8001",
            1,
            kind="heading",
            heading_path=heading_parent,
            analysis_text="12.2 不良事件",
        ),
        _grouping_block(
            "C8002",
            2,
            kind="heading",
            heading_path=heading_current,
            analysis_text="12.2.3 不良事件分析",
        ),
        _grouping_block(
            "C8003",
            3,
            kind="paragraph",
            heading_path=heading_current,
            analysis_text="发生率≥10%的TEAE包括贫血。",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    aggregate_units = outputs.units_by_route["aggregate"]

    assert len(aggregate_units) == 1
    unit = aggregate_units[0]
    assert unit["source_block_ids"] == ["C8003"]
    assert unit["context_block_ids"] == ["C8001", "C8002"]
    context_texts = _context_heading_texts(unit, _blocks_by_id(blocks))
    assert "12.2 不良事件" in context_texts
    assert "12.2.3 不良事件分析" in context_texts


def test_grouping_table_route_filters_sibling_heading_context() -> None:
    heading_parent = ["12.2 不良事件"]
    heading_prev_sibling = ["12.2 不良事件", "12.2.2 不良事件分析"]
    heading_current = ["12.2 不良事件", "12.2.3 不良事件列表"]
    rows = [
        _grouping_row("C9001", 1, block_kind="heading", heading_path=heading_parent),
        _grouping_row("C9002", 2, block_kind="heading", heading_path=heading_prev_sibling),
        _grouping_row("C9003", 3, block_kind="heading", heading_path=heading_current),
        _grouping_row("C9004", 4, block_kind="paragraph", heading_path=heading_current),
    ]
    blocks = [
        _grouping_block(
            "C9001",
            1,
            kind="heading",
            heading_path=heading_parent,
            analysis_text="12.2 不良事件",
        ),
        _grouping_block(
            "C9002",
            2,
            kind="heading",
            heading_path=heading_prev_sibling,
            analysis_text="12.2.2 不良事件分析",
        ),
        _grouping_block(
            "C9003",
            3,
            kind="heading",
            heading_path=heading_current,
            analysis_text="12.2.3 不良事件列表",
        ),
        _grouping_block(
            "C9004",
            4,
            kind="paragraph",
            heading_path=heading_current,
            analysis_text="不良事件列表见下文。",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    table_units = outputs.units_by_route["table"]

    assert len(table_units) == 1
    unit = table_units[0]
    assert unit["source_block_ids"] == ["C9004"]
    assert unit["context_block_ids"] == ["C9001", "C9003"]
    context_texts = _context_heading_texts(unit, _blocks_by_id(blocks))
    assert "12.2 不良事件" in context_texts
    assert "12.2.3 不良事件列表" in context_texts
    assert "12.2.2 不良事件分析" not in context_texts


def test_grouping_same_heading_yields_one_tu_per_paragraph() -> None:
    heading_a = ["Section A"]
    rows = [
        _grouping_row("CH001", 1, block_kind="heading", heading_path=heading_a),
        _grouping_row("CP001", 2, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("CP002", 3, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("CP003", 4, block_kind="paragraph", heading_path=heading_a),
    ]
    blocks = [
        _grouping_block(
            "CH001",
            1,
            kind="heading",
            heading_path=heading_a,
            analysis_text="Section A",
        ),
        _grouping_block(
            "CP001",
            2,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="paragraph one",
        ),
        _grouping_block(
            "CP002",
            3,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="paragraph two",
        ),
        _grouping_block(
            "CP003",
            4,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="paragraph three",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    assert len(units) == 3
    for unit, block_id in zip(units, ["CP001", "CP002", "CP003"]):
        assert unit["source_block_ids"] == [block_id]
        assert _unit_body_text(unit) == "sample text"


def test_grouping_heading_context_persists_to_all_paragraph_tus() -> None:
    heading_a = ["Section A"]
    rows = [
        _grouping_row("CH001", 1, block_kind="heading", heading_path=heading_a),
        _grouping_row("CP001", 2, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("CP002", 3, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("CP003", 4, block_kind="paragraph", heading_path=heading_a),
    ]
    blocks = [
        _grouping_block(
            "CH001",
            1,
            kind="heading",
            heading_path=heading_a,
            analysis_text="Section A",
        ),
        _grouping_block(
            "CP001",
            2,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="paragraph one",
        ),
        _grouping_block(
            "CP002",
            3,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="paragraph two",
        ),
        _grouping_block(
            "CP003",
            4,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="paragraph three",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    for unit in units:
        assert unit["context_block_ids"] == ["CH001"]
        context_texts = _context_heading_texts(unit, _blocks_by_id(blocks))
        assert context_texts == {"Section A"}
        assert "CH001" not in unit["source_block_ids"]
        assert unit["heading_path"] == heading_a


def test_grouping_heading_switch_does_not_leak_context() -> None:
    heading_a = ["Section A"]
    heading_b = ["Section B"]
    rows = [
        _grouping_row("CHA001", 1, block_kind="heading", heading_path=heading_a),
        _grouping_row("PA001", 2, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("PA002", 3, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("CHB001", 4, block_kind="heading", heading_path=heading_b),
        _grouping_row("PB001", 5, block_kind="paragraph", heading_path=heading_b),
        _grouping_row("PB002", 6, block_kind="paragraph", heading_path=heading_b),
    ]
    blocks = [
        _grouping_block(
            "CHA001",
            1,
            kind="heading",
            heading_path=heading_a,
            analysis_text="Section A",
        ),
        _grouping_block(
            "PA001",
            2,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="A paragraph one",
        ),
        _grouping_block(
            "PA002",
            3,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="A paragraph two",
        ),
        _grouping_block(
            "CHB001",
            4,
            kind="heading",
            heading_path=heading_b,
            analysis_text="Section B",
        ),
        _grouping_block(
            "PB001",
            5,
            kind="paragraph",
            heading_path=heading_b,
            analysis_text="B paragraph one",
        ),
        _grouping_block(
            "PB002",
            6,
            kind="paragraph",
            heading_path=heading_b,
            analysis_text="B paragraph two",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    assert len(units) == 4
    a_units = units[:2]
    b_units = units[2:]
    blocks_by_id = _blocks_by_id(blocks)
    for unit in a_units:
        assert unit["context_block_ids"] == ["CHA001"]
        assert unit["heading_path"] == heading_a
        assert "Section A" in _context_heading_texts(unit, blocks_by_id)
        assert "Section B" not in _context_heading_texts(unit, blocks_by_id)
    for unit in b_units:
        assert unit["context_block_ids"] == ["CHB001"]
        assert unit["heading_path"] == heading_b
        assert "Section B" in _context_heading_texts(unit, blocks_by_id)
        assert "Section A" not in _context_heading_texts(unit, blocks_by_id)


def test_grouping_multilevel_heading_lineage_per_paragraph() -> None:
    heading_h1 = ["Chapter"]
    heading_h2a = ["Chapter", "H2-A"]
    heading_h2b = ["Chapter", "H2-B"]
    rows = [
        _grouping_row("H1001", 1, block_kind="heading", heading_path=heading_h1),
        _grouping_row("H2A01", 2, block_kind="heading", heading_path=heading_h2a),
        _grouping_row("P1001", 3, block_kind="paragraph", heading_path=heading_h2a),
        _grouping_row("P1002", 4, block_kind="paragraph", heading_path=heading_h2a),
        _grouping_row("H2B01", 5, block_kind="heading", heading_path=heading_h2b),
        _grouping_row("P1003", 6, block_kind="paragraph", heading_path=heading_h2b),
    ]
    blocks = [
        _grouping_block(
            "H1001",
            1,
            kind="heading",
            heading_path=heading_h1,
            analysis_text="Chapter",
        ),
        _grouping_block(
            "H2A01",
            2,
            kind="heading",
            heading_path=heading_h2a,
            analysis_text="H2-A",
        ),
        _grouping_block(
            "P1001",
            3,
            kind="paragraph",
            heading_path=heading_h2a,
            analysis_text="paragraph one",
        ),
        _grouping_block(
            "P1002",
            4,
            kind="paragraph",
            heading_path=heading_h2a,
            analysis_text="paragraph two",
        ),
        _grouping_block(
            "H2B01",
            5,
            kind="heading",
            heading_path=heading_h2b,
            analysis_text="H2-B",
        ),
        _grouping_block(
            "P1003",
            6,
            kind="paragraph",
            heading_path=heading_h2b,
            analysis_text="paragraph three",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    assert len(units) == 3
    assert units[0]["heading_path"] == heading_h2a
    assert units[1]["heading_path"] == heading_h2a
    assert units[2]["heading_path"] == heading_h2b
    assert units[0]["context_block_ids"] == ["H1001", "H2A01"]
    assert units[1]["context_block_ids"] == ["H1001", "H2A01"]
    assert units[2]["context_block_ids"] == ["H1001", "H2B01"]
    context_texts_p3 = _context_heading_texts(units[2], _blocks_by_id(blocks))
    assert "H2-B" in context_texts_p3
    assert "H2-A" not in context_texts_p3


def test_grouping_multisentence_paragraph_stays_one_tu() -> None:
    heading_a = ["Section A"]
    multi_sentence_text = "第一句。第二句。第三句。"
    rows = [
        _grouping_row("CH001", 1, block_kind="heading", heading_path=heading_a),
        _grouping_row("CP001", 2, block_kind="paragraph", heading_path=heading_a),
    ]
    blocks = [
        _grouping_block(
            "CH001",
            1,
            kind="heading",
            heading_path=heading_a,
            analysis_text="Section A",
        ),
        _grouping_block(
            "CP001",
            2,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text=multi_sentence_text,
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    assert len(units) == 1
    assert units[0]["source_block_ids"] == ["CP001"]
    assert _unit_body_text(units[0]) == "sample text"
    assert len(_unit_sentences(units[0])) >= 1


def test_grouping_list_items_and_paragraphs_stay_separate_tus() -> None:
    heading_a = ["Section A"]
    rows = [
        _grouping_row("CH001", 1, block_kind="heading", heading_path=heading_a),
        _grouping_row("CP001", 2, block_kind="paragraph", heading_path=heading_a),
        _grouping_row("CL001", 3, block_kind="list_item", heading_path=heading_a),
        _grouping_row("CL002", 4, block_kind="list_item", heading_path=heading_a),
    ]
    blocks = [
        _grouping_block(
            "CH001",
            1,
            kind="heading",
            heading_path=heading_a,
            analysis_text="Section A",
        ),
        _grouping_block(
            "CP001",
            2,
            kind="paragraph",
            heading_path=heading_a,
            analysis_text="intro paragraph",
        ),
        _grouping_block(
            "CL001",
            3,
            kind="list_item",
            heading_path=heading_a,
            analysis_text="list item one",
        ),
        _grouping_block(
            "CL002",
            4,
            kind="list_item",
            heading_path=heading_a,
            analysis_text="list item two",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    assert len(units) == 3
    assert units[0]["source_block_ids"] == ["CP001"]
    assert units[1]["source_block_ids"] == ["CL001"]
    assert units[2]["source_block_ids"] == ["CL002"]
    for unit in units:
        assert unit["context_block_ids"] == ["CH001"]


def test_grouping_revisited_heading_path_uses_latest_heading_block_only() -> None:
    path_a = ["Section A"]
    path_b = ["Section B"]
    rows = [
        _grouping_row("HA001", 1, block_kind="heading", heading_path=path_a),
        _grouping_row("PA001", 2, block_kind="paragraph", heading_path=path_a),
        _grouping_row("HB001", 3, block_kind="heading", heading_path=path_b),
        _grouping_row("PB001", 4, block_kind="paragraph", heading_path=path_b),
        _grouping_row("HA002", 5, block_kind="heading", heading_path=path_a),
        _grouping_row("PA002", 6, block_kind="paragraph", heading_path=path_a),
    ]
    blocks = [
        _grouping_block(
            "HA001",
            1,
            kind="heading",
            heading_path=path_a,
            analysis_text="Section A first",
        ),
        _grouping_block(
            "PA001",
            2,
            kind="paragraph",
            heading_path=path_a,
            analysis_text="first visit paragraph",
        ),
        _grouping_block(
            "HB001",
            3,
            kind="heading",
            heading_path=path_b,
            analysis_text="Section B",
        ),
        _grouping_block(
            "PB001",
            4,
            kind="paragraph",
            heading_path=path_b,
            analysis_text="section b paragraph",
        ),
        _grouping_block(
            "HA002",
            5,
            kind="heading",
            heading_path=path_a,
            analysis_text="Section A revisited",
        ),
        _grouping_block(
            "PA002",
            6,
            kind="paragraph",
            heading_path=path_a,
            analysis_text="second visit paragraph",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    units = outputs.units_by_route["aggregate"]

    assert len(units) == 3
    first_visit = next(unit for unit in units if unit["source_block_ids"] == ["PA001"])
    section_b = next(unit for unit in units if unit["source_block_ids"] == ["PB001"])
    second_visit = next(unit for unit in units if unit["source_block_ids"] == ["PA002"])

    assert first_visit["context_block_ids"] == ["HA001"]
    assert section_b["context_block_ids"] == ["HB001"]
    assert second_visit["context_block_ids"] == ["HA002"]
    assert "HA001" not in second_visit["context_block_ids"]
    second_context_texts = _context_heading_texts(second_visit, _blocks_by_id(blocks))
    assert "Section A revisited" in second_context_texts
    assert "Section A first" not in second_context_texts


def test_grouping_case_route_preserves_preexisting_merge_behavior() -> None:
    """Case-route text keeps parent consecutive merge pending route-specific decomposition."""
    heading_case = ["12 临床安全性", "12.3.2 病例叙述"]
    rows = [
        _grouping_row("CH001", 1, block_kind="heading", heading_path=heading_case),
        _grouping_row("CP001", 2, block_kind="paragraph", heading_path=heading_case),
        _grouping_row("CP002", 3, block_kind="paragraph", heading_path=heading_case),
        _grouping_row("CP003", 4, block_kind="paragraph", heading_path=heading_case),
    ]
    blocks = [
        _grouping_block(
            "CH001",
            1,
            kind="heading",
            heading_path=heading_case,
            analysis_text="12.3.2 病例叙述",
        ),
        _grouping_block(
            "CP001",
            2,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case paragraph one",
        ),
        _grouping_block(
            "CP002",
            3,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case paragraph two",
        ),
        _grouping_block(
            "CP003",
            4,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case paragraph three",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    case_units = outputs.units_by_route["case"]
    aggregate_units = outputs.units_by_route["aggregate"]

    assert aggregate_units == []
    assert len(case_units) == 1
    assert case_units[0]["source_block_ids"] == ["CP001", "CP002", "CP003"]
    assert case_units[0]["context_block_ids"] == ["CH001"]
    assert _unit_body_text(case_units[0]) == "sample text" * 3


def test_grouping_aggregate_and_case_routes_use_different_grouping_policy() -> None:
    """Aggregate is paragraph-first; case preserves pre-existing merge (not final canonical design)."""
    heading_agg = ["12 临床安全性", "12.3 不良事件概述"]
    heading_case = ["12 临床安全性", "12.3.2 病例叙述"]
    rows = [
        _grouping_row("AH001", 1, block_kind="heading", heading_path=heading_agg),
        _grouping_row("AP001", 2, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("AP002", 3, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("CH001", 4, block_kind="heading", heading_path=heading_case),
        _grouping_row("CP001", 5, block_kind="paragraph", heading_path=heading_case),
        _grouping_row("CP002", 6, block_kind="paragraph", heading_path=heading_case),
    ]
    blocks = [
        _grouping_block(
            "AH001",
            1,
            kind="heading",
            heading_path=heading_agg,
            analysis_text="12.3 不良事件概述",
        ),
        _grouping_block(
            "AP001",
            2,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate one",
        ),
        _grouping_block(
            "AP002",
            3,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate two",
        ),
        _grouping_block(
            "CH001",
            4,
            kind="heading",
            heading_path=heading_case,
            analysis_text="12.3.2 病例叙述",
        ),
        _grouping_block(
            "CP001",
            5,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case one",
        ),
        _grouping_block(
            "CP002",
            6,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case two",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)

    aggregate_units = outputs.units_by_route["aggregate"]
    case_units = outputs.units_by_route["case"]
    assert len(aggregate_units) == 2
    assert aggregate_units[0]["source_block_ids"] == ["AP001"]
    assert aggregate_units[1]["source_block_ids"] == ["AP002"]
    assert len(case_units) == 1
    assert case_units[0]["source_block_ids"] == ["CP001", "CP002"]


def test_grouping_table_text_route_preserves_preexisting_merge_behavior() -> None:
    """Table-route text keeps parent consecutive merge pending route-specific decomposition."""
    heading_table = ["六、临床安全性", "各试验参与者不良事件列表"]
    rows = [
        _grouping_row("TH001", 1, block_kind="heading", heading_path=heading_table),
        _grouping_row("TP001", 2, block_kind="paragraph", heading_path=heading_table),
        _grouping_row("TP002", 3, block_kind="paragraph", heading_path=heading_table),
    ]
    blocks = [
        _grouping_block(
            "TH001",
            1,
            kind="heading",
            heading_path=heading_table,
            analysis_text="各试验参与者不良事件列表",
        ),
        _grouping_block(
            "TP001",
            2,
            kind="paragraph",
            heading_path=heading_table,
            analysis_text="table paragraph one",
        ),
        _grouping_block(
            "TP002",
            3,
            kind="paragraph",
            heading_path=heading_table,
            analysis_text="table paragraph two",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)
    table_units = outputs.units_by_route["table"]
    aggregate_units = outputs.units_by_route["aggregate"]

    assert aggregate_units == []
    assert len(table_units) == 1
    assert table_units[0]["route"] == "table"
    assert table_units[0]["source_block_ids"] == ["TP001", "TP002"]
    assert table_units[0]["context_block_ids"] == ["TH001"]
    assert _unit_body_text(table_units[0]) == "sample text" * 2


def test_grouping_text_route_policy_matrix_aggregate_separate_case_table_merge() -> None:
    """Policy matrix: aggregate separate; case/table preserve pre-existing merge."""
    heading_agg = ["12 临床安全性", "12.3 不良事件概述"]
    heading_case = ["12 临床安全性", "12.3.2 病例叙述"]
    heading_table = ["12 临床安全性", "各试验参与者不良事件列表"]
    rows = [
        _grouping_row("AH001", 1, block_kind="heading", heading_path=heading_agg),
        _grouping_row("AP001", 2, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("AP002", 3, block_kind="paragraph", heading_path=heading_agg),
        _grouping_row("CH001", 4, block_kind="heading", heading_path=heading_case),
        _grouping_row("CP001", 5, block_kind="paragraph", heading_path=heading_case),
        _grouping_row("CP002", 6, block_kind="paragraph", heading_path=heading_case),
        _grouping_row("TH001", 7, block_kind="heading", heading_path=heading_table),
        _grouping_row("TP001", 8, block_kind="paragraph", heading_path=heading_table),
        _grouping_row("TP002", 9, block_kind="paragraph", heading_path=heading_table),
    ]
    blocks = [
        _grouping_block(
            "AH001",
            1,
            kind="heading",
            heading_path=heading_agg,
            analysis_text="12.3 不良事件概述",
        ),
        _grouping_block(
            "AP001",
            2,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate one",
        ),
        _grouping_block(
            "AP002",
            3,
            kind="paragraph",
            heading_path=heading_agg,
            analysis_text="aggregate two",
        ),
        _grouping_block(
            "CH001",
            4,
            kind="heading",
            heading_path=heading_case,
            analysis_text="12.3.2 病例叙述",
        ),
        _grouping_block(
            "CP001",
            5,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case one",
        ),
        _grouping_block(
            "CP002",
            6,
            kind="paragraph",
            heading_path=heading_case,
            analysis_text="case two",
        ),
        _grouping_block(
            "TH001",
            7,
            kind="heading",
            heading_path=heading_table,
            analysis_text="各试验参与者不良事件列表",
        ),
        _grouping_block(
            "TP001",
            8,
            kind="paragraph",
            heading_path=heading_table,
            analysis_text="table one",
        ),
        _grouping_block(
            "TP002",
            9,
            kind="paragraph",
            heading_path=heading_table,
            analysis_text="table two",
        ),
    ]
    outputs = _build_grouping_outputs(rows, blocks)

    aggregate_units = outputs.units_by_route["aggregate"]
    case_units = outputs.units_by_route["case"]
    table_units = outputs.units_by_route["table"]

    assert len(aggregate_units) == 2
    assert aggregate_units[0]["source_block_ids"] == ["AP001"]
    assert aggregate_units[1]["source_block_ids"] == ["AP002"]
    assert len(case_units) == 1
    assert case_units[0]["source_block_ids"] == ["CP001", "CP002"]
    assert len(table_units) == 1
    assert table_units[0]["source_block_ids"] == ["TP001", "TP002"]
