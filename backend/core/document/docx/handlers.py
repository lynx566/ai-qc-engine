from __future__ import annotations

import re
from typing import Any

from core.normalization.text_normalize import normalize_text
from core.document.document_schema import Block, SourceRef
from core.document.docx.numbering import HeadingNumberingState, prepend_heading_number_if_needed
from core.document.docx.presentation import extract_block_presentation_meta
from core.document.docx.revision_text import (
    RevisionTextObserver,
    extract_cell_revision_aware_text,
    extract_paragraph_revision_aware_text,
)

from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph


# Version management
# DOCX_HANDLERS_VERSION = docx parsing implementation version (bump when parsing logic changes)
# BUNDLE_SCHEMA_VERSION  = output JSON structure version; owned by core/document/document_schema.py
# They can diverge independently.
DOCX_HANDLERS_VERSION = "0.1.11"
DOCX_PARSER_NAME = "docx_handlers"
# Bump when front-matter policy wording or classification rules change.
FRONT_MATTER_POLICY_VERSION = "0.1.3"

# block_id prefix (build_block_id): one letter per DocumentBundle stream, 1-based suffix per stream.
BLOCK_ID_CONTENT = "C"  # content_blocks: paragraph / heading / list_item
BLOCK_ID_TABLE = "T"  # table_blocks
BLOCK_ID_FORMAT = "F"  # format_blocks: header / footer / (future page_number, …)
BLOCK_ID_FRONT_MATTER = "M"  # front_matter_blocks: toc, …

# Kinds that go into front_matter_blocks (emitted: toc only in v0.1.x)
FRONT_MATTER_KINDS = {"toc"}

# Internal extractors below (e.g. extract_paragraph_blocks, flatten_table_text) are
# docx-handler-local; the module path is the docx scope, so names skip a redundant
# "docx_" prefix. Heuristic / style / locale helpers are prefixed with docx_* to
# avoid being mistaken for format-agnostic utilities.


def build_block_id(prefix: str, index: int) -> str:
    """
    Document-local block id: ``{prefix}{n:04d}`` (*n* 1-based; *index* 0-based per stream).

    Prefix = bundle bucket:
    ``C`` content, ``T`` table, ``F`` format (header/footer/…), ``M`` front matter (TOC/…).

    Global reference is ``(doc_id, block_id)`` on the enclosing ``DocumentBundle``.
    """
    return f"{prefix}{index + 1:04d}"


def _update_heading_path_stack(
    stack: list[str],
    *,
    heading_level: int,
    heading_text: str,
) -> list[str]:
    """Return heading ancestry after inserting *heading_text* at *heading_level*."""
    kept = stack[: max(heading_level - 1, 0)]
    return kept + [heading_text]


def _iter_docx_body_items(doc: DocxDocument):
    """Yield body children in document order: (kind, item, body_index)."""
    para_index = 0
    table_index = 0
    for child in doc.element.body.iterchildren():
        tag = child.tag
        if tag.endswith("}p"):
            yield "paragraph", Paragraph(child, doc), para_index
            para_index += 1
        elif tag.endswith("}tbl"):
            yield "table", Table(child, doc), table_index
            table_index += 1


def extract_body_blocks_ordered(
    doc: DocxDocument,
    *,
    revision_observer: RevisionTextObserver | None = None,
) -> tuple[list[Block], list[Block], list[Block]]:
    """
    Extract front matter, content, and table blocks in document body reading order.

    Assigns ``doc_order_index`` (0-based, cross-stream) and ``heading_path`` to every
    emitted body block. ``order`` remains the 1-based index within each block group.
    """
    front_matter_blocks: list[Block] = []
    content_blocks: list[Block] = []
    table_blocks: list[Block] = []
    content_seq = 0
    front_matter_seq = 0
    table_seq = 0
    heading_stack: list[str] = []
    doc_order_index = 0
    heading_numbering_state = HeadingNumberingState.from_document(doc)

    for item_kind, item, item_index in _iter_docx_body_items(doc):
        if item_kind == "paragraph":
            para = item
            para_index = item_index
            raw_text, paragraph_obs = extract_paragraph_revision_aware_text(para)
            if revision_observer is not None:
                revision_observer.absorb(paragraph_obs)
            raw_text = raw_text or ""
            normalized_text = normalize_text(raw_text)
            if not normalized_text:
                continue

            kind = classify_docx_paragraph_kind(
                para=para,
                para_index=para_index,
                text=normalized_text,
            )

            meta = _build_content_block_meta(
                para=para,
                kind=kind,
                text=normalized_text,
                raw_text=raw_text,
            )

            if kind == "heading":
                normalized_text = prepend_heading_number_if_needed(
                    para,
                    normalized_text,
                    state=heading_numbering_state,
                )

            heading_path = list(heading_stack)
            if kind == "heading":
                level = meta.get("heading_level")
                if isinstance(level, int):
                    heading_stack = _update_heading_path_stack(
                        heading_stack,
                        heading_level=level,
                        heading_text=normalized_text,
                    )
                    heading_path = list(heading_stack)

            if kind in FRONT_MATTER_KINDS:
                block_id = build_block_id(BLOCK_ID_FRONT_MATTER, front_matter_seq)
                bucket = front_matter_blocks
                front_matter_seq += 1
            else:
                block_id = build_block_id(BLOCK_ID_CONTENT, content_seq)
                bucket = content_blocks
                content_seq += 1

            bucket.append(
                Block(
                    block_id=block_id,
                    kind=kind,
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    loc=build_paragraph_loc(kind=kind, para_index=para_index),
                    source_ref=SourceRef(
                        source_type="docx",
                        locator_type="paragraph",
                        locator_payload={
                            "paragraph_index": para_index,
                        },
                    ),
                    page_no=None,
                    doc_order_index=doc_order_index,
                    heading_path=heading_path,
                    meta=meta,
                )
            )
            doc_order_index += 1
            continue

        table = item
        table_index = item_index
        visible_rows, normalized_rows = extract_table_row_pairs(
            table,
            revision_observer=revision_observer,
        )
        table_normalized_text = flatten_table_text_from_rows(normalized_rows)
        if not table_normalized_text:
            continue
        table_raw_text = flatten_table_text_from_rows(visible_rows)

        table_blocks.append(
            Block(
                block_id=build_block_id(BLOCK_ID_TABLE, table_seq),
                kind="table",
                raw_text=table_raw_text,
                normalized_text=table_normalized_text,
                loc=f"TABLE:T{table_seq + 1}",
                source_ref=SourceRef(
                    source_type="docx",
                    locator_type="table",
                    locator_payload={
                        "table_index": table_index,
                    },
                ),
                page_no=None,
                doc_order_index=doc_order_index,
                heading_path=list(heading_stack),
                meta=_build_table_block_meta(table, raw_rows=normalized_rows),
            )
        )
        table_seq += 1
        doc_order_index += 1

    return front_matter_blocks, content_blocks, table_blocks


def extract_paragraph_blocks(
    doc: DocxDocument,
    *,
    revision_observer: RevisionTextObserver | None = None,
) -> tuple[list[Block], list[Block]]:
    """
    Extract paragraph-based blocks and split them into:
    - front_matter_blocks
    - content_blocks

    v0.1.1 policy:
    - Only low-risk front matter is extracted here, mainly TOC.
    - Cover/title-page detection is intentionally conservative.
    - Do NOT classify early paragraphs as front matter by position alone.
    """
    front_matter_blocks: list[Block] = []
    content_blocks: list[Block] = []
    content_seq = 0
    front_matter_seq = 0

    for para_index, para in enumerate(doc.paragraphs):
        raw_text, paragraph_obs = extract_paragraph_revision_aware_text(para)
        if revision_observer is not None:
            revision_observer.absorb(paragraph_obs)
        raw_text = raw_text or ""
        normalized_text = normalize_text(raw_text)
        if not normalized_text:
            continue

        kind = classify_docx_paragraph_kind(
            para=para,
            para_index=para_index,
            text=normalized_text,
        )

        meta = _build_content_block_meta(
            para=para,
            kind=kind,
            text=normalized_text,
            raw_text=raw_text,
        )

        if kind in FRONT_MATTER_KINDS:
            block_id = build_block_id(BLOCK_ID_FRONT_MATTER, front_matter_seq)
        else:
            block_id = build_block_id(BLOCK_ID_CONTENT, content_seq)

        block = Block(
            block_id=block_id,
            kind=kind,
            raw_text=raw_text,
            normalized_text=normalized_text,
            loc=build_paragraph_loc(kind=kind, para_index=para_index),
            source_ref=SourceRef(
                source_type="docx",
                locator_type="paragraph",
                locator_payload={
                    "paragraph_index": para_index,
                },
            ),
            page_no=None,
            meta=meta,
        )

        if kind in FRONT_MATTER_KINDS:
            front_matter_blocks.append(block)
            front_matter_seq += 1
        else:
            content_blocks.append(block)
            content_seq += 1

    return front_matter_blocks, content_blocks


def extract_table_blocks(
    doc: DocxDocument,
    *,
    revision_observer: RevisionTextObserver | None = None,
) -> list[Block]:
    table_blocks: list[Block] = []
    table_seq = 0

    for table_index, table in enumerate(doc.tables):
        visible_rows, normalized_rows = extract_table_row_pairs(
            table,
            revision_observer=revision_observer,
        )
        table_normalized_text = flatten_table_text_from_rows(normalized_rows)
        if not table_normalized_text:
            continue
        table_raw_text = flatten_table_text_from_rows(visible_rows)

        block = Block(
            block_id=build_block_id(BLOCK_ID_TABLE, table_seq),
            kind="table",
            raw_text=table_raw_text,
            normalized_text=table_normalized_text,
            loc=f"TABLE:T{table_seq + 1}",
            source_ref=SourceRef(
                source_type="docx",
                locator_type="table",
                locator_payload={
                    "table_index": table_index,
                },
            ),
            page_no=None,
            meta=_build_table_block_meta(table, raw_rows=normalized_rows),
        )
        table_blocks.append(block)
        table_seq += 1

    return table_blocks


def extract_format_blocks(
    doc: DocxDocument,
    *,
    revision_observer: RevisionTextObserver | None = None,
) -> list[Block]:
    """
    Extract distinct headers/footers from sections.

    v0.1.1:
    - deduplicate repeated text
    - no advanced page-level fidelity
    """
    format_blocks: list[Block] = []
    seen: set[tuple[str, str]] = set()

    format_seq = 0

    for section_index, section in enumerate(doc.sections):
        header_raw_text, header_normalized_text = join_paragraph_texts(
            section.header.paragraphs,
            revision_observer=revision_observer,
        )
        if header_normalized_text:
            key = ("header", header_normalized_text)
            if key not in seen:
                seen.add(key)
                format_blocks.append(
                    Block(
                        block_id=build_block_id(BLOCK_ID_FORMAT, format_seq),
                        kind="header",
                        raw_text=header_raw_text,
                        normalized_text=header_normalized_text,
                        loc=f"FORMAT:HEADER:S{section_index + 1}",
                        source_ref=SourceRef(
                            source_type="docx",
                            locator_type="header",
                            locator_payload={
                                "section_index": section_index,
                            },
                        ),
                        page_no=None,
                        meta={
                            "section_index": section_index,
                        },
                    )
                )
                format_seq += 1

        footer_raw_text, footer_normalized_text = join_paragraph_texts(
            section.footer.paragraphs,
            revision_observer=revision_observer,
        )
        if footer_normalized_text:
            key = ("footer", footer_normalized_text)
            if key not in seen:
                seen.add(key)
                format_blocks.append(
                    Block(
                        block_id=build_block_id(BLOCK_ID_FORMAT, format_seq),
                        kind="footer",
                        raw_text=footer_raw_text,
                        normalized_text=footer_normalized_text,
                        loc=f"FORMAT:FOOTER:S{section_index + 1}",
                        source_ref=SourceRef(
                            source_type="docx",
                            locator_type="footer",
                            locator_payload={
                                "section_index": section_index,
                            },
                        ),
                        page_no=None,
                        meta={
                            "section_index": section_index,
                        },
                    )
                )
                format_seq += 1

    return format_blocks


FRONT_MATTER_POLICY_TEXT = (
    "front_matter_blocks carries low-risk front matter only (currently TOC). "
    "Cover/title-page content is not classified as front matter by default; "
    "it remains in content_blocks for downstream resolution."
)


def build_document_meta(
    doc: DocxDocument,
    front_matter_blocks: list[Block],
    table_blocks: list[Block],
    format_blocks: list[Block],
    parse_warnings: list[str] | None = None,
    *,
    parser_type: str,
    parser_version: str,
    bundle_schema_version: str,
) -> dict[str, Any]:
    has_toc = any(block.kind == "toc" for block in front_matter_blocks)

    return {
        "parser_type": parser_type,
        "parser_version": parser_version,
        "bundle_schema_version": bundle_schema_version,
        "front_matter_policy_version": FRONT_MATTER_POLICY_VERSION,
        "front_matter_policy": FRONT_MATTER_POLICY_TEXT,
        "paragraph_count_raw": len(doc.paragraphs),
        "table_count_raw": len(doc.tables),
        "parse_warnings": parse_warnings or [],
        "has_front_matter": len(front_matter_blocks) > 0,
        "has_toc": has_toc,
        "has_tables": len(table_blocks) > 0,
        "has_format_blocks": len(format_blocks) > 0,
    }


def _paragraph_normalize_meta(raw_text: str, normalized_text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "raw_text_changed_by_normalize": raw_text != normalized_text,
    }
    if raw_text != normalized_text:
        meta["raw_text_before_normalize"] = raw_text
    if "\n" in raw_text or "\r" in raw_text:
        meta["has_internal_newlines"] = True
    return meta


def _build_content_block_meta(
    para: Paragraph,
    *,
    kind: str,
    text: str,
    raw_text: str,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "style_name": safe_docx_style_name(para),
        **_paragraph_normalize_meta(raw_text, text),
    }

    if kind == "heading":
        level = infer_docx_heading_level(para)
        if level is not None:
            meta["heading_level"] = level
        heading_number, heading_text_stripped = split_heading_text(text)
        if heading_number is not None:
            meta["heading_number"] = heading_number
        if heading_number is not None and heading_text_stripped:
            meta["heading_text_stripped"] = heading_text_stripped
    elif kind == "table_caption":
        table_label = extract_docx_table_label(text)
        if table_label is not None:
            meta["table_label"] = table_label
    elif kind in {"paragraph", "list_item"}:
        refs = extract_docx_table_ref_candidates(text)
        if refs:
            meta["table_ref_candidates"] = refs

    presentation = extract_block_presentation_meta(
        para,
        style_name=meta["style_name"],
        kind=kind,
    )
    if presentation:
        meta["presentation"] = presentation

    return meta


def classify_docx_paragraph_kind(
    para: Paragraph,
    para_index: int,
    text: str,
) -> str:
    """
    Docx paragraph kind classification (v0.1.7, heuristic).

    Priority order:
    1) TOC: style name or TOC-like paragraph text (candidates, not a business decision)
    2) heading: style-name heuristic
    3) list item: style-name heuristic (List Bullet / List Number etc.) OR text-prefix heuristic
    4) table note: line-level ``^注[：:]`` / ``^Note:`` prefix
    5) table caption: standalone ``表N …`` / ``Table N …`` title line
    6) default paragraph

    Not business-level routing. No position-based front-matter fallbacks.
    Cover detection is intentionally disabled.
    """
    style_name = safe_docx_style_name(para).lower()

    if is_docx_toc_style_candidate(style_name) or is_docx_toc_candidate(text):
        return "toc"

    if is_docx_heading_style(style_name):
        return "heading"

    if is_docx_list_style(style_name) or is_docx_list_item_candidate(text):
        return "list_item"

    if is_docx_table_note_candidate(text):
        return "table_note"

    if is_docx_table_caption_candidate(text):
        return "table_caption"

    return "paragraph"


def is_docx_table_note_candidate(text: str) -> bool:
    """Heuristic: line-level table footnote (not inline narrative reference)."""
    stripped = text.strip()
    return bool(
        re.match(r"^注[：:]", stripped)
        or re.match(r"^Note\s*:", stripped, flags=re.IGNORECASE)
    )


def extract_docx_table_label(text: str) -> str | None:
    """
    Extract a standalone table label from a caption line.

    Returns None for inline references such as ``如表1所示`` or ``表1显示``.
    """
    stripped = text.strip()
    if not stripped:
        return None

    en_match = re.match(r"^(Table\s+\d+)\b", stripped, flags=re.IGNORECASE)
    if en_match:
        return re.sub(r"\s+", " ", en_match.group(1).strip())

    zh_digit_match = re.match(r"^表\s*(\d+)\s*(?:[:：]|\s)", stripped)
    if zh_digit_match:
        return f"表{zh_digit_match.group(1)}"

    zh_digit_title_match = re.match(r"^表\s*(\d+)\s+\S", stripped)
    if zh_digit_title_match:
        return f"表{zh_digit_title_match.group(1)}"

    zh_cn_match = re.match(r"^(表[一二三四五六七八九十百千万]+)\s", stripped)
    if zh_cn_match:
        return zh_cn_match.group(1)

    return None


def is_docx_table_caption_candidate(text: str) -> bool:
    """Heuristic: standalone table caption line (not inline ``见表1`` reference)."""
    return extract_docx_table_label(text) is not None


def is_docx_list_style(style_name: str) -> bool:
    """
    Heuristic: whether the paragraph style name indicates a list in docx.

    Catches "List Bullet", "List Number", "List Paragraph", "列表段落", etc.
    Checked before text-prefix heuristic so style wins when explicit.
    """
    return "list" in style_name or "列表" in style_name


def is_docx_heading_style(style_name: str) -> bool:
    """
    Docx style-name heuristic for heading detection.

    Locale-aware style names such as 'Heading' / '标题' are handled here
    because this belongs to docx extraction, not business routing.
    """
    return "heading" in style_name or "标题" in style_name


def is_docx_toc_style_candidate(style_name: str) -> bool:
    """
    Heuristic: whether the paragraph style name suggests a TOC in docx.
    """
    return "toc" in style_name or "目录" in style_name


def is_docx_toc_candidate(text: str) -> bool:
    """
    Heuristic detection of TOC-like paragraphs in docx.

    - docx-specific (style/text conventions)
    - structural only
    - not a business-level decision
    """
    text_lower = text.lower()

    if text.strip() == "目录":
        return True

    if "table of contents" in text_lower:
        return True

    # Dotted leader ending with a page number (common TOC line layout)
    # "1. Introduction ........ 5"
    # "5.2.1 临床安全性 ....... 12"
    if re.search(r"\.{2,}\s*\d+\s*$", text):
        return True

    return False


def split_heading_text(text: str) -> tuple[str | None, str]:
    """
    Split a heading like '5.2.1 临床安全性' into ('5.2.1', '临床安全性').

    Returns (None, original_text) when no leading section number is found.
    Only matches dotted-decimal prefixes (e.g. '1', '1.2', '5.2.1'), not
    free-form numbers mid-sentence.
    """
    match = re.match(r"^(\d+(?:\.\d+)*)\s+(.+)$", text.strip())
    if match:
        return match.group(1), match.group(2)
    return None, text


def is_docx_list_item_candidate(text: str) -> bool:
    """
    Heuristic: line looks like a list item in docx body text.
    """
    patterns = [
        r"^\d+\.",
        r"^\d+\)",
        r"^[A-Za-z]\.",
        r"^[A-Za-z]\)",
        r"^•",
        r"^- ",
        r"^– ",
        r"^（\d+）",
        r"^\(\d+\)",
    ]
    return any(re.match(pattern, text) for pattern in patterns)


def build_paragraph_loc(kind: str, para_index: int) -> str:
    if kind == "cover":
        return f"FRONT:COVER:P{para_index + 1}"

    if kind == "toc":
        return f"FRONT:TOC:P{para_index + 1}"

    if kind == "front_note":
        return f"FRONT:NOTE:P{para_index + 1}"

    if kind == "heading":
        return f"BODY:HDG:P{para_index + 1}"

    if kind == "list_item":
        return f"BODY:LIST:P{para_index + 1}"

    if kind == "table_caption":
        return f"BODY:TCAP:P{para_index + 1}"

    if kind == "table_note":
        return f"BODY:TNOTE:P{para_index + 1}"

    return f"BODY:P{para_index + 1}"


def safe_docx_style_name(para: Paragraph) -> str:
    """Best-effort Word style name; docx-only (python-docx Paragraph)."""
    try:
        if para.style is not None and para.style.name:
            return str(para.style.name)
    except Exception:
        pass
    return ""


def infer_docx_heading_level(para: Paragraph) -> int | None:
    """
    Best-effort heading level from docx style name (English / 标题 N patterns).
    """
    style_name = safe_docx_style_name(para).lower()

    match = re.search(r"heading\s*(\d+)", style_name)
    if match:
        return int(match.group(1))

    match = re.search(r"标题\s*(\d+)", style_name)
    if match:
        return int(match.group(1))

    return None


def extract_docx_table_ref_candidates(text: str) -> list[str]:
    """
    Extract docx-style table reference patterns.

    - heuristic only
    - may include false positives
    - downstream logic decides relevance
    """
    refs: list[str] = []

    refs.extend(re.findall(r"\bTable\s+\d+\b", text, flags=re.IGNORECASE))
    refs.extend(re.findall(r"表\s*\d+", text))

    seen: set[str] = set()
    ordered: list[str] = []
    for ref in refs:
        normalized = ref.strip()
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    return ordered


def extract_table_row_pairs(
    table: Table,
    *,
    revision_observer: RevisionTextObserver | None = None,
) -> tuple[list[list[str]], list[list[str]]]:
    """Return (visible cell text, normalized cell text) per non-empty row."""
    visible_rows: list[list[str]] = []
    normalized_rows: list[list[str]] = []
    for row in table.rows:
        visible_cells: list[str] = []
        for cell in row.cells:
            cell_text, cell_obs = extract_cell_revision_aware_text(cell)
            if revision_observer is not None:
                revision_observer.absorb(cell_obs)
            visible_cells.append(cell_text or "")
        normalized_cells = [normalize_text(value) for value in visible_cells]
        if any(normalized_cells):
            visible_rows.append(visible_cells)
            normalized_rows.append(normalized_cells)
    return visible_rows, normalized_rows


def extract_table_raw_rows(table: Table) -> list[list[str]]:
    """Return normalized cell text per row; skip rows that are entirely empty."""
    _visible_rows, normalized_rows = extract_table_row_pairs(table)
    return normalized_rows


def flatten_table_text_from_rows(rows: list[list[str]]) -> str:
    lines: list[str] = []
    for row in rows:
        cleaned = [cell for cell in row if cell]
        if cleaned:
            lines.append(" | ".join(cleaned))
    return "\n".join(lines).strip()


def flatten_table_text_from_raw_rows(raw_rows: list[list[str]]) -> str:
    """Backward-compatible alias for :func:`flatten_table_text_from_rows`."""
    return flatten_table_text_from_rows(raw_rows)


def flatten_table_text(table: Table) -> str:
    return flatten_table_text_from_rows(extract_table_raw_rows(table))


def _build_table_block_meta(
    table: Table,
    *,
    raw_rows: list[list[str]] | None = None,
) -> dict[str, Any]:
    rows = raw_rows if raw_rows is not None else extract_table_raw_rows(table)
    return {
        "row_count": len(table.rows),
        "column_count": safe_column_count(table),
        "raw_rows": rows,
        "non_empty_row_count": len(rows),
    }


def safe_column_count(table: Table) -> int:
    try:
        return len(table.columns)
    except Exception:
        if table.rows:
            return len(table.rows[0].cells)
        return 0


def join_paragraph_texts(
    paragraphs: list[Paragraph],
    *,
    revision_observer: RevisionTextObserver | None = None,
) -> tuple[str, str]:
    """Join non-empty paragraph visible/normalized text with ``\\n`` (existing gate)."""
    raw_parts: list[str] = []
    normalized_parts: list[str] = []
    for paragraph in paragraphs:
        raw, paragraph_obs = extract_paragraph_revision_aware_text(paragraph)
        if revision_observer is not None:
            revision_observer.absorb(paragraph_obs)
        raw = raw or ""
        normalized = normalize_text(raw)
        if normalized:
            raw_parts.append(raw)
            normalized_parts.append(normalized)
    return "\n".join(raw_parts).strip(), "\n".join(normalized_parts).strip()


def join_nonempty_paragraphs(paragraphs: list[Paragraph]) -> str:
    """Return normalized joined paragraph text (format-block dedup key)."""
    _raw_text, normalized_text = join_paragraph_texts(paragraphs)
    return normalized_text
