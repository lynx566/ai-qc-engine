from __future__ import annotations

from privacy.schemas import SensitiveEntityCandidate


class LocalModelDetector:
    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        """
        Future local model detector.

        This class should call UIE / Qwen / HanLP later.
        For now, it returns no candidates.
        """
        return []
