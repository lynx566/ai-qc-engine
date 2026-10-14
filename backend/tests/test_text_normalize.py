from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.docx.handlers import _paragraph_normalize_meta
from core.normalization.text_normalize import normalize_text
from tests.block_manifest_test_helpers import build_block_manifest
from tests.extract_test_helpers import extract_docx_for_test

VT8802_V13_SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "ib_v1_3"
    / "VT8802 艾美妥珠单抗研究者手册 V1.3 2024.03.15.docx"
)


def test_normalize_text_converts_en_dash_to_hyphen() -> None:
    assert normalize_text("5–10 mg/kg") == "5-10 mg/kg"


def test_normalize_text_preserves_em_dash() -> None:
    source = "试验药物——艾美妥珠单抗——已给药"
    result = normalize_text(source)
    assert "——" in result
    assert result == source


def test_normalize_text_removes_soft_hyphen() -> None:
    source = "re\u00ADsearch"
    result = normalize_text(source)
    assert "\u00AD" not in result
    assert result == "research"


def test_paragraph_normalize_meta_includes_raw_text_when_changed() -> None:
    raw = "表2            OOJ-VT8802-02研究中不良反应发生情况汇总"
    normalized = normalize_text(raw)
    meta = _paragraph_normalize_meta(raw, normalized)

    assert meta["raw_text_changed_by_normalize"] is True
    assert meta["raw_text_before_normalize"] == raw
    assert "has_internal_newlines" not in meta


def test_paragraph_normalize_meta_omits_raw_text_when_unchanged() -> None:
    raw = "摘要"
    normalized = normalize_text(raw)
    meta = _paragraph_normalize_meta(raw, normalized)

    assert meta["raw_text_changed_by_normalize"] is False
    assert "raw_text_before_normalize" not in meta
    assert "has_internal_newlines" not in meta


def test_paragraph_normalize_meta_flags_internal_newlines() -> None:
    raw = "通用名称：VT8802\n代号：VT8802"
    normalized = normalize_text(raw)
    meta = _paragraph_normalize_meta(raw, normalized)

    assert meta["has_internal_newlines"] is True
    assert meta["raw_text_changed_by_normalize"] is True
    assert meta["raw_text_before_normalize"] == raw


def test_extract_docx_populates_normalize_meta_on_changed_blocks() -> None:
    bundle = extract_docx_for_test(VT8802_V13_SAMPLE)
    changed_blocks = [
        block
        for block in bundle.content_blocks
        if (block.meta or {}).get("raw_text_changed_by_normalize")
    ]
    assert changed_blocks

    for block in changed_blocks:
        meta = block.meta or {}
        assert meta.get("raw_text_before_normalize")
        assert normalize_text(meta["raw_text_before_normalize"]) == block.normalized_text


def test_extract_docx_flags_internal_newlines_when_present() -> None:
    bundle = extract_docx_for_test(VT8802_V13_SAMPLE)
    newline_blocks = [
        block
        for block in bundle.content_blocks
        if (block.meta or {}).get("has_internal_newlines")
    ]
    assert newline_blocks

    for block in newline_blocks:
        raw = (block.meta or {}).get("raw_text_before_normalize", "")
        assert "\n" in raw or "\r" in raw


def test_block_manifest_does_not_carry_raw_text_before_normalize() -> None:
    analysis_bundle = {
        "analysis_bundle_id": "prepare_analysis_test_normalize_meta",
        "doc_id": "doc_test_normalize_meta",
        "file_hash": (
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "heading",
                "order": 1,
                "analysis_text": "表2 OOJ-VT8802-02研究中不良反应发生情况汇总",
                "meta": {
                    "heading_level": None,
                    "table_ref_candidates": ["表2"],
                    "raw_text_changed_by_normalize": True,
                    "raw_text_before_normalize": (
                        "表2            OOJ-VT8802-02研究中不良反应发生情况汇总"
                    ),
                    "has_internal_newlines": False,
                },
            }
        ],
    }
    block_manifest = build_block_manifest(analysis_bundle)

    for block in block_manifest.get("blocks") or []:
        assert "raw_text_before_normalize" not in block
        assert "has_internal_newlines" not in block
        meta = block.get("meta") or {}
        assert "raw_text_before_normalize" not in meta
        assert "has_internal_newlines" not in meta
