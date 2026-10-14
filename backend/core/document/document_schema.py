from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# =========================
# Bundle schema version
# Bump this when Block / DocumentBundle fields or types change.
# Independent of handler/parser implementation versions.
# =========================
BUNDLE_SCHEMA_VERSION = "0.2.1"


# =========================
# Source Type (current scope)
# =========================

SourceType = Literal["docx"]  # v0.1: docx-only, future: pdf/txt/md


# =========================
# Block Kind (semantic role)
# =========================
# "cover" and "front_note" are reserved for future use (not emitted in v0.1).

BlockKind = Literal[
    "cover",
    "toc",
    "front_note",
    "heading",
    "paragraph",
    "list_item",
    "table",
    "table_caption",
    "table_note",
    "header",
    "footer",
    "page_number",
    "unknown",
]


# =========================
# SourceRef
# =========================


@dataclass(frozen=True)
class SourceRef:
    """
    SourceRef describes how a Block can be traced back to the original document.

    IMPORTANT:
    - This is a black-box locator carried through the pipeline.
    - Pipeline logic must NOT interpret locator_payload.
    - Only downstream consumers (e.g., highlighter / renderer) should resolve it.
    """

    source_type: SourceType
    locator_type: str
    locator_payload: dict[str, Any] = field(default_factory=dict)


# =========================
# Sentence (extract-stage sentence index)
# =========================


@dataclass
class Sentence:
    """
    A canonical source sentence unit within a Block.

    ``raw_text`` is the source-visible unit payload (pre-normalization).
    ``normalized_text`` is the canonical processed payload for the same unit.

    ``sentence_id`` is the canonical source sentence identity: Extract-defined
    ``<block_id>:S<ordinal>`` (document-local; pair with bundle ``doc_id`` for
    cross-document refs). Downstream stages must inherit this id for 1:1 source
    sentences — role, TU membership, and route order must not be encoded here.
    """

    sentence_id: str
    raw_text: str
    normalized_text: str


# =========================
# Block
# =========================


@dataclass
class Block:
    """
    Block is the minimal normalized content unit emitted by the extract stage.

    It is the ONLY unit downstream steps should operate on.

    Design principles:
    - Format-agnostic (no docx-specific fields)
    - Self-contained (text + semantic role + source_ref)
    - Extensible via `meta` (do NOT over-design upfront)
    """

    # ---- identity (document-local; pair with bundle doc_id for global ref) ----
    block_id: str

    # ---- semantic role ----
    kind: BlockKind

    # ---- core content ----
    # Pre-normalization visible text (DOCX para.text / cell.text aggregation).
    raw_text: str

    # Canonical processed Extract representation for the block payload.
    normalized_text: str

    # ---- human-readable location (for debug / logging) ----
    loc: str

    # ---- trace-back to original document ----
    source_ref: SourceRef

    # ---- sentence index (extract stage) ----
    sentences: list[Sentence] = field(default_factory=list)

    # ---- optional ----
    page_no: int | None = None

    # ---- 1-based order within its block group (content_blocks / table_blocks / etc.)
    #      NOT a global document-wide sequence; assigned by the extractor after extraction ----
    order: int = 0

    # ---- document body reading order (0-based among emitted body blocks) ----
    #      Comparable across content_blocks / table_blocks / front_matter_blocks from body scan.
    doc_order_index: int | None = None

    # ---- heading ancestry at extraction time (full heading texts) ----
    heading_path: list[str] = field(default_factory=list)

    # ---- extension slot ----
    meta: dict[str, Any] = field(default_factory=dict)
    """
    meta is for:
    - source-specific attributes (e.g., style_name, section_index)
    - weak associations (e.g., table_ref_candidates)
    - parser/debug hints

    IMPORTANT:
    - Do NOT promote unstable fields to top-level prematurely
    - Keep pipeline logic independent from meta structure
    """


# =========================
# Document identity (extract envelope)
# =========================


@dataclass
class DocumentMeta:
    """Stable document identity produced at extract; not clinical business fields."""

    doc_id: str
    file_name: str
    display_name: str
    file_hash: str | None
    created_at: str


# =========================
# DocumentBundle
# =========================


@dataclass
class DocumentBundle:
    """
    DocumentBundle is the unified output of the extract stage.

    It represents a fully decomposed document, organized into:

    - 4 block groups (content-level data)
    - 1 document-level metadata slot

    This structure allows downstream steps to:
    - selectively consume relevant blocks
    - avoid format noise contamination
    - maintain clean separation of concerns
    """

    # ---- identity (machine doc_id; filenames are display-only) ----
    doc_id: str
    file_name: str
    display_name: str
    file_hash: str | None = None
    created_at: str = ""
    source_type: SourceType = "docx"

    # =========================
    # Block groups (4 major buckets)
    # =========================

    # 1. front matter blocks.
    # v0.1.1 docx handlers only emit low-risk front matter such as TOC.
    # cover/front_note are reserved but not emitted by default.
    front_matter_blocks: list[Block] = field(default_factory=list)

    # 2. main textual content (primary NLP input)
    content_blocks: list[Block] = field(default_factory=list)

    # 3. tables and structured data
    table_blocks: list[Block] = field(default_factory=list)

    # 4. formatting / layout noise (header, footer, page number, etc.)
    format_blocks: list[Block] = field(default_factory=list)

    # =========================
    # Document-level metadata (NOT blocks)
    # =========================

    document_meta: dict[str, Any] = field(default_factory=dict)
    """
    document_meta is for:
    - file-level attributes (e.g. source_path)
    - parser identity: parser_type (stable name), parser_version, bundle_schema_version,
      front_matter_policy_version / front_matter_policy,
      sentence_index_version / sentence_index_policy
    - extraction diagnostics (parse_warnings)
    - global hints (has_toc, has_tables, etc.)

    IMPORTANT:
    - This is NOT a block container
    - This is the "envelope" of the DocumentBundle
    """
