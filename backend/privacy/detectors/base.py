from __future__ import annotations

from typing import Protocol

from privacy.schemas import SensitiveEntityCandidate


class SensitiveEntityDetector(Protocol):
    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        ...
