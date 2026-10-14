from __future__ import annotations

from collections.abc import Sequence

from privacy.detectors.base import SensitiveEntityDetector
from privacy.schemas import SensitiveEntityCandidate


class CompositeDetector:
    """Run multiple detectors and concatenate their candidate spans.

    De-duplication / overlap resolution is intentionally left to merger.
    """

    def __init__(self, detectors: Sequence[SensitiveEntityDetector]) -> None:
        self._detectors = list(detectors)

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        candidates: list[SensitiveEntityCandidate] = []

        for detector in self._detectors:
            candidates.extend(detector.detect(text))

        return candidates
