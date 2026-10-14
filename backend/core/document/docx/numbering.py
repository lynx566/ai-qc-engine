"""Word automatic heading numbering recovery for DOCX extract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

_SUPPORTED_NUM_FMTS = frozenset({"decimal", "decimalZero", "upperRoman", "lowerRoman"})


@dataclass(frozen=True)
class _LevelDefinition:
    start: int
    num_fmt: str
    lvl_text: str


@dataclass
class NumberingDefinitions:
    """Parsed numbering.xml definitions needed for heading prefix recovery."""

    num_to_abstract: dict[int, int]
    abstract_levels: dict[int, dict[int, _LevelDefinition]]
    level_overrides: dict[int, dict[int, _LevelDefinition]]

    @classmethod
    def from_document(cls, doc: DocxDocument) -> NumberingDefinitions | None:
        try:
            numbering_part = doc.part.numbering_part
        except (AttributeError, KeyError, NotImplementedError):
            return None
        root = numbering_part._element
        if root is None:
            return None
        return cls._from_numbering_element(root)

    @classmethod
    def _from_numbering_element(cls, root: Any) -> NumberingDefinitions:
        num_to_abstract: dict[int, int] = {}
        abstract_levels: dict[int, dict[int, _LevelDefinition]] = {}
        level_overrides: dict[int, dict[int, _LevelDefinition]] = {}

        for abstract in root.findall(qn("w:abstractNum")):
            abstract_id = int(abstract.get(qn("w:abstractNumId")))
            levels: dict[int, _LevelDefinition] = {}
            for lvl in abstract.findall(qn("w:lvl")):
                ilvl = int(lvl.get(qn("w:ilvl")))
                levels[ilvl] = _parse_level_definition(lvl)
            abstract_levels[abstract_id] = levels

        for num in root.findall(qn("w:num")):
            num_id = int(num.get(qn("w:numId")))
            abstract_id_el = num.find(qn("w:abstractNumId"))
            if abstract_id_el is None:
                continue
            abstract_id = int(abstract_id_el.get(qn("w:val")))
            num_to_abstract[num_id] = abstract_id
            overrides: dict[int, _LevelDefinition] = {}
            for override in num.findall(qn("w:lvlOverride")):
                ilvl = int(override.get(qn("w:ilvl")))
                lvl_el = override.find(qn("w:lvl"))
                if lvl_el is not None:
                    overrides[ilvl] = _parse_level_definition(lvl_el)
                else:
                    start_el = override.find(qn("w:startOverride"))
                    if start_el is not None:
                        base = abstract_levels.get(abstract_id, {}).get(ilvl)
                        if base is not None:
                            overrides[ilvl] = _LevelDefinition(
                                start=int(start_el.get(qn("w:val"))),
                                num_fmt=base.num_fmt,
                                lvl_text=base.lvl_text,
                            )
            if overrides:
                level_overrides[num_id] = overrides

        return cls(
            num_to_abstract=num_to_abstract,
            abstract_levels=abstract_levels,
            level_overrides=level_overrides,
        )

    def level_definition(self, num_id: int, ilvl: int) -> _LevelDefinition | None:
        override = self.level_overrides.get(num_id, {}).get(ilvl)
        if override is not None:
            return override
        abstract_id = self.num_to_abstract.get(num_id)
        if abstract_id is None:
            return None
        return self.abstract_levels.get(abstract_id, {}).get(ilvl)


def _parse_level_definition(lvl: Any) -> _LevelDefinition:
    start_el = lvl.find(qn("w:start"))
    fmt_el = lvl.find(qn("w:numFmt"))
    text_el = lvl.find(qn("w:lvlText"))
    start = int(start_el.get(qn("w:val"))) if start_el is not None else 1
    num_fmt = fmt_el.get(qn("w:val")) if fmt_el is not None else "decimal"
    lvl_text = text_el.get(qn("w:val")) if text_el is not None else "%1"
    return _LevelDefinition(start=start, num_fmt=num_fmt, lvl_text=lvl_text)


@dataclass
class HeadingNumberingState:
    """Document-level counters for multilevel automatic heading numbering."""

    definitions: NumberingDefinitions | None
    counters: dict[int, list[int]] = field(default_factory=dict)

    @classmethod
    def from_document(cls, doc: DocxDocument) -> HeadingNumberingState:
        return cls(definitions=NumberingDefinitions.from_document(doc))

    def advance_and_format(self, num_id: int, ilvl: int) -> str | None:
        if self.definitions is None:
            return None
        level_def = self.definitions.level_definition(num_id, ilvl)
        if level_def is None:
            return None
        if level_def.num_fmt not in _SUPPORTED_NUM_FMTS:
            return None
        counts = self._counts_for(num_id, ilvl)
        return _format_lvl_text(level_def.lvl_text, counts[: ilvl + 1], level_def.num_fmt)

    def _counts_for(self, num_id: int, ilvl: int) -> list[int]:
        current = self.counters.setdefault(num_id, [])
        while len(current) <= ilvl:
            idx = len(current)
            level_def = self.definitions.level_definition(num_id, idx) if self.definitions else None
            initial = level_def.start if level_def is not None else 1
            current.append(initial - 1)
        current[ilvl] += 1
        for level in range(ilvl + 1, len(current)):
            level_def = self.definitions.level_definition(num_id, level) if self.definitions else None
            initial = level_def.start if level_def is not None else 1
            current[level] = initial - 1
        return current


def resolve_heading_num_pr(para: Paragraph) -> tuple[int, int] | None:
    """Return (numId, ilvl) from paragraph or inherited style chain."""
    direct = _read_num_pr(para._p.pPr)
    if direct is not None:
        return direct
    style = para.style
    visited: set[str] = set()
    while style is not None:
        style_id = str(getattr(style, "style_id", "") or "")
        if style_id in visited:
            break
        if style_id:
            visited.add(style_id)
        element = getattr(style, "element", None)
        if element is not None:
            inherited = _read_num_pr(element.pPr)
            if inherited is not None:
                return inherited
        base = getattr(style, "base_style", None)
        if base is style:
            break
        style = base
    return None


def resolve_heading_display_prefix(
    para: Paragraph,
    *,
    state: HeadingNumberingState,
) -> str | None:
    """Resolve the displayed numbering prefix for a heading paragraph."""
    resolved = resolve_heading_num_pr(para)
    if resolved is None:
        return None
    num_id, ilvl = resolved
    prefix = state.advance_and_format(num_id, ilvl)
    if prefix is None:
        return None
    return prefix


def prepend_heading_number_if_needed(
    para: Paragraph,
    text: str,
    *,
    state: HeadingNumberingState,
) -> str:
    """Prepend Word automatic numbering when absent from paragraph text."""
    prefix = resolve_heading_display_prefix(para, state=state)
    if not prefix:
        return text
    if _heading_text_has_prefix(text, prefix):
        return text
    separator = "" if prefix.endswith((" ", "\t")) else " "
    return f"{prefix}{separator}{text}"


def _read_num_pr(p_pr: Any) -> tuple[int, int] | None:
    if p_pr is None:
        return None
    num_pr = p_pr.numPr
    if num_pr is None:
        return None
    num_id_el = num_pr.numId
    ilvl_el = num_pr.ilvl
    if num_id_el is None:
        return None
    num_id = int(num_id_el.val)
    ilvl = int(ilvl_el.val) if ilvl_el is not None else 0
    return num_id, ilvl


def _format_lvl_text(lvl_text: str, counts: list[int], num_fmt: str) -> str:
    rendered = lvl_text
    for index, count in enumerate(counts, start=1):
        token = f"%{index}"
        rendered = rendered.replace(token, _format_counter(count, num_fmt))
    if "%" in rendered:
        return ""
    return rendered


def _format_counter(value: int, num_fmt: str) -> str:
    if num_fmt == "decimalZero":
        return str(value).zfill(2)
    if num_fmt == "upperRoman":
        return _to_roman(value).upper()
    if num_fmt == "lowerRoman":
        return _to_roman(value).lower()
    return str(value)


def _to_roman(value: int) -> str:
    pairs = [
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
    ]
    remaining = value
    parts: list[str] = []
    for amount, symbol in pairs:
        while remaining >= amount:
            parts.append(symbol)
            remaining -= amount
    return "".join(parts) or "0"


def _heading_text_has_prefix(text: str, prefix: str) -> bool:
    stripped_text = text.lstrip()
    stripped_prefix = prefix.rstrip()
    if not stripped_prefix:
        return False
    if not stripped_text.startswith(stripped_prefix):
        return False
    if len(stripped_text) == len(stripped_prefix):
        return True
    next_char = stripped_text[len(stripped_prefix)]
    return next_char in {" ", "\t", "\u3000", ".", "、", "．"}


__all__ = [
    "HeadingNumberingState",
    "prepend_heading_number_if_needed",
    "resolve_heading_display_prefix",
    "resolve_heading_num_pr",
]
