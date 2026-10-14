from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.filter_test_helpers import resolved_filter_job

from tests.clinical_program_fixtures import canonical_clinical_program_fields
from tests.extract_test_helpers import extract_docx_for_test
from steps.filter import extract_zones_from_bundle
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)

TABLE_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_table_001.docx"
)

SAFETY_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "legacy_ib_v1_0"
    / "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15.docx"
)


def _blocks_by_id(bundle) -> dict[str, object]:
    blocks = (
        bundle.front_matter_blocks
        + bundle.content_blocks
        + bundle.table_blocks
        + bundle.format_blocks
    )
    return {block.block_id: block for block in blocks}


def test_table_block_has_heading_path_and_doc_order_between_neighbors() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    by_id = _blocks_by_id(bundle)

    table = by_id["T0001"]
    assert table.kind == "table"
    assert table.heading_path
    assert any("临床安全性" in item for item in table.heading_path)

    caption = by_id["C0010"]
    note = by_id["C0011"]
    assert caption.doc_order_index is not None
    assert table.doc_order_index is not None
    assert note.doc_order_index is not None
    assert caption.doc_order_index < table.doc_order_index < note.doc_order_index


def test_safety_section_neighbors_share_top_level_heading_path() -> None:
    """C0009/C0010/T0001/C0011 use the same top-level heading_path (not meta-only)."""
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    by_id = _blocks_by_id(bundle)

    block_ids = ["C0009", "C0010", "T0001", "C0011"]
    blocks = [by_id[block_id] for block_id in block_ids]
    paths = [block.heading_path for block in blocks]

    assert paths[0] == paths[1] == paths[2] == paths[3]
    assert len(paths[0]) >= 2
    assert any("临床安全性" in item for item in paths[0])
    assert any("6.1" in item for item in paths[0])

    for block in blocks:
        assert isinstance(block.heading_path, list)
        assert block.heading_path
        assert "heading_path" not in (block.meta or {})


def test_prepare_analysis_preserves_doc_order_index_and_heading_path() -> None:
    """Mask/prepare_analysis must carry ordered-block fields into analysis_bundle."""
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    result = prepare_analysis_bundle(
        asdict(bundle),
        profile=None,
        language="zh",
        **canonical_clinical_program_fields(),
    )
    analysis = result.analysis_bundle

    by_id: dict[str, dict] = {}
    for group in ("content_blocks", "table_blocks"):
        for block in analysis.get(group) or []:
            by_id[str(block["block_id"])] = block

    block_ids = ["C0009", "C0010", "C0011", "T0001"]
    paths: list[list[str]] = []
    for block_id in block_ids:
        block = by_id[block_id]
        assert block.get("doc_order_index") is not None
        heading_path = block.get("heading_path")
        assert isinstance(heading_path, list)
        assert heading_path
        assert "heading_path" not in (block.get("meta") or {})
        paths.append(heading_path)

    assert paths[0] == paths[1] == paths[2] == paths[3]
    assert by_id["C0010"]["doc_order_index"] < by_id["T0001"]["doc_order_index"]
    assert by_id["T0001"]["doc_order_index"] < by_id["C0011"]["doc_order_index"]


def test_filter_clinical_safety_zone_includes_table_from_safety_sample() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    analysis = prepare_analysis_bundle(
        asdict(bundle),
        profile=None,
        language="zh",
        **canonical_clinical_program_fields(),
    )
    analysis_bundle = dict(analysis.analysis_bundle)

    result = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    zones_with_t0001 = [
        zone
        for zone in result["matched_zones"]
        if any(block.get("block_id") == "T0001" for block in zone.get("table_blocks") or [])
    ]
    assert len(zones_with_t0001) == 1
    zone = zones_with_t0001[0]
    assert any(block.get("block_id") == "C0009" for block in zone["blocks"])
    t0001 = next(
        block for block in zone["table_blocks"] if block.get("block_id") == "T0001"
    )
    assert t0001.get("doc_order_index") is not None
    assert t0001.get("heading_path")
    assert any("临床安全性" in item for item in t0001["heading_path"])
    for zone in result["matched_zones"]:
        assert isinstance(zone.get("table_blocks"), list)


def test_doc_order_index_unique_and_cross_stream_on_table_sample() -> None:
    bundle = extract_docx_for_test(TABLE_SAMPLE)
    body_blocks = sorted(
        bundle.front_matter_blocks + bundle.content_blocks + bundle.table_blocks,
        key=lambda block: block.doc_order_index if block.doc_order_index is not None else -1,
    )
    indices = [block.doc_order_index for block in body_blocks]
    assert indices
    assert all(index is not None for index in indices)
    assert len(indices) == len(set(indices))
    assert indices == list(range(len(indices)))

    table_blocks = bundle.table_blocks
    assert len(table_blocks) >= 2
    for table in table_blocks:
        assert table.doc_order_index is not None
        assert isinstance(table.heading_path, list)


def test_group_order_unchanged_within_streams() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    for group in (
        bundle.content_blocks,
        bundle.table_blocks,
        bundle.front_matter_blocks,
    ):
        orders = [block.order for block in group]
        if not orders:
            continue
        assert orders == list(range(1, len(orders) + 1))
