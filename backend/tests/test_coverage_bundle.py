from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.coverage_bundle import (
    COVERAGE_BUNDLE_FILENAME,
    EXCLUDE_REASON_NOT_MATCHED,
    assert_coverage_bundle_safe,
    build_coverage_bundle,
    build_coverage_bundle_id,
)
from steps.filter import (
    INCLUDE_REASON_MATCHED_ZONE,
    derive_block_selection_coverage,
)
from tests.filter_test_helpers import build_test_coverage_bundle

_FORBIDDEN_SUBSTRINGS = (
    "analysis_text",
    "normalized_text",
    "span_map",
    "source_ref",
    "document_meta",
    "privacy_transforms",
    "sentences",
    "matched_heading_text",
)

FILTER_RUN_ID = "filter_20260607_220638_ib_clinical_safety_zh"
ZONE_KEY = "ib_clinical_safety_zh"

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _block_by_id(coverage: list[dict], block_id: str) -> dict:
    for row in coverage:
        if row["block_id"] == block_id:
            return row
    raise AssertionError(f"missing coverage row for {block_id!r}")


def _minimal_block_manifest() -> dict:
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "heading_path": [],
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0001",
                },
            },
            {
                "block_id": "C0009",
                "kind": "paragraph",
                "order": 9,
                "heading_path": ["六、临床安全性", "6.1 StudyDrug_001"],
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0009",
                },
            },
        ],
    }


def _minimal_zone_result(*, included_block_ids: set[str]) -> dict:
    return {
        "matched_zones": [
            {
                "zone_id": "Z0001",
                "match": {
                    "match_type": "heading",
                    "matched_term": "安全性",
                    "matched_heading_block_id": "C0007",
                    "matched_heading_text": "六、临床安全性",
                },
                "blocks": [
                    {"block_id": block_id, "kind": "paragraph"}
                    for block_id in sorted(included_block_ids)
                ],
            }
        ],
    }


def test_build_coverage_bundle_id() -> None:
    assert build_coverage_bundle_id(filter_run_id=FILTER_RUN_ID) == (
        f"coverage_{FILTER_RUN_ID}"
    )


def test_derive_block_selection_coverage_minimal_included_and_excluded() -> None:
    block_manifest = _minimal_block_manifest()
    zone_result = _minimal_zone_result(included_block_ids={"C0009"})
    coverage = derive_block_selection_coverage(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
    )

    assert len(coverage) == 2

    included = _block_by_id(coverage, "C0009")
    assert included["selected_by_filter"] is True
    assert included["include_reason"] == INCLUDE_REASON_MATCHED_ZONE
    assert included["exclude_reason"] is None
    assert included["zone_match"] == {
        "zone_id": "Z0001",
        "match_type": "heading",
        "matched_block_id": "C0007",
        "matched_terms": ["安全性"],
    }
    assert included["selected_sentence_ids"] == []
    assert included["text_ref"]["analysis_bundle_id"] == "prepare_analysis_test"
    assert included["text_ref"]["block_id"] == "C0009"

    excluded = _block_by_id(coverage, "C0001")
    assert excluded["selected_by_filter"] is False
    assert excluded["include_reason"] is None
    assert excluded["exclude_reason"] == EXCLUDE_REASON_NOT_MATCHED
    assert excluded["zone_match"] is None


def test_build_coverage_bundle_minimal_included_and_excluded() -> None:
    block_manifest = _minimal_block_manifest()
    zone_result = _minimal_zone_result(included_block_ids={"C0009"})
    result = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    assert len(result["coverage"]) == 2
    assert result["coverage_bundle_id"] == f"coverage_{FILTER_RUN_ID}"
    assert result["zone_key"] == ZONE_KEY

    included = _block_by_id(result["coverage"], "C0009")
    assert included["selected_by_filter"] is True
    assert included["include_reason"] == INCLUDE_REASON_MATCHED_ZONE

    excluded = _block_by_id(result["coverage"], "C0001")
    assert excluded["selected_by_filter"] is False
    assert excluded["exclude_reason"] == EXCLUDE_REASON_NOT_MATCHED

    assert result["summary"] == {
        "total_blocks": 2,
        "selected_blocks": 1,
        "excluded_blocks": 1,
    }

    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized
    assert_coverage_bundle_safe(result)


def test_build_coverage_bundle_serializes_prederived_rows_only() -> None:
    block_manifest = _minimal_block_manifest()
    prederived = [
        {
            "block_id": "C0001",
            "block_kind": "paragraph",
            "order": 1,
            "doc_order_index": None,
            "heading_path": [],
            "selected_by_filter": False,
            "include_reason": None,
            "exclude_reason": EXCLUDE_REASON_NOT_MATCHED,
            "zone_match": None,
            "zone_ids": [],
            "selected_sentence_ids": [],
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": "C0001",
            },
        }
    ]
    result = build_coverage_bundle(
        block_manifest=block_manifest,
        coverage=prederived,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )
    assert result["coverage"] == prederived
    assert result["summary"]["total_blocks"] == 1
    assert result["summary"]["selected_blocks"] == 0


def test_coverage_bundle_has_no_checked_status_fields() -> None:
    block_manifest = _minimal_block_manifest()
    zone_result = _minimal_zone_result(included_block_ids={"C0009"})
    result = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )
    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in ("checked", "not_checked", "reviewed", "unreviewed"):
        assert forbidden not in serialized


def test_build_coverage_bundle_includes_table_rows_with_block_kind() -> None:
    block_manifest = _minimal_block_manifest()
    block_manifest["table_blocks"] = [
        {
            "block_id": "T0001",
            "kind": "table",
            "order": 1,
            "doc_order_index": 10,
            "heading_path": ["六、临床安全性", "6.1"],
            "text": "table body",
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": "T0001",
            },
            "meta": {"row_count": 2, "column_count": 3},
        },
        {
            "block_id": "T0002",
            "kind": "table",
            "order": 2,
            "doc_order_index": 20,
            "heading_path": [],
            "text": "outside",
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": "T0002",
            },
            "meta": {"row_count": 1, "column_count": 1},
        },
    ]
    zone_result = _minimal_zone_result(included_block_ids={"C0009"})
    zone_result["matched_zones"][0]["table_blocks"] = [
        {"block_id": "T0001", "kind": "table"},
    ]

    result = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    assert len(result["coverage"]) == 4
    included_table = _block_by_id(result["coverage"], "T0001")
    excluded_table = _block_by_id(result["coverage"], "T0002")
    assert included_table["block_kind"] == "table"
    assert included_table["selected_by_filter"] is True
    assert included_table["zone_ids"] == ["Z0001"]
    assert excluded_table["selected_by_filter"] is False

    narrative = _block_by_id(result["coverage"], "C0009")
    assert narrative["block_kind"] == "paragraph"
    assert "evidence_kind" not in narrative


def test_coverage_block_kind_matches_block_manifest_kind() -> None:
    block_manifest = _minimal_block_manifest()
    block_manifest["blocks"].extend(
        [
            {
                "block_id": "C0010",
                "kind": "table_caption",
                "order": 10,
                "heading_path": [],
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0010",
                },
            },
            {
                "block_id": "C0011",
                "kind": "heading",
                "order": 11,
                "heading_path": ["Section"],
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "C0011",
                },
            },
        ]
    )
    zone_result = _minimal_zone_result(included_block_ids={"C0009", "C0010", "C0011"})

    result = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    assert _block_by_id(result["coverage"], "C0010")["block_kind"] == "table_caption"
    assert _block_by_id(result["coverage"], "C0011")["block_kind"] == "heading"
    assert _block_by_id(result["coverage"], "C0009")["block_kind"] == "paragraph"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "evidence_kind" not in serialized


def test_build_coverage_bundle_covers_all_block_manifest_blocks() -> None:
    block_manifest = _minimal_block_manifest()
    block_manifest["blocks"].insert(
        1,
        {
            "block_id": "C0007",
            "kind": "heading",
            "order": 7,
            "heading_path": ["Clinical Safety"],
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": "C0007",
            },
        },
    )
    block_manifest["table_blocks"] = [
        {
            "block_id": "T0001",
            "kind": "table",
            "order": 10,
            "doc_order_index": 10,
            "heading_path": ["Clinical Safety", "6.1 Safety Results"],
            "text": "adverse event table",
            "text_ref": {
                "analysis_bundle_id": "prepare_analysis_test",
                "block_id": "T0001",
            },
            "meta": {"row_count": 1, "column_count": 1},
        }
    ]
    zone_result = _minimal_zone_result(included_block_ids={"C0007", "C0009"})
    zone_result["matched_zones"][0]["table_blocks"] = [
        {"block_id": "T0001", "kind": "table"}
    ]

    result = build_test_coverage_bundle(
        block_manifest=block_manifest,
        public_filter_result=zone_result,
        zone_key=ZONE_KEY,
        filter_run_id=FILTER_RUN_ID,
    )

    assert len(result["coverage"]) == len(block_manifest["blocks"]) + len(
        block_manifest.get("table_blocks") or []
    )
    assert result["block_manifest_ref"]["block_manifest_id"] == block_manifest["block_manifest_id"]
    assert result["analysis_bundle_ref"]["analysis_bundle_id"] == (
        block_manifest["analysis_bundle_ref"]["analysis_bundle_id"]
    )

    c0009 = _block_by_id(result["coverage"], "C0009")
    assert c0009["selected_by_filter"] is True
    assert c0009["include_reason"] == INCLUDE_REASON_MATCHED_ZONE
    table = _block_by_id(result["coverage"], "T0001")
    assert table["selected_by_filter"] is True
    assert table["heading_path"] == ["Clinical Safety", "6.1 Safety Results"]
    source_c0009 = next(
        block for block in block_manifest["blocks"] if block["block_id"] == "C0009"
    )
    assert c0009["heading_path"] == source_c0009["heading_path"]

    c0001 = _block_by_id(result["coverage"], "C0001")
    assert c0001["selected_by_filter"] is False
    assert c0001["exclude_reason"] == EXCLUDE_REASON_NOT_MATCHED

    selected = sum(row["selected_by_filter"] for row in result["coverage"])
    assert selected > 0
    assert result["summary"] == {
        "total_blocks": len(result["coverage"]),
        "selected_blocks": selected,
        "excluded_blocks": len(result["coverage"]) - selected,
    }

    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized
    assert_coverage_bundle_safe(result)


def test_coverage_bundle_filename_constant() -> None:
    assert COVERAGE_BUNDLE_FILENAME == "coverage_bundle.json"
