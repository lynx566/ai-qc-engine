"""Canonical projected-sentence contract for Filter-output projection artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from operations.filter_output_projection.contracts import (
    CanonicalSourceRef,
    ProjectedSentence,
    ProjectedSource,
)

_FORBIDDEN_PROJECTED_SENTENCE_KEYS = frozenset(
    {
        "role",
        "kind",
        "sentence_order",
        "canonical_sentence_id",
        "source_item_index",
        "char_start",
        "char_end",
    }
)

_LEGACY_PAYLOAD_BODY_KEYS = frozenset(
    {
        "analysis_text",
        "substantive_items",
        "context_items",
    }
)


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def declared_source_block_ids(source: ProjectedSource) -> frozenset[str]:
    """Return block ids declared on projected-source provenance refs."""

    block_ids: set[str] = set()
    for ref in source.source_refs:
        block_id = ref.refs.get("block_id")
        if isinstance(block_id, str) and block_id.strip():
            block_ids.add(block_id.strip())
    return frozenset(block_ids)


def serialize_projected_sentence(sentence: ProjectedSentence) -> dict[str, str]:
    return {
        "sentence_id": sentence.sentence_id,
        "text": sentence.text,
        "source_block_id": sentence.source_block_id,
    }


def deserialize_projected_sentence(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> ProjectedSentence:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be a mapping")
    forbidden = _FORBIDDEN_PROJECTED_SENTENCE_KEYS.intersection(raw)
    if forbidden:
        raise ValueError(
            f"{label} must not contain forbidden keys: {sorted(forbidden)!r}"
        )
    return ProjectedSentence(
        sentence_id=_require_non_empty_str(raw.get("sentence_id"), field=f"{label}.sentence_id"),
        text=raw.get("text") if isinstance(raw.get("text"), str) else "",
        source_block_id=_require_non_empty_str(
            raw.get("source_block_id"),
            field=f"{label}.source_block_id",
        ),
    )


def validate_projected_sentences(
    sentences: Sequence[ProjectedSentence],
    *,
    label: str,
) -> None:
    """Validate one projected-source canonical sentence collection."""

    if not isinstance(sentences, Sequence) or isinstance(sentences, (str, bytes)):
        raise TypeError(f"{label}.sentences must be a sequence")
    if not sentences:
        raise ValueError(f"{label}.sentences must be non-empty")
    seen_ids: set[str] = set()
    for index, sentence in enumerate(sentences):
        if not isinstance(sentence, ProjectedSentence):
            raise TypeError(f"{label}.sentences[{index}] must be a ProjectedSentence")
        if sentence.sentence_id in seen_ids:
            raise ValueError(
                f"{label}.sentences contains duplicate sentence_id "
                f"{sentence.sentence_id!r}"
            )
        seen_ids.add(sentence.sentence_id)


def validate_projected_source_sentences(
    source: ProjectedSource,
    *,
    label: str = "projected_source",
) -> None:
    """Validate canonical sentences and source-block integrity for one source."""

    validate_projected_sentences(source.sentences, label=label)
    declared_blocks = declared_source_block_ids(source)
    if not declared_blocks:
        raise ValueError(f"{label} must declare at least one source_ref block_id")
    for index, sentence in enumerate(source.sentences):
        if sentence.source_block_id not in declared_blocks:
            raise ValueError(
                f"{label}.sentences[{index}].source_block_id={sentence.source_block_id!r} "
                f"is not declared in source_refs: {sorted(declared_blocks)!r}"
            )


def reject_legacy_projected_source_payload(payload: Mapping[str, Any], *, label: str) -> None:
    """Reject retired 0.2.0 body keys from persisted projected-source payload."""

    if not isinstance(payload, Mapping):
        raise TypeError(f"{label}.payload must be a mapping")
    legacy = _LEGACY_PAYLOAD_BODY_KEYS.intersection(payload)
    if legacy:
        raise ValueError(
            f"{label}.payload must not contain legacy body keys: {sorted(legacy)!r}"
        )


def projected_sentence_from_item(
    *,
    sentence_id: str,
    text: str,
    source_block_id: str,
) -> ProjectedSentence:
    return ProjectedSentence(
        sentence_id=sentence_id,
        text=text,
        source_block_id=source_block_id,
    )


def block_level_source_ref(*, block_id: str, source_group: str) -> CanonicalSourceRef:
    return CanonicalSourceRef(
        refs={
            "block_id": block_id,
            "source_group": source_group,
        }
    )


def source_refs_for_sentences(
    sentences: Sequence[ProjectedSentence],
    *,
    source_group_by_block_id: Mapping[str, str],
    primary_block_id: str | None = None,
) -> tuple[CanonicalSourceRef, ...]:
    """Build deduplicated block-level source refs in first-seen sentence order.

    When ``primary_block_id`` is set (Overview assembled sources), that block's
    ref is emitted first for stable document-order anchoring.
    """

    refs: list[CanonicalSourceRef] = []
    seen: set[str] = set()
    if primary_block_id and primary_block_id.strip():
        primary = primary_block_id.strip()
        source_group = str(source_group_by_block_id.get(primary) or "blocks")
        refs.append(block_level_source_ref(block_id=primary, source_group=source_group))
        seen.add(primary)
    for sentence in sentences:
        block_id = sentence.source_block_id
        if block_id in seen:
            continue
        seen.add(block_id)
        source_group = str(source_group_by_block_id.get(block_id) or "blocks")
        refs.append(block_level_source_ref(block_id=block_id, source_group=source_group))
    return tuple(refs)


__all__ = [
    "block_level_source_ref",
    "declared_source_block_ids",
    "deserialize_projected_sentence",
    "projected_sentence_from_item",
    "reject_legacy_projected_source_payload",
    "serialize_projected_sentence",
    "source_refs_for_sentences",
    "validate_projected_sentences",
    "validate_projected_source_sentences",
]
