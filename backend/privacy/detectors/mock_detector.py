from __future__ import annotations

from privacy.schemas import EntityType, SensitiveEntityCandidate

_MOCK_ENTITIES: list[tuple[str, EntityType]] = [
    ("张三", "SUBJECT"),
    ("VT8802", "STUDY_DRUG"),
]


class MockDetector:
    """Development / test detector with fixed terms."""

    def __init__(
        self,
        entities: list[tuple[str, EntityType]] | None = None,
    ) -> None:
        self._entities = list(entities if entities is not None else _MOCK_ENTITIES)

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        candidates: list[SensitiveEntityCandidate] = []

        for term, entity_type in self._entities:
            start = 0
            while True:
                pos = text.find(term, start)
                if pos == -1:
                    break
                candidates.append(
                    SensitiveEntityCandidate(
                        original_text=term,
                        entity_type=entity_type,
                        start=pos,
                        end=pos + len(term),
                        source="mock",
                        confidence=1.0,
                    )
                )
                start = pos + len(term)

        candidates.sort(key=lambda c: c.start)
        return candidates
