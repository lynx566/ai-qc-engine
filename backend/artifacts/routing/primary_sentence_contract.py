"""Route persisted artifact primary sentence / routed TU body contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PRIMARY_ROUTED_SENTENCE_KEYS = frozenset({"sentence_id", "text", "source_block_id"})
_FORBIDDEN_PRIMARY_SENTENCE_KEYS = frozenset(
    {
        "kind",
        "role",
        "heading_path",
        "sentence_order",
        "canonical_sentence_id",
        "char_start",
        "char_end",
        "source_item_index",
    }
)
_RETIRED_ROUTED_BODY_DUPLICATE_KEYS = frozenset(
    {
        "candidate_sentences",
        "candidate_text",
        "source_sentence_ids",
        "context_sentences",
    }
)


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def build_text_unit_sentences(
    primary_sentences: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize routed primary body sentences for persisted text units."""

    return [
        {
            "sentence_id": str(sentence["sentence_id"]),
            "text": str(sentence["text"]),
            "source_block_id": str(sentence["source_block_id"]),
        }
        for sentence in primary_sentences
    ]


def validate_primary_sentence_shape(
    sentence: Mapping[str, Any],
    *,
    sentence_path: str,
) -> None:
    """Validate one routed primary sentence has the allowed persisted shape."""

    if not isinstance(sentence, Mapping):
        raise TypeError(f"{sentence_path} must be an object")
    extra = set(sentence) - PRIMARY_ROUTED_SENTENCE_KEYS
    forbidden = extra & _FORBIDDEN_PRIMARY_SENTENCE_KEYS
    if forbidden:
        raise ValueError(
            f"{sentence_path} must not include compatibility-only keys: {sorted(forbidden)!r}"
        )
    if extra - _FORBIDDEN_PRIMARY_SENTENCE_KEYS:
        raise ValueError(f"{sentence_path} has unexpected keys: {sorted(extra)!r}")
    _require_str(sentence.get("sentence_id"), field=f"{sentence_path}.sentence_id")
    _require_str(sentence.get("text"), field=f"{sentence_path}.text")
    _require_str(
        sentence.get("source_block_id"),
        field=f"{sentence_path}.source_block_id",
    )


def validate_text_unit_body_consistency(
    unit: Mapping[str, Any],
    *,
    unit_path: str,
) -> None:
    """Validate routed primary ``sentences[]`` body contract."""

    if unit.get("unit_kind") != "text_unit":
        return

    for retired_key in _RETIRED_ROUTED_BODY_DUPLICATE_KEYS:
        if retired_key in unit:
            raise ValueError(
                f"{unit_path} must not include retired routed body field {retired_key!r}"
            )

    sentences = unit.get("sentences")
    if sentences is None:
        return

    if not isinstance(sentences, list):
        raise TypeError(f"{unit_path}.sentences must be a list")

    seen_sentence_ids: set[str] = set()
    for index, sentence in enumerate(sentences):
        sentence_path = f"{unit_path}.sentences[{index}]"
        if not isinstance(sentence, dict):
            raise TypeError(f"{sentence_path} must be an object")
        validate_primary_sentence_shape(sentence, sentence_path=sentence_path)
        sentence_id = str(sentence["sentence_id"])
        if sentence_id in seen_sentence_ids:
            raise ValueError(
                f"{unit_path}.sentences contains duplicate sentence_id {sentence_id!r}"
            )
        seen_sentence_ids.add(sentence_id)


def routed_body_text_from_sentences(
    sentences: Sequence[Mapping[str, Any]],
    *,
    source_stage: str | None = None,
) -> str:
    """Render canonical routed TU body text from primary ``sentences[]``."""

    texts = [str(sentence.get("text") or "") for sentence in sentences]
    if not texts:
        return ""
    if str(source_stage or "") == "overview_decompose":
        return "\n".join(texts)
    return "".join(texts)


__all__ = [
    "PRIMARY_ROUTED_SENTENCE_KEYS",
    "build_text_unit_sentences",
    "routed_body_text_from_sentences",
    "validate_primary_sentence_shape",
    "validate_text_unit_body_consistency",
]
