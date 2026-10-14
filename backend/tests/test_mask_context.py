from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from privacy.config import PrivacyConfig
from privacy.profile import DEFAULT_DATE_SHIFT_OFFSET_DAYS
from runtime.prepare_analysis.context import infer_language_from_bundle
from tests.clinical_program_fixtures import canonical_clinical_program_fields


def test_infer_language_from_bundle() -> None:
    bundle = {"document_meta": {"language": "zh"}}
    assert infer_language_from_bundle(bundle) == "zh"


def test_mask_output_unaffected_by_summary_profile_presence() -> None:
    bundle = {
        "doc_id": "ib_001",
        "file_name": "ib_001.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "text": "研究者手册",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }

    result = prepare_analysis_bundle(bundle, language="zh", **canonical_clinical_program_fields())
    masked_text = result.analysis_bundle["content_blocks"][0]["analysis_text"]

    assert masked_text == "研究者手册"


def test_mask_bundle_shifts_dates_per_document() -> None:
    bundle = {
        "doc_id": "ib_001",
        "file_name": "ib_001.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "text": "入组日期2026年4月20日，随访2026年5月15日。",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }

    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        privacy_config=PrivacyConfig.from_dict(
            {
                "transforms": {
                    "after_extract": {"detectors": ["registry", "regex"]},
                    "after_filter": {"detectors": []},
                }
            }
        ), **canonical_clinical_program_fields())
    masked_text = result.analysis_bundle["content_blocks"][0]["analysis_text"]

    assert "2026年5月7日" in masked_text
    assert "2026年6月1日" in masked_text
    assert "2026年4月20日" not in masked_text
    assert result.mask_result.date_shift == {
        "enabled": True,
        "offset_days": DEFAULT_DATE_SHIFT_OFFSET_DAYS,
    }

