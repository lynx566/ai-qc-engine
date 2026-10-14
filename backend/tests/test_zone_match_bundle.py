from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.privacy_safety import assert_zone_match_public_safe
from artifacts.zone_match_bundle import (
    ZONE_MATCH_BUNDLE_DEBUG_FILENAME,
    ZONE_MATCH_BUNDLE_FILENAME,
    assert_zone_match_bundle_safe,
    build_zone_match_bundle,
)
from steps.filter import extract_zones_from_bundle, to_public_filter_payload
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.filter_test_helpers import resolved_filter_job


def test_zone_match_bundle_filename_owned_by_artifacts() -> None:
    assert ZONE_MATCH_BUNDLE_FILENAME == "zone_match_bundle.json"
    assert ZONE_MATCH_BUNDLE_DEBUG_FILENAME == "zone_match_bundle.debug.json"


def test_build_zone_match_bundle_preserves_public_payload() -> None:
    raw = extract_zones_from_bundle(
        {
            "doc_id": "doc_test",
            "file_name": "ib.docx",
            "source_type": "docx",
            "content_blocks": [
                {
                    "block_id": "h1",
                    "kind": "heading",
                    "analysis_text": "六、临床安全性",
                    "meta": {
                        "heading_level": 1,
                        "heading_text_stripped": "临床安全性",
                    },
                },
            ],
        },
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    public_payload = to_public_filter_payload(raw)
    bundle = build_zone_match_bundle(public_payload)
    assert bundle["doc_id"] == public_payload["doc_id"]
    assert bundle["matched_zones"] == public_payload["matched_zones"]
    assert bundle["matched_zone_count"] == public_payload["matched_zone_count"]


def test_assert_zone_match_bundle_safe_requires_singular_identity() -> None:
    payload = {
        "matched_zones": [],
        "matched_zone_count": 0,
        "zone_config_name": "ib_overview_zh",
        "zone_config_version": "0.2.0",
        "language": "zh",
        "resolved_filter_strategy_id": "heading_zone",
    }
    assert_zone_match_bundle_safe(payload)

    missing = dict(payload)
    del missing["zone_config_name"]
    with pytest.raises(ValueError, match="zone_config_name"):
        assert_zone_match_bundle_safe(missing)


def test_assert_zone_match_bundle_safe_rejects_bad_zone_count() -> None:
    payload = {
        "matched_zones": [],
        "matched_zone_count": 1,
        "zone_config_name": "ib_overview_zh",
        "zone_config_version": "0.2.0",
        "language": "zh",
        "resolved_filter_strategy_id": "heading_zone",
    }
    with pytest.raises(ValueError, match="matched_zone_count"):
        assert_zone_match_bundle_safe(payload)


def test_assert_zone_match_bundle_safe_delegates_privacy() -> None:
    payload = {
        "matched_zones": [
            {
                "zone_id": "Z0001",
                "blocks": [{"block_id": "C1", "original_text": "leak"}],
            }
        ],
        "matched_zone_count": 1,
        "zone_config_name": "ib_clinical_safety_zh",
        "zone_config_version": "0.2.0",
        "language": "zh",
        "resolved_filter_strategy_id": "heading_zone",
    }
    with pytest.raises(ValueError, match="forbidden key 'original_text'"):
        assert_zone_match_bundle_safe(payload)

    assert_zone_match_public_safe(
        {
            "matched_zones": [
                {
                    "zone_id": "Z0001",
                    "blocks": [{"block_id": "C1", "analysis_text": "safe"}],
                }
            ]
        }
    )
