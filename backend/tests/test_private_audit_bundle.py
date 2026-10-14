from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.private_audit_bundle import (
    PRIVATE_AUDIT_SCHEMA_VERSION,
    assert_private_audit_bundle_shape,
    build_private_audit_bundle_from_audit_surfaces,
)
from runtime.run_summaries import build_prepare_analysis_output_privacy_contract


def test_build_private_audit_bundle_from_audit_surfaces() -> None:
    surfaces = [
        {
            "block_id": "C0001",
            "kind": "paragraph",
            "normalized_text": "VT8802 body",
            "analysis_text": "StudyDrug_001 body",
            "heading_path_extract": ["VT8802 heading"],
            "meta_audit": {"raw_rows": [["VT8802"]]},
        }
    ]
    audit = build_private_audit_bundle_from_audit_surfaces(
        surfaces,
        doc_id="doc_test",
        file_hash=(
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        analysis_bundle_id="prepare_analysis_test",
    )
    assert_private_audit_bundle_shape(audit)
    assert audit["private_audit_schema_version"] == PRIVATE_AUDIT_SCHEMA_VERSION
    assert audit["blocks"][0]["heading_path_extract"] == ["VT8802 heading"]
    assert audit["blocks"][0]["meta_audit"]["raw_rows"] == [["VT8802"]]


def test_output_privacy_contract_distinguishes_identity_mode() -> None:
    identity = build_prepare_analysis_output_privacy_contract(
        privacy_transform_applied=False,
    )
    assert identity["analysis_bundle"]["artifact_privacy_level"] == "local_raw_public"
    assert identity["analysis_bundle"]["safe_for_export"] is False
    assert identity["private_outputs"] == {}

    privacy = build_prepare_analysis_output_privacy_contract(
        privacy_transform_applied=True,
    )
    assert (
        privacy["analysis_bundle"]["artifact_privacy_level"]
        == "public_masked_v0.4"
    )
    assert privacy["private_outputs"]["private_audit_bundle"] == "private_raw_audit"
