from __future__ import annotations

from collections.abc import Collection

from privacy.schemas import SensitiveEntityCandidate


def filter_uie_denied_terms(
    candidates: list[SensitiveEntityCandidate],
    denylist: Collection[str],
) -> list[SensitiveEntityCandidate]:
    """Drop UIE spans whose text is a known generic role term."""
    if not denylist:
        return candidates
    denied = set(denylist)
    return [c for c in candidates if c.original_text not in denied]
