from __future__ import annotations

import re

# Zero-width characters (U+200B..U+200D) and BOM (U+FEFF).
_ZW_BOM_RE = re.compile(r"[\u200B-\u200D\uFEFF]")

# One or more whitespace characters (including tabs, newlines after prior steps).
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """
    General-purpose Unicode normalization for plain-text strings.

    Removes invisible artifacts that frequently appear in text extracted from
    documents (DOCX, PDF) or copied from web sources, then collapses whitespace.

    Steps applied in order:
    1. Strip zero-width characters (U+200B–U+200D) and BOM (U+FEFF).
    2. Remove soft hyphens (U+00AD).
    3. Replace non-breaking spaces (U+00A0) with regular spaces.
    4. Map en-dash (U+2013) to ASCII hyphen (em-dash U+2014 is preserved).
    5. Collapse consecutive whitespace to a single space and strip edges.

    Returns an empty string for falsy input.
    """
    if not text:
        return ""

    text = _ZW_BOM_RE.sub("", text)
    text = text.replace("\u00AD", "")
    text = text.replace("\xa0", " ")
    text = text.replace("\u2013", "-")
    text = _WHITESPACE_RE.sub(" ", text)

    return text.strip()
