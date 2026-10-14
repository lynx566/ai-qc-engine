from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.privacy_safety import (
    PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_KEYS,
    PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES,
    PUBLIC_BLOCK_MANIFEST_FORBIDDEN_KEYS,
    assert_public_analysis_bundle_safe,
    assert_zone_match_public_safe,
    scan_public_block_manifest_violations,
    scan_raw_term_leaks,
    walk_forbidden_keys,
    walk_forbidden_path_patterns,
)
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from steps.filter import extract_zones_from_bundle, to_public_filter_payload
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from privacy.config import PrivacyConfig
from tests.block_manifest_test_helpers import build_block_manifest
from tests.clinical_program_fixtures import canonical_clinical_program_fields
from tests.filter_test_helpers import resolved_filter_job
from tests.fixtures.privacy_golden_terms import (
    DEFAULT_RAW_TERM_GOLDEN_LIST,
    VT8802_IB_HEADING_RAW_TERMS,
)

SAFETY_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "legacy_ib_v1_0"
    / "OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15.docx"
)


def _heading_path_strings(payload: dict) -> list[str]:
    strings: list[str] = []

    def _walk(value: object) -> None:
        if isinstance(value, dict):
            heading_path = value.get("heading_path")
            if isinstance(heading_path, list):
                strings.extend(str(item) for item in heading_path)
            for item in value.values():
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(payload)
    return strings


def _registry_regex_config() -> PrivacyConfig:
    return PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": []},
            }
        }
    )


def _prepare_slim_analysis_bundle() -> dict:
    from tests.extract_test_helpers import extract_docx_for_test

    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    analysis = prepare_analysis_bundle(
        asdict(bundle),
        profile=None,
        language="zh",
        privacy_config=_registry_regex_config(),
        analysis_bundle_id="prepare_analysis_leak_regression_test",
        **canonical_clinical_program_fields(),
    )
    return dict(analysis.analysis_bundle)


def _prepare_fresh_zone_match_bundle() -> dict:
    analysis_bundle = _prepare_slim_analysis_bundle()
    block_manifest = build_block_manifest(analysis_bundle)
    zones_raw = extract_zones_from_bundle(
        analysis_bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )
    return to_public_filter_payload(
        zones_raw,
        block_manifest=block_manifest,
    )


class TestPublicAnalysisBundleLeaks:
    def test_no_forbidden_keys_when_privacy_on(self) -> None:
        bundle = _prepare_slim_analysis_bundle()
        assert bundle.get("privacy_enabled") is True
        assert bundle.get("analysis_bundle_contract") == "public_masked_v0.4"
        hits = walk_forbidden_keys(
            bundle,
            PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_KEYS,
            root_label="analysis_bundle",
        )
        assert hits == []

    def test_no_forbidden_sentence_paths_when_privacy_on(self) -> None:
        bundle = _prepare_slim_analysis_bundle()
        hits = walk_forbidden_path_patterns(
            bundle,
            PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES,
            root_label="analysis_bundle",
        )
        assert hits == []

    def test_no_raw_terms_in_public_bundle(self) -> None:
        bundle = _prepare_slim_analysis_bundle()
        assert_public_analysis_bundle_safe(
            bundle,
            terms=DEFAULT_RAW_TERM_GOLDEN_LIST,
        )

    def test_no_raw_terms_in_heading_path(self) -> None:
        bundle = _prepare_slim_analysis_bundle()
        heading_only = {"segments": _heading_path_strings(bundle)}
        hits = scan_raw_term_leaks(
            heading_only,
            VT8802_IB_HEADING_RAW_TERMS,
            root_label="heading_paths",
        )
        assert hits == []


class TestZoneMatchBundleLeaks:
    def test_no_raw_terms_in_public_zone_match(self) -> None:
        payload = _prepare_fresh_zone_match_bundle()
        assert_zone_match_public_safe(
            payload,
            terms=DEFAULT_RAW_TERM_GOLDEN_LIST,
        )

    def test_no_forbidden_keys_in_fresh_zone_match(self) -> None:
        payload = _prepare_fresh_zone_match_bundle()
        assert_zone_match_public_safe(payload)


class TestBlockManifestLeaks:
    def test_no_raw_rows_key_in_synthetic_table_manifest(self) -> None:
        analysis_bundle = {
            "analysis_bundle_id": "prepare_analysis_test_raw_rows",
            "doc_id": "doc_test_raw_rows",
            "file_hash": (
                "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            ),
            "content_blocks": [],
            "table_blocks": [
                {
                    "block_id": "T0001",
                    "kind": "table",
                    "order": 1,
                    "doc_order_index": 1,
                    "analysis_text": "SOC | n",
                    "meta": {
                        "row_count": 1,
                        "column_count": 2,
                        "raw_rows": [["SOC", "VT8802"]],
                    },
                }
            ],
        }
        manifest = build_block_manifest(analysis_bundle)
        hits = walk_forbidden_keys(
            manifest,
            PUBLIC_BLOCK_MANIFEST_FORBIDDEN_KEYS,
            root_label="block_manifest",
        )
        raw_row_hits = [hit for hit in hits if hit.key == "raw_rows"]
        assert raw_row_hits == []


class TestBlockManifestSlimPublicSideEffect:
    """Slim public analysis_bundle omits meta.raw_rows; manifest inherits that gap."""

    def test_no_raw_rows_from_safety_sample_prepare(self) -> None:
        analysis_bundle = _prepare_slim_analysis_bundle()
        manifest = build_block_manifest(analysis_bundle)
        report = scan_public_block_manifest_violations(
            manifest,
            DEFAULT_RAW_TERM_GOLDEN_LIST,
        )
        assert report["passed"] is True
