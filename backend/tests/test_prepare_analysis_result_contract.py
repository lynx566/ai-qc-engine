"""Validator guards for the canonical Prepare Analysis Step result contract."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.prepare_analysis import validate_prepare_analysis_result
from operations.prepare_analysis.contracts import AnalysisBundleResult
from privacy.schemas import MaskedBlock, MaskResult


def _analysis_bundle(*, block_id: str = "C0001") -> dict[str, Any]:
    return {
        "doc_id": "doc_validator",
        "file_hash": "sha256:" + "b" * 64,
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "stage": "prepare_analysis",
        "pipeline": ["extract", "prepare_analysis"],
        "analysis_bundle_schema_version": "0.3.0",
        "analysis_bundle_contract": "local_raw_v0.3",
        "privacy_enabled": False,
        "privacy_transforms": {
            "after_extract": {
                "detectors": [],
                "applied": False,
                "detectors_used": [],
            },
            "after_filter": {"detectors": [], "applied": False},
        },
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": block_id,
                "kind": "paragraph",
                "normalized_text": "Example text.",
                "analysis_text": "Example text.",
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "normalized_text": "Example text.",
                        "analysis_text": "Example text.",
                    }
                ],
            }
        ],
        "table_blocks": [],
        "format_blocks": [],
    }


def _heading_projection(*, block_id: str = "C0001") -> SimpleNamespace:
    return SimpleNamespace(content={block_id: []}, tables={})


def _mask_result(*, block_id: str = "C0001") -> MaskResult:
    return MaskResult(
        doc_id="doc_validator",
        masked_blocks=[
            MaskedBlock(
                block_id=block_id,
                original_text="Example text.",
                masked_text="Example text.",
                mask_hits=[],
            )
        ],
        mapping={"schema_version": "0.2.0", "doc_id": "doc_validator", "mappings": []},
        date_shift={"enabled": False, "offset_days": 0},
        detectors=[],
        privacy_mode="none",
    )


def test_validator_accepts_raw_result_without_mask_result() -> None:
    result = AnalysisBundleResult(
        doc_id="doc_validator",
        analysis_bundle=_analysis_bundle(),
        mask_result=None,
        block_audit_surfaces=[],
        heading_projection=_heading_projection(),
    )

    validate_prepare_analysis_result(result)


def test_validator_rejects_absent_mask_result_with_audit_surfaces() -> None:
    result = AnalysisBundleResult(
        doc_id="doc_validator",
        analysis_bundle=_analysis_bundle(),
        mask_result=None,
        block_audit_surfaces=[{"block_id": "C0001"}],
        heading_projection=_heading_projection(),
    )

    with pytest.raises(ValueError, match="block_audit_surfaces must be empty"):
        validate_prepare_analysis_result(result)


def test_validator_accepts_mask_result_with_empty_audit_surfaces() -> None:
    result = AnalysisBundleResult(
        doc_id="doc_validator",
        analysis_bundle=_analysis_bundle(),
        mask_result=_mask_result(),
        block_audit_surfaces=[],
        heading_projection=_heading_projection(),
    )

    validate_prepare_analysis_result(result)


def test_validator_accepts_mask_result_with_audit_surfaces() -> None:
    result = AnalysisBundleResult(
        doc_id="doc_validator",
        analysis_bundle=_analysis_bundle(),
        mask_result=_mask_result(),
        block_audit_surfaces=[{"block_id": "C0001", "analysis_text": "Example text."}],
        heading_projection=_heading_projection(),
    )

    validate_prepare_analysis_result(result)
