from __future__ import annotations

from pathlib import Path

KNOWN_DOCUMENT_LANGUAGES = frozenset({"zh", "en"})


def infer_language_from_source_path(path: Path | str) -> str | None:
    """
    Infer document language from a path segment (nearest ancestor first).

    Convention: ``samples/docx/zh/extract/ib_extract_heading_001.docx`` → ``"zh"``;
    legacy ``.../zh/ib_001.docx`` still works. Returns ``None`` when no
    known language segment appears in the path.
    """
    for part in reversed(Path(path).parts[:-1]):
        seg = part.strip().lower()
        if seg in KNOWN_DOCUMENT_LANGUAGES:
            return seg
    return None
