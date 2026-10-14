"""DOCX block-level presentation metadata extraction (Final / No Markup runs only)."""

from __future__ import annotations

import re
from typing import Any

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Length
from docx.text.paragraph import Paragraph

from core.document.docx.revision_text import iter_paragraph_revision_visible_run_elements

PresentationMeta = dict[str, Any]

_ALIGNMENT_BY_VALUE = {
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
}


def infer_toc_level_from_style_name(style_name: str) -> int | None:
    """Parse ``TOC N`` style names into a 1-based outline level.

    Standard Word styles use ``TOC 1`` … ``TOC 9``. Some localized templates
    encode the outline level in the tens digit (``TOC 11`` → 1, ``TOC 21`` → 2).
    """
    match = re.search(r"toc\s*(\d+)", style_name, flags=re.IGNORECASE)
    if not match:
        return None
    raw = int(match.group(1))
    if raw < 1:
        return None
    if raw >= 10:
        return raw // 10
    return raw


def extract_block_presentation_meta(
    para: Paragraph,
    *,
    style_name: str,
    kind: str,
) -> PresentationMeta:
    """
    Build optional ``meta.presentation`` for a paragraph-backed block.

    Returns an empty dict when no reliable presentation fields are available.
    """
    presentation: PresentationMeta = {}

    alignment = _paragraph_alignment(para)
    if alignment is not None:
        presentation["alignment"] = alignment

    first_line_indent_pt = _length_to_pt(para.paragraph_format.first_line_indent)
    if first_line_indent_pt is not None:
        presentation["indent_first_line_pt"] = first_line_indent_pt

    left_indent_pt = _length_to_pt(para.paragraph_format.left_indent)
    if left_indent_pt is not None:
        presentation["indent_left_pt"] = left_indent_pt

    line_spacing_multiple = _paragraph_line_spacing_multiple(para)
    if line_spacing_multiple is not None:
        presentation["line_spacing_multiple"] = line_spacing_multiple

    space_before_pt = _length_to_pt(para.paragraph_format.space_before)
    if space_before_pt is not None:
        presentation["space_before_pt"] = space_before_pt

    space_after_pt = _length_to_pt(para.paragraph_format.space_after)
    if space_after_pt is not None:
        presentation["space_after_pt"] = space_after_pt

    visible_runs = list(iter_paragraph_revision_visible_run_elements(para))
    font_size_pt = _rollup_uniform([_run_explicit_font_size_pt(run) for run in visible_runs])
    if font_size_pt is not None:
        presentation["font_size_pt"] = font_size_pt

    bold = _rollup_uniform([_run_explicit_bool(run, "w:b") for run in visible_runs])
    if bold is not None:
        presentation["bold"] = bold

    italic = _rollup_uniform([_run_explicit_bool(run, "w:i") for run in visible_runs])
    if italic is not None:
        presentation["italic"] = italic

    if kind == "toc":
        toc_level = infer_toc_level_from_style_name(style_name)
        if toc_level is not None:
            presentation["toc_level"] = toc_level

    return presentation


def _paragraph_alignment(para: Paragraph) -> str | None:
    alignment = para.paragraph_format.alignment
    if alignment is None:
        return None
    return _ALIGNMENT_BY_VALUE.get(alignment)


def _length_to_pt(value: Length | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value.pt), 4)
    except (AttributeError, TypeError, ValueError):
        return None


def _paragraph_line_spacing_multiple(para: Paragraph) -> float | None:
    paragraph_format = para.paragraph_format
    if paragraph_format.line_spacing_rule != WD_LINE_SPACING.MULTIPLE:
        return None
    line_spacing = paragraph_format.line_spacing
    if line_spacing is None:
        return None
    try:
        return round(float(line_spacing), 4)
    except (TypeError, ValueError):
        return None


def _run_explicit_font_size_pt(run_el) -> float | None:
    run_properties = run_el.find(qn("w:rPr"))
    if run_properties is None:
        return None
    size_el = run_properties.find(qn("w:sz"))
    if size_el is None:
        return None
    raw_value = size_el.get(qn("w:val"))
    if raw_value is None:
        return None
    try:
        return round(int(raw_value) / 2.0, 4)
    except ValueError:
        return None


def _run_explicit_bool(run_el, tag: str) -> bool | None:
    run_properties = run_el.find(qn("w:rPr"))
    if run_properties is None:
        return None
    flag_el = run_properties.find(qn(tag))
    if flag_el is None:
        return None
    raw_value = flag_el.get(qn("w:val"))
    if raw_value is None:
        return True
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "on"}:
        return True
    if normalized in {"0", "false", "off"}:
        return False
    return None


def _rollup_uniform(values: list[Any | None]) -> Any | None:
    if not values:
        return None
    if any(value is None for value in values):
        return None
    first = values[0]
    if all(value == first for value in values):
        return first
    return None
