"""Generic date and date-range normalization utilities."""

from __future__ import annotations

import re

__all__ = [
    "normalize_date_value",
    "normalize_date_range_value",
]

_MASKED_DATE_RE = re.compile(r"^Date_\d+$")
_CN_DATE_RE = re.compile(r"^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日$")

_ISO_RANGE_RE = re.compile(r"^(\d{4}-\d{1,2}-\d{1,2})-(\d{4}-\d{1,2}-\d{1,2})$")
_DOT_RANGE_RE = re.compile(r"^(\d{4}\.\d{1,2}\.\d{1,2})-(\d{4}\.\d{1,2}\.\d{1,2})$")
_SLASH_RANGE_RE = re.compile(r"^(\d{4}/\d{1,2}/\d{1,2})-(\d{4}/\d{1,2}/\d{1,2})$")
_CN_RANGE_RE = re.compile(r"^(\d{4}年\d{1,2}月\d{1,2}日)-(\d{4}年\d{1,2}月\d{1,2}日)$")
_MASKED_RANGE_RE = re.compile(r"^(Date_\d+)-(Date_\d+)$")
_CANONICAL_RANGE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})$")

_RANGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    _ISO_RANGE_RE,
    _DOT_RANGE_RE,
    _SLASH_RANGE_RE,
    _CN_RANGE_RE,
    _MASKED_RANGE_RE,
)


def _format_iso_date_parts(year: str, month: str, day: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _parse_single_date(value: str) -> str | None:
    stripped = value.strip()
    if not stripped:
        return None

    match = _CN_DATE_RE.match(stripped)
    if match:
        return _format_iso_date_parts(match.group(1), match.group(2), match.group(3))

    normalized = stripped.replace("/", "-")
    parts = re.split(r"[-.]", normalized)
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = parts
        if len(year) == 4:
            return _format_iso_date_parts(year, month, day)

    return None


def normalize_date_value(value: str | None) -> str | None:
    """Normalize a single date to ``YYYY-MM-DD``, or return the input unchanged."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value
    if _MASKED_DATE_RE.match(stripped):
        return stripped

    parsed = _parse_single_date(stripped)
    return parsed if parsed is not None else value


def normalize_date_range_value(value: str | None) -> str | None:
    """Normalize a date range to ``YYYY-MM-DD/YYYY-MM-DD``, or return unchanged."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value
    if _CANONICAL_RANGE_RE.match(stripped):
        return stripped

    for pattern in _RANGE_PATTERNS:
        match = pattern.match(stripped)
        if match is None:
            continue
        start = normalize_date_value(match.group(1))
        end = normalize_date_value(match.group(2))
        if start is None or end is None:
            return value
        return f"{start}/{end}"

    return value
