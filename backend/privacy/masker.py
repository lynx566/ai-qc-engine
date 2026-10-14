from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .date_shift import DateShifter
from .schemas import MaskedBlock, MaskHit, MergedEntity


class MappingStore(Protocol):
    def get_or_create_token(
        self,
        entity_type: str,
        original_text: str,
        *,
        canonical_id: str | None = None,
        predefined_token: str | None = None,
        parent_canonical_id: str | None = None,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class _MaskOperation:
    start: int
    end: int
    replacement: str
    hit: MaskHit


def _entities_for_mask(entities: list[MergedEntity]) -> list[MergedEntity]:
    """DATE is shifted via date_shift spans, not tokenized here."""
    return [e for e in entities if e.entity_type != "DATE"]


def _build_mask_operations(
    raw_text: str,
    entities: list[MergedEntity],
    mapping_store: MappingStore,
    *,
    date_shifter: DateShifter | None = None,
) -> list[_MaskOperation]:
    operations: list[_MaskOperation] = []

    for entity in _entities_for_mask(entities):
        span_text = raw_text[entity.start : entity.end]
        if span_text != entity.original_text:
            raise ValueError(
                f"Span mismatch: expected {entity.original_text!r}, "
                f"got {span_text!r} at [{entity.start}:{entity.end}]"
            )
        token = mapping_store.get_or_create_token(
            entity_type=entity.entity_type,
            original_text=entity.original_text,
            canonical_id=entity.canonical_id,
            predefined_token=entity.predefined_token,
            parent_canonical_id=entity.parent_canonical_id,
        )
        operations.append(
            _MaskOperation(
                start=entity.start,
                end=entity.end,
                replacement=token,
                hit=MaskHit(
                    original_text=entity.original_text,
                    token=token,
                    entity_type=entity.entity_type,
                    original_start=entity.start,
                    original_end=entity.end,
                    source=entity.sources[0] if entity.sources else "unknown",
                    canonical_id=entity.canonical_id,
                    parent_canonical_id=entity.parent_canonical_id,
                    sources=tuple(entity.sources),
                ),
            )
        )

    if date_shifter is not None:
        for start, end, original, shifted in date_shifter.iter_shift_spans(raw_text):
            operations.append(
                _MaskOperation(
                    start=start,
                    end=end,
                    replacement=shifted,
                    hit=MaskHit(
                        original_text=original,
                        token=shifted,
                        entity_type="DATE",
                        original_start=start,
                        original_end=end,
                        source="date_shift",
                        sources=("date_shift",),
                        shift_days=date_shifter.config.offset_days,
                    ),
                )
            )

    operations.sort(key=lambda op: op.start, reverse=True)
    return operations


def mask_text(
    raw_text: str,
    entities: list[MergedEntity],
    mapping_store: MappingStore,
    *,
    date_shifter: DateShifter | None = None,
) -> tuple[str, list[MaskHit]]:
    """
    Mask raw_text by replacing entity spans and shifting dates.

    All replacements use ``raw_text`` coordinates and apply right-to-left so
    earlier spans stay addressable.
    """
    operations = _build_mask_operations(
        raw_text,
        entities,
        mapping_store,
        date_shifter=date_shifter,
    )
    if not operations:
        return raw_text, []

    masked_text = raw_text
    mask_hits: list[MaskHit] = []
    for op in operations:
        span_text = raw_text[op.start : op.end]
        if op.hit.entity_type == "DATE":
            if span_text != op.hit.original_text:
                raise ValueError(
                    f"Date span mismatch: expected {op.hit.original_text!r}, "
                    f"got {span_text!r} at [{op.start}:{op.end}]"
                )
        masked_text = (
            masked_text[: op.start] + op.replacement + masked_text[op.end :]
        )
        mask_hits.append(op.hit)

    mask_hits.reverse()
    return masked_text, mask_hits


def mask_block(
    block_id: str,
    raw_text: str,
    entities: list[MergedEntity],
    mapping_store: MappingStore,
    *,
    date_shifter: DateShifter | None = None,
) -> MaskedBlock:
    masked_text, mask_hits = mask_text(
        raw_text=raw_text,
        entities=entities,
        mapping_store=mapping_store,
        date_shifter=date_shifter,
    )

    return MaskedBlock(
        block_id=block_id,
        original_text=raw_text,
        masked_text=masked_text,
        mask_hits=mask_hits,
    )
