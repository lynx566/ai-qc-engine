from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.privacy_safety import (
    PUBLIC_ZONE_MATCH_FORBIDDEN_KEYS,
    walk_forbidden_keys,
)
from steps.filter import (
    extract_zones_from_bundle,
    heading_paths_from_block_manifest,
    to_debug_filter_payload,
    to_public_filter_payload,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.filter_test_helpers import resolved_filter_job


def _legacy_bundle_with_raw_heading_path() -> dict:
    return {
        "doc_id": "doc_legacy_heading_path",
        "file_name": "ib.docx",
        "source_type": "docx",
        "content_blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "order": 1,
                "analysis_text": "6.1 StudyDrug_001",
                "heading_path": ["六、临床安全性", "6.1 VT8802 I期研究"],
                "meta": {
                    "heading_level": 2,
                    "heading_text_stripped": "临床安全性",
                    "raw_text_before_normalize": "6.1 VT8802 raw",
                },
            },
            {
                "block_id": "p1",
                "kind": "paragraph",
                "order": 2,
                "analysis_text": "masked body",
                "heading_path": ["六、临床安全性", "6.1 VT8802 I期研究"],
                "meta": {"raw_rows": [["VT8802"]]},
            },
        ],
        "table_blocks": [],
        "front_matter_blocks": [],
        "format_blocks": [],
    }


def _masked_block_manifest() -> dict:
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_legacy_heading_path",
        "file_hash": (
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_test"},
        "blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "order": 1,
                "heading_path": ["六、临床安全性", "6.1 StudyDrug_001"],
                "analysis_text": "6.1 StudyDrug_001",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "h1",
                },
            },
            {
                "block_id": "p1",
                "kind": "paragraph",
                "order": 2,
                "heading_path": ["六、临床安全性", "6.1 StudyDrug_001"],
                "analysis_text": "masked body",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_test",
                    "block_id": "p1",
                },
            },
        ],
    }


def test_public_export_does_not_copy_extract_heading_path() -> None:
    raw = extract_zones_from_bundle(
        _legacy_bundle_with_raw_heading_path(),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    public = to_public_filter_payload(raw)
    block = public["matched_zones"][0]["blocks"][0]
    assert "heading_path" not in block
    assert "VT8802" not in json.dumps(public, ensure_ascii=False)


def test_public_export_heading_path_from_block_manifest() -> None:
    raw = extract_zones_from_bundle(
        _legacy_bundle_with_raw_heading_path(),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    manifest = _masked_block_manifest()
    public = to_public_filter_payload(raw, block_manifest=manifest)
    block = public["matched_zones"][0]["blocks"][0]
    assert block["heading_path"] == ["六、临床安全性", "6.1 StudyDrug_001"]
    assert "VT8802" not in json.dumps(block["heading_path"], ensure_ascii=False)


def test_public_export_strips_sensitive_meta_and_match_fields() -> None:
    raw = extract_zones_from_bundle(
        _legacy_bundle_with_raw_heading_path(),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    public = to_public_filter_payload(raw, block_manifest=_masked_block_manifest())
    block = public["matched_zones"][0]["blocks"][0]
    assert block["meta"] == {"heading_level": 2}
    match = public["matched_zones"][0]["match"]
    assert "matched_heading_text" not in match
    assert "matched_heading_text_stripped" not in match
    assert match.get("matched_heading_analysis_text") == "6.1 StudyDrug_001"
    assert "text" not in block
    hits = walk_forbidden_keys(
        public,
        PUBLIC_ZONE_MATCH_FORBIDDEN_KEYS,
        root_label="zone_match_bundle",
    )
    assert hits == []


def test_debug_export_retains_original_sidecars() -> None:
    raw = extract_zones_from_bundle(
        _legacy_bundle_with_raw_heading_path(),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    debug = to_debug_filter_payload(
        raw,
        mask_result={
            "masked_blocks": [
                {
                    "block_id": "h1",
                    "original_text": "6.1 VT8802 raw heading",
                    "masked_text": "6.1 StudyDrug_001",
                }
            ]
        },
    )
    block = debug["matched_zones"][0]["blocks"][0]
    assert block["heading_path"] == ["六、临床安全性", "6.1 VT8802 I期研究"]
    assert block["meta"]["raw_text_before_normalize"] == "6.1 VT8802 raw"
    assert "original_text" in block


def test_heading_paths_from_block_manifest_index() -> None:
    paths = heading_paths_from_block_manifest(_masked_block_manifest())
    assert paths["p1"] == ["六、临床安全性", "6.1 StudyDrug_001"]
