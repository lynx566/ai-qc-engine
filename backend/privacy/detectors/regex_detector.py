from __future__ import annotations

import re
from collections.abc import Sequence

from privacy.schemas import EntityType, SensitiveEntityCandidate

RegexRule = tuple[EntityType, str, re.Pattern[str]]


class RegexDetector:
    """Rule-based detector driven by injected regex rules."""

    def __init__(self, rules: Sequence[RegexRule]) -> None:
        self._rules = list(rules)

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        candidates: list[SensitiveEntityCandidate] = []

        for entity_type, source, pattern in self._rules:
            span_group = 1 if pattern.groups else 0

            for match in pattern.finditer(text):
                original = match.group(span_group)
                start, end = match.span(span_group)

                candidates.append(
                    SensitiveEntityCandidate(
                        original_text=original,
                        entity_type=entity_type,
                        start=start,
                        end=end,
                        source=source,
                        confidence=1.0,
                    )
                )

        candidates.sort(key=lambda c: (c.start, c.end))
        return candidates
