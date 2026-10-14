from __future__ import annotations

from .schemas import MergedEntity, SensitiveEntityCandidate

# Overlap resolution priority: higher wins.
SOURCE_PRIORITY: dict[str, int] = {
    "registry": 4,
    "regex": 3,
    "uie": 1,
}

# Tiebreaker when source priority is equal and spans are identical but entity
# types differ (e.g. UIE produces both SUBJECT and INVESTIGATOR for same text).
ENTITY_TYPE_PRIORITY: dict[str, int] = {
    "STUDY_DRUG": 10,
    "GENERIC_NAME": 9,
    "TARGET": 8,
    "SPONSOR": 7,
    "PROTOCOL_ID": 6,
    "SITE": 5,
    "INVESTIGATOR": 5,
    "SUBJECT": 4,
    "RECORD_ID": 3,
    "DATE": 2,
    "OTHER_CCI": 1,
}


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def candidate_rank(
    candidate: SensitiveEntityCandidate,
) -> tuple[int, int, int, float]:
    """
    Higher is better.

    Priority order:
    1. Longer span
    2. Higher source priority
    3. Higher entity_type priority (tiebreaker for same-span, different types)
    4. Higher confidence
    """
    span_len = candidate.end - candidate.start
    source_priority = SOURCE_PRIORITY.get(candidate.source, 0)
    entity_priority = ENTITY_TYPE_PRIORITY.get(candidate.entity_type, 0)
    return span_len, source_priority, entity_priority, candidate.confidence


def _collect_sources(candidates: list[SensitiveEntityCandidate]) -> list[str]:
    """Deduplicated sources from a candidate group, sorted highest priority first."""
    unique = {c.source for c in candidates if c.source}
    if not unique:
        return ["unknown"]
    return sorted(unique, key=lambda s: (-SOURCE_PRIORITY.get(s, 0), s))


def merge_candidates(
    candidates: list[SensitiveEntityCandidate],
) -> list[MergedEntity]:
    """
    Merge overlapping sensitive entity candidates into a non-overlapping list.

    Three-phase resolution:

    Phase 1 — Exact same span + same entity_type:
        Keep the highest-ranked candidate; aggregate *all* sources into the
        resulting MergedEntity.  This preserves multi-detector provenance when
        e.g. both ``regex`` and ``uie`` fire on the same span with the same type.

    Phase 2 — Exact same span, different entity_types:
        Select the highest-ranked entity_type using ``ENTITY_TYPE_PRIORITY`` as
        tiebreaker after source priority.  Prevents the same span from producing
        both e.g. SUBJECT and INVESTIGATOR hits.

    Phase 3 — Partially overlapping spans:
        Greedy longest-first selection (existing behaviour).
    """

    # Phase 1: group by (start, end, entity_type) → pick best, collect all sources
    span_type_groups: dict[
        tuple[int, int, str], list[SensitiveEntityCandidate]
    ] = {}
    for c in candidates:
        span_type_groups.setdefault((c.start, c.end, c.entity_type), []).append(c)

    per_span_type: list[tuple[SensitiveEntityCandidate, list[str]]] = []
    for group in span_type_groups.values():
        best = max(group, key=candidate_rank)
        sources = _collect_sources(group)
        per_span_type.append((best, sources))

    # Phase 2: group by (start, end) → pick best entity_type
    span_groups: dict[
        tuple[int, int], list[tuple[SensitiveEntityCandidate, list[str]]]
    ] = {}
    for item in per_span_type:
        span_groups.setdefault((item[0].start, item[0].end), []).append(item)

    span_resolved: list[tuple[SensitiveEntityCandidate, list[str]]] = []
    for items in span_groups.values():
        best_item = max(items, key=lambda x: candidate_rank(x[0]))
        span_resolved.append(best_item)

    # Phase 3: greedy overlap resolution for non-exact overlapping spans
    selected: list[tuple[SensitiveEntityCandidate, list[str]]] = []
    for item in sorted(span_resolved, key=lambda x: candidate_rank(x[0]), reverse=True):
        c = item[0]
        if not any(
            spans_overlap(c.start, c.end, kept[0].start, kept[0].end)
            for kept in selected
        ):
            selected.append(item)

    selected.sort(key=lambda x: x[0].start)

    return [
        MergedEntity(
            original_text=c.original_text,
            entity_type=c.entity_type,
            start=c.start,
            end=c.end,
            sources=sources,
            confidence=c.confidence,
            canonical_id=c.canonical_id,
            predefined_token=c.predefined_token,
            parent_canonical_id=c.parent_canonical_id,
        )
        for c, sources in selected
    ]
