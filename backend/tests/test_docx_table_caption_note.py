from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from core.document.docx.handlers import (
    extract_docx_table_label,
    is_docx_table_caption_candidate,
    is_docx_table_note_candidate,
)
from steps.filter import extract_zones_from_bundle
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.block_manifest_test_helpers import build_block_manifest
from tests.clinical_program_fixtures import canonical_clinical_program_fields
from tests.extract_test_helpers import extract_docx_for_test
from tests.filter_test_helpers import build_test_coverage_bundle, resolved_filter_job
from tests.route_test_fixtures import _route_units

SAFETY_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "legacy_ib_v1_0"
    / "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15.docx"
)

VT8802_V13_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "ib_v1_3"
    / "VT8802 艾美妥珠单抗研究者手册 V1.3 2024.03.15.docx"
)

ZONE_KEY = "ib_clinical_safety_zh"
FILTER_RUN_ID = "filter_test_table_caption_note"


def _blocks_by_id(bundle) -> dict[str, object]:
    blocks = (
        bundle.front_matter_blocks
        + bundle.content_blocks
        + bundle.table_blocks
        + bundle.format_blocks
    )
    return {block.block_id: block for block in blocks}


def _find_table_caption(bundle, label: str):
    matches = [
        block
        for block in bundle.content_blocks
        if block.kind == "table_caption"
        and (block.meta or {}).get("table_label") == label
    ]
    assert len(matches) == 1, f"expected one table_caption for {label!r}, got {len(matches)}"
    return matches[0]


def _find_paragraphs_with_table_refs(bundle, refs: list[str]) -> list[object]:
    return [
        block
        for block in bundle.content_blocks
        if block.kind == "paragraph"
        and (block.meta or {}).get("table_ref_candidates") == refs
    ]


def _find_table_notes(bundle) -> list[object]:
    return [block for block in bundle.content_blocks if block.kind == "table_note"]


def _table_blocks(bundle) -> list[object]:
    return [block for block in bundle.table_blocks if block.kind == "table"]


def test_extract_meta_omits_empty_noise_fields() -> None:
    """Extract bundle meta should omit null-equivalent keys on non-heading blocks."""
    bundle = extract_docx_for_test(VT8802_V13_SAMPLE)
    by_id = _blocks_by_id(bundle)

    for block in (
        bundle.front_matter_blocks
        + bundle.content_blocks
        + bundle.table_blocks
        + bundle.format_blocks
    ):
        meta = block.meta or {}
        if block.kind != "heading":
            assert "heading_level" not in meta, block.block_id
        assert "table_ref_candidates" not in meta or meta["table_ref_candidates"], block.block_id

    summary = by_id["C0003"]
    assert summary.kind == "heading"
    assert summary.normalized_text == "摘要"
    assert "heading_text_stripped" not in summary.meta

    numbered = next(
        (
            block
            for block in bundle.content_blocks
            if block.kind == "heading"
            and (block.meta or {}).get("heading_text_stripped") == "VT8802 I期研究"
        ),
        None,
    )
    assert numbered is not None
    assert numbered.meta.get("heading_level") == 2

    narrative = next(
        (
            block
            for block in bundle.content_blocks
            if block.kind == "paragraph"
            and (block.meta or {}).get("table_ref_candidates") == ["表1"]
        ),
        None,
    )
    assert narrative is not None
    assert "heading_level" not in narrative.meta
    assert narrative.meta.get("table_ref_candidates") == ["表1"]


def test_table_caption_candidate_positive_and_negative() -> None:
    assert is_docx_table_caption_candidate(
        "表1 VT8802 I期试验期间出现的不良反应情况汇总"
    )
    assert is_docx_table_caption_candidate(
        "Table 1 Summary of adverse reactions"
    )
    assert not is_docx_table_caption_candidate("如表1所示，发生率较高。")
    assert not is_docx_table_caption_candidate("表1显示，试验参与者共20例。")
    assert not is_docx_table_caption_candidate("见表2。")


def test_table_note_candidate_positive() -> None:
    assert is_docx_table_note_candidate("注：数据截至2023年11月30日。")
    assert is_docx_table_note_candidate("Note: Data cut-off 2023-11-30.")


def test_extract_docx_table_label() -> None:
    assert (
        extract_docx_table_label("表1 VT8802 I期试验期间出现的不良反应情况汇总")
        == "表1"
    )
    assert (
        extract_docx_table_label("表2 OOJ-VT8802-02研究中不良反应发生情况汇总")
        == "表2"
    )
    assert (
        extract_docx_table_label("表 2：OOJ-VT8802-02研究中不良反应发生情况汇总")
        == "表2"
    )
    assert extract_docx_table_label("表三 不良反应汇总") == "表三"
    assert (
        extract_docx_table_label("Table 1 Summary of adverse reactions")
        == "Table 1"
    )
    assert extract_docx_table_label("Table 3 Adverse events") == "Table 3"
    assert extract_docx_table_label("如表1所示，发生率较高。") is None


def test_v13_sample_classifies_captions_notes_and_preserves_refs() -> None:
    bundle = extract_docx_for_test(VT8802_V13_SAMPLE)

    for label in ("表1", "表2", "表3", "表4"):
        block = _find_table_caption(bundle, label)
        assert block.kind == "table_caption"
        assert (block.meta or {}).get("table_label") == label
        assert "table_ref_candidates" not in (block.meta or {})

    table3_notes = [
        note
        for note in _find_table_notes(bundle)
        if "OOJ-VT8802-02" in note.normalized_text
        and "进行中" in note.normalized_text
    ]
    assert len(table3_notes) == 1
    table3_note = table3_notes[0]
    assert table3_note.kind == "table_note"
    assert "table_ref_candidates" not in (table3_note.meta or {})
    assert "table_label" not in (table3_note.meta or {})

    tables = _table_blocks(bundle)
    assert len(tables) >= 3
    assert all(block.kind == "table" for block in tables)

    for refs in (["表1"], ["表2"], ["表3"]):
        matches = _find_paragraphs_with_table_refs(bundle, refs)
        assert len(matches) >= 1, refs
        for block in matches:
            assert block.kind == "paragraph"
            assert (block.meta or {}).get("table_ref_candidates") == refs


def test_caption_and_note_inherit_heading_path_without_updating_stack() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    by_id = _blocks_by_id(bundle)

    caption = by_id["C0010"]
    table = by_id["T0001"]
    note = by_id["C0011"]
    narrative = by_id["C0009"]

    assert caption.kind == "table_caption"
    assert note.kind == "table_note"
    assert caption.heading_path == table.heading_path == note.heading_path
    assert caption.heading_path == narrative.heading_path
    assert "table_label" in (caption.meta or {})
    assert "table_ref_candidates" not in (caption.meta or {})
    assert "table_ref_candidates" not in (note.meta or {})


def test_table_caption_note_excluded_from_narrative_and_table_units() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    analysis = prepare_analysis_bundle(
        asdict(bundle),
        profile=None,
        language="zh",
        **canonical_clinical_program_fields(),
    )
    analysis_bundle = dict(analysis.analysis_bundle)
    analysis_bundle["analysis_bundle_id"] = "prepare_analysis_test_caption_note"

    block_manifest = build_block_manifest(analysis_bundle)
    zone_result = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    coverage_bundle = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    coverage_by_id = {
        row["block_id"]: row for row in coverage_bundle.get("coverage") or []
    }
    assert coverage_by_id["C0010"]["block_kind"] == "table_caption"
    assert coverage_by_id["C0011"]["block_kind"] == "table_note"
    assert coverage_by_id["T0001"]["block_kind"] == "table"

    routed = _route_units(coverage=coverage_bundle, manifest=block_manifest)

    aggregate_block_ids = {
        block_id
        for unit in routed.units_by_route["aggregate"]
        for block_id in unit.get("source_block_ids") or []
    }
    table_unit_ids = [
        (unit.get("source_table_ids") or [None])[0]
        for unit in routed.units_by_route["table"]
        if unit.get("unit_kind") == "table_unit"
    ]

    assert "C0010" not in aggregate_block_ids
    assert "C0011" not in aggregate_block_ids
    assert "T0001" in table_unit_ids
    assert "C0010" not in table_unit_ids
    assert "C0011" not in table_unit_ids
