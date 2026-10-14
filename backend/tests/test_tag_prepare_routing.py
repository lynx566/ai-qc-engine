from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.routing import infer_route_from_heading
from tests.route_test_fixtures import _route_units
from tests.routing_test_helpers import build_current_route_artifacts_from_inputs

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _minimal_doc_meta(*, doc_id: str = "doc_test") -> dict:
    return {
        "doc_meta_bundle_id": "doc_meta_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "summary": {"doc_type": "IB", "study_drug": "StudyDrug_001"},
    }


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
        "coverage_bundle_id": "coverage_route_test",
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


def _table_block(
    block_id: str,
    order: int,
    *,
    heading_path: list[str] | None = None,
    analysis_text: str = "A | B\n1 | 2",
) -> dict:
    return {
        "block_id": block_id,
        "kind": "table",
        "order": order,
        "heading_path": heading_path or [],
        "analysis_text": analysis_text,
        "text_ref": {
            "analysis_bundle_id": "prepare_analysis_test",
            "block_id": block_id,
        },
    }


def _block_manifest(*, blocks: list[dict], table_blocks: list[dict] | None = None) -> dict:
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": blocks,
        "table_blocks": table_blocks or [],
    }


def _build_routed(**kwargs):
    return _route_units(
        coverage=kwargs["coverage"],
        manifest=kwargs["manifest"],
    )


@pytest.mark.parametrize(
    ("heading_path", "block_kind", "expected_route", "expected_term"),
    [
        (("12 临床安全性", "12.3 不良事件汇总表"), "paragraph", "table", "汇总表"),
        (("12 临床安全性", "行列表"), "paragraph", "table", "行列表"),
        (("12 临床安全性", "测量值列表"), "paragraph", "table", "测量值列表"),
        (("12 临床安全性", "12.3.2 病例叙述"), "paragraph", "case", "病例叙述"),
        (("12 临床安全性", "死亡试验参与者"), "paragraph", "case", "死亡试验参与者"),
        (("12 临床安全性", "12.3 不良事件概述"), "paragraph", "aggregate", "不良事件"),
        (("12 临床安全性", "各实验室参数的评价"), "paragraph", "aggregate", "各实验室参数的评价"),
        (("12 临床安全性", "生命体征"), "paragraph", "aggregate", "生命体征"),
        (("12 临床安全性", "体格检查"), "paragraph", "aggregate", "体格检查"),
    ],
)
def test_infer_route_from_heading(
    heading_path: tuple[str, ...],
    block_kind: str,
    expected_route: str,
    expected_term: str,
) -> None:
    decision = infer_route_from_heading(
        heading_path=heading_path,
        block_kind=block_kind,
    )
    assert decision.route == expected_route
    assert expected_term in decision.route_matched_terms


def test_table_route_priority_over_case_when_both_terms_present() -> None:
    decision = infer_route_from_heading(
        heading_path=("12 临床安全性", "各患者的个例实验室测量值列表"),
        block_kind="paragraph",
    )
    assert decision.route == "table"
    assert "列表" in decision.route_matched_terms
    assert "个例" not in decision.route_matched_terms




def test_table_caption_and_note_join_table_unit_not_aggregate() -> None:
    heading = ["12 临床安全性", "12.3 不良事件"]
    coverage = _coverage_bundle(
        _coverage_row("C0009", 8, heading_path=heading),
        _coverage_row("C0010", 9, block_kind="table_caption", heading_path=heading),
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
        _coverage_row("C0011", 11, block_kind="table_note", heading_path=heading),
    )
    manifest = _block_manifest(
        blocks=[
            _block("C0009", 8, heading_path=heading, analysis_text="aggregate body"),
            _block(
                "C0010",
                9,
                kind="table_caption",
                heading_path=heading,
                analysis_text="表1 汇总",
            ),
            _block(
                "C0011",
                11,
                kind="table_note",
                heading_path=heading,
                analysis_text="注：说明",
            ),
        ],
        table_blocks=[_table_block("T0001", 10, heading_path=heading)],
    )
    routed = _build_routed(coverage=coverage, manifest=manifest)

    aggregate_block_ids = {
        block_id
        for unit in routed.units_by_route["aggregate"]
        for block_id in unit.get("source_block_ids") or []
    }
    assert aggregate_block_ids == {"C0009"}
    assert "C0010" not in aggregate_block_ids
    assert "C0011" not in aggregate_block_ids

    table_unit = routed.units_by_route["table"][0]
    roles = {component["component_role"] for component in table_unit["components"]}
    assert roles == {"caption", "table_body", "note"}
    assert table_unit["source_block_ids"] == ["C0010", "C0011"]
    assert table_unit["source_table_ids"] == ["T0001"]
    assert table_unit["component_status"] == {"has_caption": True, "has_note": True}
    assert "all_source_block_ids" not in table_unit
    assert table_unit["all_source_refs"] == [
        {"ref_type": "block", "ref_id": "C0010", "block_kind": "table_caption"},
        {"ref_type": "table", "ref_id": "T0001"},
        {"ref_type": "block", "ref_id": "C0011", "block_kind": "table_note"},
    ]








def test_infer_route_matched_terms_uses_route_basis_token() -> None:
    decision = infer_route_from_heading(
        heading_path=("12 临床安全性", "12.3 不良事件概述"),
        block_kind="paragraph",
        zone_key="ib_clinical_safety_zh",
    )
    assert decision.route == "aggregate"
    assert decision.route_basis == "route_matched_terms"
    assert "不良事件" in decision.route_matched_terms


def test_default_aggregate_route_basis_uses_selected_zone_label() -> None:
    decision = infer_route_from_heading(
        heading_path=("12 临床安全性", "6.1 StudyDrug_001"),
        block_kind="paragraph",
        zone_key="ib_clinical_safety_zh",
    )
    assert decision.route == "aggregate"
    assert decision.route_basis == "selected_zone_default_text"
    assert decision.route_matched_terms == ()


def test_default_aggregate_route_basis_is_zone_key_driven_not_module_specific() -> None:
    decision = infer_route_from_heading(
        heading_path=("7 疗效", "6.1 StudyDrug_001"),
        block_kind="paragraph",
        zone_key="ib_overview_zh",
    )
    assert decision.route == "aggregate"
    assert decision.route_basis == "selected_zone_default_text"
    assert decision.route_matched_terms == ()


def test_px2471_reference_drug_aggregate_not_excluded_at_tag_prepare() -> None:
    heading = ["12 临床安全性", "12.3 PX-2471 同类药安全性概述"]
    coverage = _coverage_bundle(
        _coverage_row("C0400", 40, heading_path=heading),
    )
    manifest = _block_manifest(
        blocks=[
            _block(
                "C0400",
                40,
                heading_path=heading,
                analysis_text="PX-2471 与 StudyDrug_001 对比分析。",
            ),
        ],
    )
    routed = _build_routed(coverage=coverage, manifest=manifest)
    aggregate_units = routed.units_by_route["aggregate"]
    assert len(aggregate_units) == 1
    assert aggregate_units[0]["source_block_ids"] == ["C0400"]
    assert aggregate_units[0]["sentences"] == [
        {
            "sentence_id": "C0400:S001",
            "text": "sample text",
            "source_block_id": "C0400",
        }
    ]
    assert "candidate_text" not in aggregate_units[0]








def test_coverage_row_uses_block_kind_not_evidence_kind() -> None:
    row = _coverage_row("C0001", 1, block_kind="paragraph")
    assert "block_kind" in row
    assert "evidence_kind" not in row


def test_table_route_bundle_structure_and_privacy() -> None:
    heading = ["六、临床安全性", "6.1 StudyDrug_001 I期研究"]
    coverage = _coverage_bundle(
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
    )
    manifest = _block_manifest(
        blocks=[],
        table_blocks=[
            _table_block(
                "T0001",
                10,
                heading_path=heading,
                analysis_text="不良反应 | DoseLevel_001",
            ),
        ],
    )
    artifacts = build_current_route_artifacts_from_inputs(
        coverage_bundle=coverage,
        block_manifest=manifest,
        doc_meta_bundle=_minimal_doc_meta(),
    )
    table_bundle = artifacts["routed_bundles"]["table"]
    table_unit = table_bundle["units"][0]

    assert table_bundle["route"] == "table"
    assert table_unit["route"] == "table"
    assert table_unit["unit_kind"] == "table_unit"
    assert table_unit["source_table_ids"] == ["T0001"]
    assert "T0001" not in table_unit["source_block_ids"]
    assert "all_source_block_ids" not in table_unit
    assert table_unit["all_source_refs"] == [{"ref_type": "table", "ref_id": "T0001"}]
    assert table_unit["component_status"] == {"has_caption": False, "has_note": False}
    assert "VT8802" not in str(table_unit["heading_path"])
    assert "StudyDrug_001" in str(table_unit["heading_path"])

    body = next(
        component
        for component in table_unit["components"]
        if component["component_role"] == "table_body"
    )
    assert body["table_shape"] == {"row_count": None, "column_count": None}
    assert body["header_rows"] == []
    assert body["rows"] == []

    manifest_doc = artifacts["routing_manifest"]
    table_manifest_unit = next(
        unit for unit in manifest_doc["units"] if unit.get("unit_id") == "TTU0001"
    )
    assert table_manifest_unit["component_roles"] == ["table_body"]
    assert table_manifest_unit["component_status"] == {
        "has_caption": False,
        "has_note": False,
    }
    assert "all_source_block_ids" not in table_manifest_unit
    assert "不良反应" not in str(manifest_doc)

def test_caption_not_attached_across_section_heading() -> None:
    """A caption separated from the table by a same-level heading must not be attached."""
    heading_a = ["12 临床安全性", "12.1 研究A"]
    heading_b = ["12 临床安全性", "12.2 研究B"]
    # Caption C0010 belongs to heading_a; table T0002 belongs to heading_b.
    # Between them is heading block C0014 which starts 12.2 (same depth).
    coverage = _coverage_bundle(
        _coverage_row("C0010", 10, block_kind="table_caption", heading_path=heading_a),
        _coverage_row("T0001", 11, block_kind="table", heading_path=heading_a),
        _coverage_row("T0002", 20, block_kind="table", heading_path=heading_b),
    )
    heading_block = {
        "block_id": "C0014",
        "kind": "heading",
        "order": 14,
        "heading_level": 2,
        "heading_path": heading_b,
        "analysis_text": "12.2 研究B",
        "text_ref": {"analysis_bundle_id": "prepare_analysis_test", "block_id": "C0014"},
    }
    manifest = _block_manifest(
        blocks=[
            _block("C0010", 10, kind="table_caption", heading_path=heading_a, analysis_text="表A"),
            heading_block,
        ],
        table_blocks=[
            _table_block("T0001", 11, heading_path=heading_a),
            _table_block("T0002", 20, heading_path=heading_b),
        ],
    )
    routed = _build_routed(coverage=coverage, manifest=manifest)
    table_units = routed.units_by_route["table"]

    ttu_t0001 = next(u for u in table_units if u["source_table_ids"] == ["T0001"])
    ttu_t0002 = next(u for u in table_units if u["source_table_ids"] == ["T0002"])

    # C0010 attaches to T0001 (same section)
    assert ttu_t0001["source_block_ids"] == ["C0010"]
    assert ttu_t0001["component_status"]["has_caption"] is True

    # T0002 must NOT pick up C0010 — it is in a different section
    assert ttu_t0002["source_block_ids"] == []
    assert ttu_t0002["component_status"]["has_caption"] is False


def test_note_not_attached_across_section_heading() -> None:
    """A note separated from the table by a same-level heading must not be attached."""
    heading_a = ["12 临床安全性", "12.1 研究A"]
    heading_b = ["12 临床安全性", "12.2 研究B"]
    coverage = _coverage_bundle(
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading_a),
        _coverage_row("T0002", 20, block_kind="table", heading_path=heading_b),
        _coverage_row("C0025", 25, block_kind="table_note", heading_path=heading_b),
    )
    heading_block = {
        "block_id": "C0015",
        "kind": "heading",
        "order": 15,
        "heading_level": 2,
        "heading_path": heading_b,
        "analysis_text": "12.2 研究B",
        "text_ref": {"analysis_bundle_id": "prepare_analysis_test", "block_id": "C0015"},
    }
    manifest = _block_manifest(
        blocks=[
            heading_block,
            _block("C0025", 25, kind="table_note", heading_path=heading_b, analysis_text="注"),
        ],
        table_blocks=[
            _table_block("T0001", 10, heading_path=heading_a),
            _table_block("T0002", 20, heading_path=heading_b),
        ],
    )
    routed = _build_routed(coverage=coverage, manifest=manifest)
    table_units = routed.units_by_route["table"]

    ttu_t0001 = next(u for u in table_units if u["source_table_ids"] == ["T0001"])
    ttu_t0002 = next(u for u in table_units if u["source_table_ids"] == ["T0002"])

    # T0001 must NOT pick up C0025 — heading 12.2 intervenes
    assert ttu_t0001["component_status"]["has_note"] is False

    # C0025 attaches to T0002 (same section, no intervening heading)
    assert ttu_t0002["source_block_ids"] == ["C0025"]
    assert ttu_t0002["component_status"]["has_note"] is True


def test_table_body_structured_rows_available_false_when_no_raw_rows() -> None:
    heading = ["12 临床安全性"]
    coverage = _coverage_bundle(
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
    )
    manifest = _block_manifest(
        blocks=[],
        table_blocks=[_table_block("T0001", 10, heading_path=heading)],
    )
    routed = _build_routed(coverage=coverage, manifest=manifest)
    table_unit = routed.units_by_route["table"][0]
    body = next(c for c in table_unit["components"] if c["component_role"] == "table_body")
    assert body["structured_rows_available"] is False
    assert body["rows"] == []


def test_table_body_structured_rows_available_true_when_raw_rows_present() -> None:
    heading = ["12 临床安全性"]
    coverage = _coverage_bundle(
        _coverage_row("T0001", 10, block_kind="table", heading_path=heading),
    )
    table_block_with_raw_rows: dict = {
        "block_id": "T0001",
        "kind": "table",
        "order": 10,
        "heading_path": heading,
        "analysis_text": "A | B\n1 | 2",
        "meta": {
            "row_count": 2,
            "column_count": 2,
            "raw_rows": [["A", "B"], ["1", "2"]],
        },
        "text_ref": {"analysis_bundle_id": "prepare_analysis_test", "block_id": "T0001"},
    }
    manifest = _block_manifest(
        blocks=[],
        table_blocks=[table_block_with_raw_rows],
    )
    routed = _build_routed(coverage=coverage, manifest=manifest)
    table_unit = routed.units_by_route["table"][0]
    body = next(c for c in table_unit["components"] if c["component_role"] == "table_body")
    assert body["structured_rows_available"] is True
    assert body["rows"] == [["A", "B"], ["1", "2"]]
    assert body["table_shape"] == {"row_count": 2, "column_count": 2}
