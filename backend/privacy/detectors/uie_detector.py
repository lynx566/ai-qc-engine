from __future__ import annotations

from collections.abc import Collection
from typing import Any

from privacy.detectors.uie_filters import filter_uie_denied_terms
from privacy.schemas import SensitiveEntityCandidate


class UIEDetector:
    def __init__(
        self,
        schema_to_entity_type: dict[str, str],
        *,
        min_confidence: float = 0.5,
        denylist: Collection[str] | None = None,
    ) -> None:
        from paddlenlp import Taskflow

        self.schema_to_entity_type = schema_to_entity_type
        self.min_confidence = min_confidence
        self.denylist = frozenset(denylist or ())
        self._ie = Taskflow(
            "information_extraction",
            schema=list(schema_to_entity_type.keys()),
            device_id=-1,
        )

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        raw_result: list[dict[str, Any]] = self._ie(text)

        candidates: list[SensitiveEntityCandidate] = []

        if not raw_result:
            return candidates

        item = raw_result[0]

        for schema_name, matches in item.items():
            entity_type = self.schema_to_entity_type.get(schema_name)
            if entity_type is None:
                continue

            for match in matches:
                entity_text = match.get("text")
                start = match.get("start")
                end = match.get("end")
                probability = match.get("probability", 0.0)
                if float(probability) < self.min_confidence:
                    continue

                if entity_text is None or start is None or end is None:
                    continue

                if text[start:end] != entity_text:
                    continue

                candidates.append(
                    SensitiveEntityCandidate(
                        original_text=entity_text,
                        entity_type=entity_type,
                        start=start,
                        end=end,
                        source="uie",
                        confidence=float(probability),
                    )
                )

        return filter_uie_denied_terms(candidates, self.denylist)
