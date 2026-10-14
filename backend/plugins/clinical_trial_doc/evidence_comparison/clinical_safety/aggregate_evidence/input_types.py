"""Canonical in-memory inputs for Aggregate Evidence Comparison."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from operations.evidence_comparison.contracts import EvidenceComparisonInvocation


def _require_non_empty_str(value: Any, *, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _require_typed_tuple(
    value: Any,
    *,
    field: str,
    item_type: type,
) -> None:
    if not isinstance(value, tuple) or not value:
        raise ValueError(f"{field} must be a non-empty tuple")
    for index, item in enumerate(value):
        if not isinstance(item, item_type):
            raise TypeError(f"{field}[{index}] must be a {item_type.__name__}")


def _reject_duplicate_ids(
    values: tuple[Any, ...],
    *,
    attribute: str,
    label: str | None = None,
) -> None:
    seen: set[str] = set()
    for value in values:
        identity = getattr(value, attribute)
        if identity in seen:
            raise ValueError(f"duplicate {label or attribute} {identity!r}")
        seen.add(identity)


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonSourceProvenance:
    """Producer-neutral identity for one aggregate evidence source."""

    source_artifact_id: str
    doc_id: str
    file_hash: str

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.source_artifact_id,
            field="source_artifact_id",
        )
        _require_non_empty_str(self.doc_id, field="doc_id")
        _require_non_empty_str(self.file_hash, field="file_hash")


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonSentence:
    """One ordered atomic textual evidence item from a source unit."""

    source_sentence_id: str
    text: str

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.source_sentence_id,
            field="source_sentence_id",
        )
        _require_non_empty_str(self.text, field="text")


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonUnit:
    """One ordered source unit containing canonical sentences."""

    source_unit_id: str
    sentences: tuple[AggregateEvidenceComparisonSentence, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.source_unit_id, field="source_unit_id")
        _require_typed_tuple(
            self.sentences,
            field="sentences",
            item_type=AggregateEvidenceComparisonSentence,
        )
        _reject_duplicate_ids(
            self.sentences,
            attribute="source_sentence_id",
        )


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonScope:
    """One ordered semantic scope containing canonical source units."""

    source_scope_id: str
    semantic_path: tuple[str, ...]
    units: tuple[AggregateEvidenceComparisonUnit, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.source_scope_id, field="source_scope_id")
        if not isinstance(self.semantic_path, tuple) or not self.semantic_path:
            raise ValueError("semantic_path must be a non-empty tuple")
        for index, segment in enumerate(self.semantic_path):
            _require_non_empty_str(segment, field=f"semantic_path[{index}]")
        _require_typed_tuple(
            self.units,
            field="units",
            item_type=AggregateEvidenceComparisonUnit,
        )
        _reject_duplicate_ids(self.units, attribute="source_unit_id")


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonParticipantEvidence:
    """Canonical producer-adapted evidence before a role is bound."""

    source_provenance: AggregateEvidenceComparisonSourceProvenance
    scopes: tuple[AggregateEvidenceComparisonScope, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_provenance,
            AggregateEvidenceComparisonSourceProvenance,
        ):
            raise TypeError(
                "source_provenance must be an "
                "AggregateEvidenceComparisonSourceProvenance"
            )
        _require_typed_tuple(
            self.scopes,
            field="scopes",
            item_type=AggregateEvidenceComparisonScope,
        )
        _reject_duplicate_ids(self.scopes, attribute="source_scope_id")


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonParticipant:
    """One role-bound canonical aggregate evidence participant."""

    role_id: str
    source_provenance: AggregateEvidenceComparisonSourceProvenance
    scopes: tuple[AggregateEvidenceComparisonScope, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.role_id, field="role_id")
        AggregateEvidenceComparisonParticipantEvidence(
            source_provenance=self.source_provenance,
            scopes=self.scopes,
        )


@dataclass(frozen=True, slots=True)
class AggregateEvidenceComparisonInvocation(EvidenceComparisonInvocation):
    """Ordered producer-neutral input for one Aggregate Comparison."""

    participants: tuple[AggregateEvidenceComparisonParticipant, ...]

    def __post_init__(self) -> None:
        _require_typed_tuple(
            self.participants,
            field="participants",
            item_type=AggregateEvidenceComparisonParticipant,
        )
        _reject_duplicate_ids(
            self.participants,
            attribute="role_id",
            label="participant role_id",
        )


class AggregateEvidenceComparisonSourceAdapter(Protocol):
    """Adapt one concrete source artifact into canonical participant evidence."""

    def __call__(
        self,
        source: Mapping[str, Any],
        /,
    ) -> AggregateEvidenceComparisonParticipantEvidence: ...


__all__ = [
    "AggregateEvidenceComparisonInvocation",
    "AggregateEvidenceComparisonParticipant",
    "AggregateEvidenceComparisonParticipantEvidence",
    "AggregateEvidenceComparisonScope",
    "AggregateEvidenceComparisonSentence",
    "AggregateEvidenceComparisonSourceAdapter",
    "AggregateEvidenceComparisonSourceProvenance",
    "AggregateEvidenceComparisonUnit",
]
