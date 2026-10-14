"""Format-agnostic helpers for navigating extracted heading blocks.

DOCX-specific heading detection lives in ``core.document.docx.handlers``; this
module only operates on normalized blocks emitted by the extract stage.
"""

from __future__ import annotations

from typing import Any


def is_heading(block: dict[str, Any]) -> bool:
    return block.get("kind") == "heading"


def get_heading_level(block: dict[str, Any]) -> int | None:
    meta = block.get("meta") or {}
    level = meta.get("heading_level")
    return level if isinstance(level, int) else None


def get_heading_text_for_match(block: dict[str, Any]) -> str:
    """
    Text for **zone matching** only (structural / original metadata).

    Resolution order:

    1. ``meta.heading_text_stripped`` — extract / legacy structural field
    2. ``block["analysis_text"]`` — prepare_analysis ``analysis_bundle``
    3. ``block["normalized_text"]`` — current Extract canonical field
    4. ``block["text"]`` — legacy Extract artifact fallback only

    Do **not** use this for LLM/tag prompts — use ``analysis_text`` from formal
    ``assessment_input`` evidence (see ``assessment_input_safety``).
    """
    meta = block.get("meta") or {}
    structural_or_analysis = meta.get("heading_text_stripped") or block.get(
        "analysis_text"
    )
    if structural_or_analysis:
        return structural_or_analysis
    if "normalized_text" in block:
        return block.get("normalized_text") or ""
    return block.get("text") or ""


def update_heading_stack(
    heading_stack: list[dict[str, Any]],
    heading_block: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return a new stack reflecting the current position in the document outline.

    Pops all headings at the same level or deeper than *heading_block*, then
    appends *heading_block*.
    """
    level = get_heading_level(heading_block)

    if level is None:
        return heading_stack

    kept = [h for h in heading_stack if (get_heading_level(h) or 999) < level]
    return kept + [heading_block]
