"""
Sentence indexing strategy (v0.2)

Stable sentence-level anchors for downstream privacy transformation and evidence
tracing. Each indexed sentence carries canonical identity ``<block_id>:Snnn``.

Paragraph blocks split source-visible units from ``Block.raw_text`` using Chinese
sentence delimiters (。；！？) and explicit newlines. Each unit carries its own
``raw_text`` and per-unit ``normalized_text``.

English period "." is intentionally not used as a delimiter to avoid incorrect
splits in dates, decimals, and abbreviations.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from core.document.document_schema import Block, BlockKind, DocumentBundle, Sentence
from core.normalization.text_normalize import normalize_text

SENTENCE_INDEX_VERSION = "0.2"
SENTENCE_INDEX_POLICY = "zh_source_unit_rule_based"

# Extract ``build_block_id``: single-letter bucket prefix + 4-digit ordinal (1-based).
_BLOCK_ID_RE = r"[A-Z]\d{4}"

CANONICAL_SOURCE_SENTENCE_ID_RE = re.compile(
    rf"^(?P<block_id>{_BLOCK_ID_RE}):S(?P<ordinal>\d{{3}})$"
)


def is_canonical_source_sentence_id(sentence_id: str) -> bool:
    """Return True when ``sentence_id`` matches Extract ``<block_id>:Snnn`` shape."""

    token = str(sentence_id or "").strip()
    return bool(token) and CANONICAL_SOURCE_SENTENCE_ID_RE.fullmatch(token) is not None


# Paragraph splitting: Chinese sentence enders and newlines only (not ASCII period).
_CN_SENTENCE_END_CHARS = frozenset("。；！？")

# Kinds that use the whole block as a single sentence.
_WHOLE_BLOCK_KINDS = frozenset(
    {
        "toc",
        "heading",
        "list_item",
        "table",
        "header",
        "footer",
        "cover",
        "front_note",
        "table_caption",
        "table_note",
        "page_number",
        "unknown",
    }
)


def split_source_paragraph_units(raw_text: str) -> list[str]:
    """
    Split paragraph ``Block.raw_text`` into ordered source-visible unit payloads.

    Boundary-adjacent layout whitespace is excluded; internal whitespace is kept.
    Newline separators are not included in any unit payload.
    """
    return [payload for payload, _start, _end in _split_source_units_with_spans(raw_text)]


def split_chinese_paragraph_sentences(text: str) -> list[tuple[str, int, int]]:
    """
    Split *text* into (unit_payload, start, end) spans relative to *text*.

    Uses the same source-unit boundary policy as Extract paragraph segmentation.
    Non-Extract callers (e.g. projection helpers) may apply this to analysis text;
    Extract paragraph materialization must use ``Block.raw_text`` via
    ``split_source_paragraph_units`` / ``build_sentences``.
    """
    return _split_source_units_with_spans(text)


def _split_source_units_with_spans(text: str) -> list[tuple[str, int, int]]:
    if not text:
        return []

    units: list[tuple[str, int, int]] = []
    start = 0
    n = len(text)

    for i, ch in enumerate(text):
        if ch in _CN_SENTENCE_END_CHARS or ch == "\n":
            end = i + 1
            chunk = text[start:end]
            stripped = chunk.strip()
            if stripped:
                lead = len(chunk) - len(chunk.lstrip())
                s = start + lead
                e = s + len(stripped)
                units.append((text[s:e], s, e))
            start = end

    if start < n:
        chunk = text[start:]
        stripped = chunk.strip()
        if stripped:
            lead = len(chunk) - len(chunk.lstrip())
            s = start + lead
            e = s + len(stripped)
            units.append((text[s:e], s, e))

    return units


def legacy_sentence_normalized_payload(sentence: Mapping[str, Any]) -> str:
    """Read normalized payload from legacy Extract sentence dicts that used ``text``."""

    if "normalized_text" in sentence:
        return str(sentence["normalized_text"])
    if "text" in sentence:
        return str(sentence["text"])
    return ""


def build_sentences(
    block_id: str,
    kind: BlockKind,
    *,
    raw_text: str,
    normalized_text: str,
) -> list[Sentence]:
    """Build sentence list for a block from source-visible units."""
    if kind == "paragraph":
        raw_units = split_source_paragraph_units(raw_text)
        unit_pairs: list[tuple[str, str]] = []
        for unit_raw in raw_units:
            unit_norm = normalize_text(unit_raw)
            if unit_norm:
                unit_pairs.append((unit_raw, unit_norm))
        if not unit_pairs:
            return []
        return [
            Sentence(
                sentence_id=f"{block_id}:S{index:03d}",
                raw_text=unit_raw,
                normalized_text=unit_norm,
            )
            for index, (unit_raw, unit_norm) in enumerate(unit_pairs, start=1)
        ]

    if kind in _WHOLE_BLOCK_KINDS or normalized_text:
        if not normalized_text:
            return []
        return [
            Sentence(
                sentence_id=f"{block_id}:S001",
                raw_text=raw_text,
                normalized_text=normalized_text,
            )
        ]
    return []


def apply_sentence_index_to_block(block: Block) -> Block:
    """Build sentence records from block raw/normalized text."""
    if not isinstance(block.raw_text, str):
        raise TypeError("raw_text must already be str")
    if not isinstance(block.normalized_text, str):
        raise TypeError("normalized_text must already be str")

    block.sentences = build_sentences(
        block.block_id,
        block.kind,
        raw_text=block.raw_text,
        normalized_text=block.normalized_text,
    )
    return block


def apply_sentence_index(bundle: DocumentBundle) -> DocumentBundle:
    """Populate sentences on every block in the bundle."""
    for group in (
        bundle.front_matter_blocks,
        bundle.content_blocks,
        bundle.table_blocks,
        bundle.format_blocks,
    ):
        for block in group:
            apply_sentence_index_to_block(block)
    return bundle
