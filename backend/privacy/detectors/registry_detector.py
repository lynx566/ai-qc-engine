from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from privacy.schemas import EntityType, SensitiveEntityCandidate


@dataclass(frozen=True)
class RegistryEntry:
    entity_type: EntityType
    canonical_id: str
    token: str
    aliases: tuple[str, ...]
    parent_canonical_id: str | None = None


class RegistryDetector:
    """
    Exact phrase hits from structured registry entries (canonical id + stable token).

    Longer aliases are searched first so shorter substrings do not steal spans.
    """

    def __init__(self, entries: Sequence[RegistryEntry]) -> None:
        flat: list[tuple[str, RegistryEntry]] = []
        for entry in entries:
            for alias in entry.aliases:
                stripped = alias.strip()
                if stripped:
                    flat.append((stripped, entry))
        self._entries = sorted(flat, key=lambda item: len(item[0]), reverse=True)

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        candidates: list[SensitiveEntityCandidate] = []

        for alias, entry in self._entries:
            start = 0
            while True:
                pos = text.find(alias, start)
                if pos == -1:
                    break
                end = pos + len(alias)
                candidates.append(
                    SensitiveEntityCandidate(
                        original_text=text[pos:end],
                        entity_type=entry.entity_type,
                        start=pos,
                        end=end,
                        source="registry",
                        confidence=1.0,
                        canonical_id=entry.canonical_id,
                        predefined_token=entry.token,
                        parent_canonical_id=entry.parent_canonical_id,
                    )
                )
                start = pos + 1

        candidates.sort(key=lambda c: c.start)
        return candidates
