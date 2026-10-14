from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateShiftConfig:
    offset_days: int


_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_ISO_DATE_FULL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATE_RANGE_FULL_RE = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2})/(?P<end>\d{4}-\d{2}-\d{2})$"
)
_ISO_DATE_OPEN_END_RE = re.compile(r"^(?P<start>\d{4}-\d{2}-\d{2})/$")
_ISO_DATE_OPEN_START_RE = re.compile(r"^/(?P<end>\d{4}-\d{2}-\d{2})$")
_MASKED_DATE_TOKEN_RE = re.compile(r"^Date_\d+$")
_DOT_DATE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
_SLASH_DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})")
_CN_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

_DATE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_ISO_DATE_RE, "iso"),
    (_DOT_DATE_RE, "dot"),
    (_SLASH_DATE_RE, "slash"),
    (_CN_DATE_RE, "cn"),
)


def _shift_date(y: int, m: int, d: int, offset_days: int) -> date | None:
    try:
        return date(y, m, d) + timedelta(days=offset_days)
    except ValueError:
        return None


def _format_iso(shifted: date) -> str:
    return shifted.isoformat()


def _format_dot(shifted: date) -> str:
    return f"{shifted.year:04d}.{shifted.month:02d}.{shifted.day:02d}"


def _format_slash(shifted: date) -> str:
    return f"{shifted.year:04d}/{shifted.month:02d}/{shifted.day:02d}"


def _format_cn(shifted: date) -> str:
    return f"{shifted.year}年{shifted.month}月{shifted.day}日"


def _shift_matched_date(
    matched_text: str,
    *,
    kind: str,
    offset_days: int,
) -> str | None:
    pattern_by_kind = {
        "iso": _ISO_DATE_RE,
        "dot": _DOT_DATE_RE,
        "slash": _SLASH_DATE_RE,
        "cn": _CN_DATE_RE,
    }
    pattern = pattern_by_kind.get(kind)
    if pattern is None:
        return None
    match = pattern.fullmatch(matched_text)
    if match is None:
        return None
    y, m, d = (int(match.group(i)) for i in range(1, 4))
    shifted = _shift_date(y, m, d, offset_days)
    if shifted is None:
        return None
    if kind == "iso":
        return _format_iso(shifted)
    if kind == "dot":
        return _format_dot(shifted)
    if kind == "slash":
        return _format_slash(shifted)
    return _format_cn(shifted)


def shift_iso_date(value: str, offset_days: int) -> str | None:
    """Shift one canonical ISO date (``YYYY-MM-DD``) by *offset_days*."""
    if offset_days == 0 or not _ISO_DATE_FULL_RE.match(value):
        return value if offset_days == 0 else None
    return _shift_matched_date(value, kind="iso", offset_days=offset_days)


def shift_iso_date_value(value: str | None, offset_days: int) -> str | None:
    """
    Shift structured ISO date values used outside free text.

    Supports single dates, closed ``YYYY-MM-DD/YYYY-MM-DD`` ranges, open-ended
    ``YYYY-MM-DD/`` and open-start ``/YYYY-MM-DD`` intervals, preserves masked
    tokens like ``Date_001``, and leaves unparseable values unchanged.
    """
    if value is None:
        return None
    if offset_days == 0:
        return value
    if _MASKED_DATE_TOKEN_RE.match(value):
        return value

    range_match = _ISO_DATE_RANGE_FULL_RE.match(value)
    if range_match is not None:
        shifted_start = shift_iso_date(range_match.group("start"), offset_days)
        shifted_end = shift_iso_date(range_match.group("end"), offset_days)
        if shifted_start is None or shifted_end is None:
            return value
        return f"{shifted_start}/{shifted_end}"

    open_end_match = _ISO_DATE_OPEN_END_RE.match(value)
    if open_end_match is not None:
        shifted_start = shift_iso_date(open_end_match.group("start"), offset_days)
        if shifted_start is None:
            return value
        return f"{shifted_start}/"

    open_start_match = _ISO_DATE_OPEN_START_RE.match(value)
    if open_start_match is not None:
        shifted_end = shift_iso_date(open_start_match.group("end"), offset_days)
        if shifted_end is None:
            return value
        return f"/{shifted_end}"

    if _ISO_DATE_FULL_RE.match(value):
        shifted = shift_iso_date(value, offset_days)
        return shifted if shifted is not None else value

    return value


class DateShifter:
    def __init__(self, config: DateShiftConfig) -> None:
        self.config = config

    def iter_shift_spans(
        self, text: str
    ) -> list[tuple[int, int, str, str]]:
        """
        Return ``(start, end, original, shifted)`` for each date in ``text``.

        Spans are non-overlapping and sorted by ``start``.
        """
        spans: list[tuple[int, int, str, str, int]] = []
        for pattern, kind in _DATE_PATTERNS:
            for match in pattern.finditer(text):
                original = match.group(0)
                shifted = _shift_matched_date(
                    original,
                    kind=kind,
                    offset_days=self.config.offset_days,
                )
                if shifted is None or shifted == original:
                    continue
                spans.append(
                    (match.start(), match.end(), original, shifted, match.start())
                )
        if not spans:
            return []
        spans.sort(key=lambda item: (item[0], item[4]))
        merged: list[tuple[int, int, str, str]] = []
        for start, end, original, shifted, _ in spans:
            if merged and start < merged[-1][1]:
                continue
            merged.append((start, end, original, shifted))
        return merged

    def shift_text(self, text: str) -> str:
        spans = self.iter_shift_spans(text)
        if not spans:
            return text
        out = text
        for start, end, _original, shifted in sorted(
            spans, key=lambda item: item[0], reverse=True
        ):
            out = out[:start] + shifted + out[end:]
        return out
