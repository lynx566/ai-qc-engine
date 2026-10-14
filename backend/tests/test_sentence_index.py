from __future__ import annotations

import json
import sys
from dataclasses import asdict, fields
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.document_schema import BUNDLE_SCHEMA_VERSION, Block, SourceRef
from core.normalization.text_normalize import normalize_text
from tests.extract_test_helpers import extract_docx_for_test
from core.document.sentence_index import (
    SENTENCE_INDEX_POLICY,
    SENTENCE_INDEX_VERSION,
    apply_sentence_index_to_block,
    build_sentences,
    legacy_sentence_normalized_payload,
    split_chinese_paragraph_sentences,
    split_source_paragraph_units,
)

FIXED_DOC_ID = "doc_00000000-0000-4000-8000-000000000001"
SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)


def _paragraph_block(
    text: str,
    *,
    block_id: str = "C0001",
    raw_text: str | None = None,
    normalized_text: str | None = None,
) -> Block:
    return Block(
        block_id=block_id,
        kind="paragraph",
        raw_text=raw_text if raw_text is not None else text,
        normalized_text=normalized_text if normalized_text is not None else text,
        loc="BODY:P1",
        source_ref=SourceRef(
            source_type="docx",
            locator_type="paragraph",
            locator_payload={"paragraph_index": 0},
        ),
    )


def _kind_block(kind: str, text: str, *, block_id: str) -> Block:
    return Block(
        block_id=block_id,
        kind=kind,  # type: ignore[arg-type]
        raw_text=text,
        normalized_text=text,
        loc=f"LOC:{kind}",
        source_ref=SourceRef(
            source_type="docx",
            locator_type="paragraph",
            locator_payload={"paragraph_index": 0},
        ),
    )


def _assert_sentence_canonical_fields(sentence: object) -> None:
    field_names = {field.name for field in fields(sentence)}
    assert field_names == {
        "sentence_id",
        "raw_text",
        "normalized_text",
    }
    assert "text" not in field_names
    assert not hasattr(sentence, "start")
    assert not hasattr(sentence, "end")


def test_paragraph_multiline_chinese_sentences() -> None:
    text = "第一句。第二句；第三句！第四句？"
    block = _paragraph_block(text)
    apply_sentence_index_to_block(block)

    assert block.normalized_text == text
    assert len(block.sentences) == 4
    assert [s.sentence_id for s in block.sentences] == [
        "C0001:S001",
        "C0001:S002",
        "C0001:S003",
        "C0001:S004",
    ]
    assert [s.raw_text for s in block.sentences] == [
        "第一句。",
        "第二句；",
        "第三句！",
        "第四句？",
    ]
    assert [s.normalized_text for s in block.sentences] == [
        "第一句。",
        "第二句；",
        "第三句！",
        "第四句？",
    ]
    for sentence in block.sentences:
        _assert_sentence_canonical_fields(sentence)
        assert sentence.normalized_text == normalize_text(sentence.raw_text)


def test_paragraph_splits_on_newline() -> None:
    text = "上行内容\n下行内容。"
    spans = split_chinese_paragraph_sentences(text)
    assert spans == [("上行内容", 0, 4), ("下行内容。", 5, 10)]
    assert split_source_paragraph_units(text) == ["上行内容", "下行内容。"]

    block = _paragraph_block(text)
    apply_sentence_index_to_block(block)
    assert len(block.sentences) == 2


def test_explicit_newline_three_units_with_normalized_gap() -> None:
    raw = "A\nB\nC"
    normalized = normalize_text(raw)
    assert normalized == "A B C"
    block = _paragraph_block(raw, raw_text=raw, normalized_text=normalized)
    apply_sentence_index_to_block(block)

    assert len(block.sentences) == 3
    assert [s.raw_text for s in block.sentences] == ["A", "B", "C"]
    assert [s.normalized_text for s in block.sentences] == ["A", "B", "C"]


def test_mixed_punctuation_and_newline_two_units() -> None:
    raw = "A。\nB。"
    block = _paragraph_block(raw)
    apply_sentence_index_to_block(block)
    assert len(block.sentences) == 2
    assert [s.raw_text for s in block.sentences] == ["A。", "B。"]


def test_repeated_newline_two_units() -> None:
    raw = "A\n\nB"
    block = _paragraph_block(raw)
    apply_sentence_index_to_block(block)
    assert len(block.sentences) == 2
    assert [s.raw_text for s in block.sentences] == ["A", "B"]


def test_duplicate_sentence_text_forward_cursor() -> None:
    raw = "A。A。"
    block = _paragraph_block(raw)
    apply_sentence_index_to_block(block)
    assert len(block.sentences) == 2
    assert [s.sentence_id for s in block.sentences] == ["C0001:S001", "C0001:S002"]
    assert block.sentences[0].raw_text == "A。"
    assert block.sentences[1].raw_text == "A。"
    assert block.sentences[0].normalized_text == "A。"
    assert block.sentences[1].normalized_text == "A。"


def test_raw_vs_normalized_unit_payload() -> None:
    raw = "表2\u00a0\u200b   OOJ\u00adVT8802-02。"
    normalized = normalize_text(raw)
    block = _paragraph_block(raw, raw_text=raw, normalized_text=normalized)
    apply_sentence_index_to_block(block)

    assert len(block.sentences) == 1
    sentence = block.sentences[0]
    assert sentence.raw_text == raw
    assert sentence.normalized_text == normalized
    assert raw != normalized


def test_paragraph_date_not_split_on_english_period() -> None:
    text = "研究截止日期为2023.11.30。下一节继续。"
    block = _paragraph_block(text)
    apply_sentence_index_to_block(block)

    assert len(block.sentences) == 2
    assert block.sentences[0].normalized_text == "研究截止日期为2023.11.30。"
    assert block.sentences[1].normalized_text == "下一节继续。"

    percent_text = "剂量为57.5%。"
    percent_block = _paragraph_block(percent_text)
    apply_sentence_index_to_block(percent_block)
    assert len(percent_block.sentences) == 1
    assert percent_block.sentences[0].normalized_text == percent_text


def test_heading_whole_block_sentence() -> None:
    raw = "临床安全性"
    normalized = "5.2.1 临床安全性"
    block = Block(
        block_id="C0002",
        kind="heading",
        raw_text=raw,
        normalized_text=normalized,
        loc="LOC:heading",
        source_ref=SourceRef(
            source_type="docx",
            locator_type="paragraph",
            locator_payload={"paragraph_index": 0},
        ),
    )
    apply_sentence_index_to_block(block)

    assert len(block.sentences) == 1
    sentence = block.sentences[0]
    assert sentence.sentence_id == "C0002:S001"
    assert sentence.raw_text == raw
    assert sentence.normalized_text == normalized


def test_list_item_whole_block_sentence() -> None:
    text = "1. 主要不良事件"
    block = _kind_block("list_item", text, block_id="C0003")
    apply_sentence_index_to_block(block)

    assert len(block.sentences) == 1
    assert block.sentences[0].raw_text == text
    assert block.sentences[0].normalized_text == text


def test_table_whole_block_sentence() -> None:
    text = "列A | 列B\n值1 | 值2"
    block = _kind_block("table", text, block_id="T0001")
    apply_sentence_index_to_block(block)

    assert len(block.sentences) == 1
    sentence = block.sentences[0]
    assert sentence.sentence_id == "T0001:S001"
    assert sentence.raw_text == text
    assert sentence.normalized_text == text


def test_toc_header_footer_have_sentences_field() -> None:
    cases = [
        ("toc", "目录", "M0001"),
        ("header", "机密文件", "F0001"),
        ("footer", "第 1 页", "F0002"),
    ]
    for kind, text, block_id in cases:
        block = _kind_block(kind, text, block_id=block_id)
        apply_sentence_index_to_block(block)

        assert block.normalized_text == text
        assert isinstance(block.sentences, list)
        assert len(block.sentences) == 1
        assert block.sentences[0].sentence_id == f"{block_id}:S001"
        assert block.sentences[0].raw_text == text
        assert block.sentences[0].normalized_text == text


def test_empty_block_has_empty_sentences_list() -> None:
    block = _paragraph_block("")
    apply_sentence_index_to_block(block)
    assert block.normalized_text == ""
    assert block.sentences == []

    heading = _kind_block("heading", "", block_id="C0099")
    apply_sentence_index_to_block(heading)
    assert heading.sentences == []


def test_build_sentences_reserved_kinds_use_whole_block() -> None:
    for kind in ("cover", "front_note", "table_caption", "table_note", "page_number", "unknown"):
        sentences = build_sentences(
            "X0001",
            kind,
            raw_text="预留内容",
            normalized_text="预留内容",
        )
        assert len(sentences) == 1
        assert sentences[0].raw_text == "预留内容"
        assert sentences[0].normalized_text == "预留内容"


def test_legacy_sentence_normalized_payload_reads_text_only() -> None:
    legacy = {"sentence_id": "C0001:S001", "text": "legacy payload", "start": 0, "end": 5}
    assert legacy_sentence_normalized_payload(legacy) == "legacy payload"
    assert "raw_text" not in legacy


def test_persisted_bundle_sentence_shape() -> None:
    block = _paragraph_block("A。B。")
    apply_sentence_index_to_block(block)
    payload = asdict(block)
    assert payload["sentences"][0]["raw_text"] == "A。"
    assert payload["sentences"][0]["normalized_text"] == "A。"
    assert "text" not in payload["sentences"][0]
    assert "start" not in payload["sentences"][0]
    assert "end" not in payload["sentences"][0]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert '"raw_text"' in serialized
    assert '"normalized_text"' in serialized
    assert '"start"' not in serialized
    assert '"end"' not in serialized


def test_sentence_index_version_constants() -> None:
    assert SENTENCE_INDEX_VERSION == "0.2"
    assert SENTENCE_INDEX_POLICY == "zh_source_unit_rule_based"
    assert BUNDLE_SCHEMA_VERSION == "0.2.1"


@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_extract_bundle_document_meta_has_sentence_index_version(_mock_gen) -> None:
    bundle = extract_docx_for_test(SAMPLE)
    assert bundle.document_meta.get("sentence_index_version") == SENTENCE_INDEX_VERSION
    assert bundle.document_meta.get("sentence_index_policy") == SENTENCE_INDEX_POLICY
    assert bundle.document_meta.get("bundle_schema_version") == BUNDLE_SCHEMA_VERSION


@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_extract_bundle_blocks_have_sentence_index(_mock_gen) -> None:
    bundle = extract_docx_for_test(SAMPLE)
    all_blocks = (
        bundle.front_matter_blocks
        + bundle.content_blocks
        + bundle.table_blocks
        + bundle.format_blocks
    )
    assert all_blocks

    for block in all_blocks:
        assert block.normalized_text
        assert isinstance(block.sentences, list)
        assert block.sentences
        for sentence in block.sentences:
            _assert_sentence_canonical_fields(sentence)
            assert sentence.sentence_id.startswith(f"{block.block_id}:S")
            assert sentence.raw_text
            assert sentence.normalized_text
            if block.kind == "paragraph":
                assert sentence.normalized_text == normalize_text(sentence.raw_text)

        if block.kind == "paragraph":
            assert len(block.sentences) >= 1
        elif block.kind in {"heading", "list_item", "table", "toc", "header", "footer"}:
            assert len(block.sentences) == 1
            assert block.sentences[0].raw_text == block.raw_text
            assert block.sentences[0].normalized_text == block.normalized_text
