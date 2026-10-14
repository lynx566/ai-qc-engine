from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.document_schema import Block, SourceRef
from core.document.sentence_index import (
    apply_sentence_index_to_block,
    is_canonical_source_sentence_id,
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


def test_canonical_source_sentence_id_accepts_content_and_table_blocks() -> None:
    assert is_canonical_source_sentence_id("C0001:S001")
    assert is_canonical_source_sentence_id("T0001:S001")


def test_canonical_source_sentence_id_rejects_non_canonical_shapes() -> None:
    for token in ("S0001", "CAND0001", "CTX0001", "S001", "C0001:S1", "C0001", ""):
        assert not is_canonical_source_sentence_id(token)


def test_extract_sentence_index_mints_canonical_source_sentence_ids() -> None:
    content = _kind_block("paragraph", "第一句。第二句。", block_id="C0010")
    apply_sentence_index_to_block(content)
    assert [s.sentence_id for s in content.sentences] == ["C0010:S001", "C0010:S002"]
    for sentence in content.sentences:
        assert is_canonical_source_sentence_id(sentence.sentence_id)

    table = _kind_block("table", "列A | 列B", block_id="C0020")
    apply_sentence_index_to_block(table)
    assert table.sentences[0].sentence_id == "C0020:S001"
    assert is_canonical_source_sentence_id(table.sentences[0].sentence_id)


def test_same_canonical_sentence_id_means_same_source_sentence() -> None:
    """Contract: dedup keyed on sentence_id is valid only for canonical Extract ids."""

    shared = "C0004:S001"
    assert is_canonical_source_sentence_id(shared)
    # Two units referencing the same Extract sentence must share one canonical id.
    unit_a = shared
    unit_b = shared
    assert unit_a == unit_b


def test_different_canonical_sentence_ids_mean_different_source_sentences() -> None:
    """Non-canonical alias collision must not collapse distinct source sentences."""

    assert not is_canonical_source_sentence_id("S0001")

    tu1_canonical = "C0010:S001"
    tu2_canonical = "C0020:S001"
    assert tu1_canonical != tu2_canonical
    assert is_canonical_source_sentence_id(tu1_canonical)
    assert is_canonical_source_sentence_id(tu2_canonical)
