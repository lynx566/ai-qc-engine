from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from artifacts.privacy_mapping import (
    build_privacy_mapping_artifact,
)

from .schemas import EntityType, MaskHit

_TOKEN_INDEX_RE = re.compile(r"_(\d+)$")
def neutral_token_prefix(entity_type: EntityType) -> str:
    """Derive a domain-neutral display prefix from an entity-type identifier."""

    words = [part for part in str(entity_type).split("_") if part]
    return "".join(word[:1].upper() + word[1:].lower() for word in words) or "Entity"


def _normalize_text(text: str) -> str:
    """Normalize entity text for non-canonical store keys (strip only)."""
    return text.strip()


def mapping_store_key(
    entity_type: EntityType,
    original_text: str,
    *,
    canonical_id: str | None = None,
    parent_canonical_id: str | None = None,
) -> tuple[EntityType, str]:
    """
    Stable key for the MappingStore:

    1. ``canonical_id`` present → (entity_type, canonical_id)
    2. ``parent_canonical_id`` present → (entity_type, "<parent>::<normalized_text>")
    3. Otherwise → (entity_type, normalized_text)

    Source is intentionally excluded so the same entity detected by different
    detectors always maps to the same token.
    """
    if canonical_id:
        return (entity_type, canonical_id)
    if parent_canonical_id:
        return (entity_type, f"{parent_canonical_id}::{_normalize_text(original_text)}")
    return (entity_type, _normalize_text(original_text))


@dataclass
class MappingStore:
    """
    In-memory mapping store for semantic masking.

    Store key:
    - ``(entity_type, canonical_id)`` when ``canonical_id`` is set (registry identity)
    - ``(entity_type, original_text)`` otherwise (regex / uie / …)

    Mapping artifact rows aggregate registry hits by ``(entity_type, canonical_id, token)``
    and other hits by ``(entity_type, token, original_text)`` (see ``export_mapping_artifact``).
    """

    mapping: dict[tuple[EntityType, str], str] = field(default_factory=dict)
    counters: dict[EntityType, int] = field(default_factory=dict)
    token_prefixes: dict[str, str] = field(default_factory=dict)

    def _token_prefix(self, entity_type: EntityType) -> str:
        return self.token_prefixes.get(str(entity_type), neutral_token_prefix(entity_type))

    def _reserve_counter_for_token(self, entity_type: EntityType, token: str) -> None:
        prefix = self._token_prefix(entity_type)
        match = _TOKEN_INDEX_RE.search(token)
        if not match or not token.startswith(f"{prefix}_"):
            return
        index = int(match.group(1))
        self.counters[entity_type] = max(self.counters.get(entity_type, 0), index)

    def get_or_create_token(
        self,
        entity_type: EntityType,
        original_text: str,
        *,
        canonical_id: str | None = None,
        predefined_token: str | None = None,
        parent_canonical_id: str | None = None,
    ) -> str:
        key = mapping_store_key(
            entity_type,
            original_text,
            canonical_id=canonical_id,
            parent_canonical_id=parent_canonical_id,
        )

        if key in self.mapping:
            return self.mapping[key]

        if predefined_token:
            token = predefined_token
            self._reserve_counter_for_token(entity_type, token)
        else:
            prefix = self._token_prefix(entity_type)
            next_index = self.counters.get(entity_type, 0) + 1
            self.counters[entity_type] = next_index
            token = f"{prefix}_{next_index:03d}"

        self.mapping[key] = token
        return token

    def to_public_mapping(self) -> dict[str, str]:
        """
        Export mapping as JSON-friendly dictionary.

        Example:
        {
            "SUBJECT::张三": "Subject_001",
            "STUDY_DRUG::study_drug_001": "StudyDrug_001"
        }
        """

        return {
            f"{entity_type}::{label}": token
            for (entity_type, label), token in self.mapping.items()
        }

    def to_reverse_mapping(self) -> dict[str, str]:
        """
        Export token -> store label mapping.

        This should stay local only.
        """

        return {token: label for (_, label), token in self.mapping.items()}


def export_mapping_artifact(
    *,
    doc_id: str,
    mapping_store: MappingStore,
    mask_hits: Iterable[MaskHit],
) -> dict[str, Any]:
    """
    Build the document-level mapping.json artifact (entity summary, not spans).

    Registry hits (``canonical_id`` set) aggregate by ``(entity_type, canonical_id, token)``.
    Other hits aggregate by ``(entity_type, token, original_text)`` with
    ``original_texts: [original_text]``.
    """
    del mapping_store  # retained for compatibility with the historical shared API
    return build_privacy_mapping_artifact(doc_id=doc_id, mask_hits=mask_hits)
