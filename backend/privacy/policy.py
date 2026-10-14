from __future__ import annotations

from collections.abc import Iterable

from privacy.schemas import SensitiveEntityCandidate


def filter_candidates_by_profile(
    candidates: Iterable[SensitiveEntityCandidate],
    *,
    entity_types_to_mask: frozenset[str],
    entity_types_to_keep: frozenset[str],
) -> list[SensitiveEntityCandidate]:
    out: list[SensitiveEntityCandidate] = []

    for c in candidates:
        if c.entity_type in entity_types_to_keep:
            continue

        if c.entity_type in entity_types_to_mask:
            out.append(c)

    return out
