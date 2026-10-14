"""User-facing report filenames and attachment headers owned by HTTP export."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote


def qc_report_download_filename(original_file_name: str) -> str:
    """Preserve ordinary document names within a 240-byte UTF-8 filename."""
    cleaned = "".join(
        char
        for char in original_file_name
        if unicodedata.category(char) not in {"Cc", "Cf", "Cs"}
    )
    cleaned = re.sub(r'[/\\:*?"<>|]', "_", cleaned).strip().rstrip(" .")
    stem = cleaned.rsplit(".", 1)[0] if "." in cleaned else cleaned
    stem = stem.strip().strip(" .")
    if not stem:
        return "质控审查报告.pdf"
    suffix = "_质控审查报告.pdf"
    budget = 240 - len(suffix.encode("utf-8"))
    stem = stem.encode("utf-8")[:budget].decode("utf-8", errors="ignore").rstrip(" .")
    return stem + suffix


def qc_report_content_disposition(original_file_name: str) -> str:
    name = qc_report_download_filename(original_file_name)
    return (
        'attachment; filename="qc-review-report.pdf"; '
        f"filename*=UTF-8''{quote(name, safe='')}"
    )
