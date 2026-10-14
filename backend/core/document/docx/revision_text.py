"""Revision-aware visible text extraction for DOCX (Final / No Markup semantics)."""

from __future__ import annotations

from dataclasses import dataclass, field

from docx.table import _Cell
from docx.text.paragraph import Paragraph

_RUN_TEXT_XPATH = "w:br | w:cr | w:noBreakHyphen | w:ptab | w:t | w:tab"

_INCLUDE_CONTAINER_TAGS = frozenset({"ins", "moveTo"})
_EXCLUDE_CONTAINER_TAGS = frozenset({"del", "moveFrom"})
_TRAVERSE_CONTAINER_TAGS = frozenset({"hyperlink"}) | _INCLUDE_CONTAINER_TAGS


@dataclass
class RevisionTextObservation:
    """Revision markup encountered while extracting canonical visible text."""

    insertions_detected: bool = False
    deletions_detected: bool = False
    moves_detected: bool = False

    def absorb(self, other: RevisionTextObservation) -> None:
        self.insertions_detected = self.insertions_detected or other.insertions_detected
        self.deletions_detected = self.deletions_detected or other.deletions_detected
        self.moves_detected = self.moves_detected or other.moves_detected


@dataclass
class RevisionTextObserver:
    """Accumulates revision observations across an Extract pass."""

    observation: RevisionTextObservation = field(default_factory=RevisionTextObservation)

    def absorb(self, other: RevisionTextObservation) -> None:
        self.observation.absorb(other)

    def to_parse_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.observation.insertions_detected:
            warnings.append("tracked_insertions_detected")
        if self.observation.deletions_detected:
            warnings.append("tracked_deletions_detected")
        if self.observation.moves_detected:
            warnings.append("tracked_moves_detected")
        return warnings


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _run_visible_text(run_el) -> str:
    return "".join(str(node) for node in run_el.xpath(_RUN_TEXT_XPATH))


def _iter_revision_visible_run_elements(container_el):
    """Yield ``w:r`` elements whose text is included in Final / No Markup output."""
    for child in container_el.iterchildren():
        local = _local_tag(child.tag)
        if local == "r":
            if _run_visible_text(child):
                yield child
            continue
        if local in _EXCLUDE_CONTAINER_TAGS:
            continue
        if local in _INCLUDE_CONTAINER_TAGS:
            yield from _iter_revision_visible_run_elements(child)
            continue
        if local in _TRAVERSE_CONTAINER_TAGS:
            yield from _iter_revision_visible_run_elements(child)


def iter_paragraph_revision_visible_run_elements(paragraph: Paragraph):
    """Yield visible ``w:r`` elements for a paragraph using Final / No Markup rules."""
    yield from _iter_revision_visible_run_elements(paragraph._p)


def _walk_revision_aware_container(container_el, observation: RevisionTextObservation) -> str:
    parts: list[str] = []
    for child in container_el.iterchildren():
        local = _local_tag(child.tag)
        if local == "r":
            parts.append(_run_visible_text(child))
            continue
        if local in _EXCLUDE_CONTAINER_TAGS:
            if local == "del":
                observation.deletions_detected = True
            else:
                observation.moves_detected = True
            continue
        if local in _INCLUDE_CONTAINER_TAGS:
            if local == "ins":
                observation.insertions_detected = True
            else:
                observation.moves_detected = True
            parts.append(_walk_revision_aware_container(child, observation))
            continue
        if local in _TRAVERSE_CONTAINER_TAGS:
            parts.append(_walk_revision_aware_container(child, observation))
    return "".join(parts)


def extract_paragraph_revision_aware_text(
    paragraph: Paragraph,
    *,
    observation: RevisionTextObservation | None = None,
) -> tuple[str, RevisionTextObservation]:
    """
    Return Final / No Markup visible text for a DOCX paragraph.

    Includes direct ``w:r``, ``w:hyperlink``, ``w:ins``, and ``w:moveTo`` content.
    Excludes ``w:del`` and ``w:moveFrom``. Comment markers and ``comments.xml`` are
    ignored.
    """
    obs = observation if observation is not None else RevisionTextObservation()
    text = _walk_revision_aware_container(paragraph._p, obs)
    return text, obs


def extract_cell_revision_aware_text(
    cell: _Cell,
    *,
    observation: RevisionTextObservation | None = None,
) -> tuple[str, RevisionTextObservation]:
    """Join paragraph-level revision-aware text for a table cell with ``\\n``."""
    obs = observation if observation is not None else RevisionTextObservation()
    parts: list[str] = []
    for paragraph in cell.paragraphs:
        paragraph_text, paragraph_obs = extract_paragraph_revision_aware_text(paragraph)
        obs.absorb(paragraph_obs)
        parts.append(paragraph_text)
    return "\n".join(parts), obs


def revision_aware_text_matches_legacy_paragraph(paragraph: Paragraph) -> bool:
    """Return True when revision-aware text equals python-docx ``Paragraph.text``."""
    revision_text, _obs = extract_paragraph_revision_aware_text(paragraph)
    legacy_text = paragraph.text or ""
    return revision_text == legacy_text
