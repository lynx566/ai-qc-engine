"""Neutral participant identities for ESP-to-Comparison handoff."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


@dataclass(frozen=True, slots=True)
class EvidenceComparisonParticipantRequirement:
    """One Application-declared participant selector and opaque role."""

    role_id: str
    slot_id: str
    semantic_module_id: str

    def __post_init__(self) -> None:
        for field_name in ("role_id", "slot_id", "semantic_module_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_str(getattr(self, field_name), field_name=field_name),
            )


@dataclass(frozen=True, slots=True)
class ProducedEvidenceSourcePreparationOutputReference:
    """One neutral ESP declared output available to Comparison."""

    slot_id: str
    semantic_module_id: str
    declared_output_path: Path

    def __post_init__(self) -> None:
        for field_name in ("slot_id", "semantic_module_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_str(getattr(self, field_name), field_name=field_name),
            )
        if not isinstance(self.declared_output_path, Path):
            raise TypeError("declared_output_path must be a pathlib.Path")


@dataclass(frozen=True, slots=True)
class EvidenceComparisonParticipantReference:
    """One resolved participant passed to a Comparison stage runtime."""

    role_id: str
    slot_id: str
    semantic_module_id: str
    declared_output_path: Path

    def __post_init__(self) -> None:
        for field_name in ("role_id", "slot_id", "semantic_module_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_str(getattr(self, field_name), field_name=field_name),
            )
        if not isinstance(self.declared_output_path, Path):
            raise TypeError("declared_output_path must be a pathlib.Path")


__all__ = [
    "EvidenceComparisonParticipantReference",
    "EvidenceComparisonParticipantRequirement",
    "ProducedEvidenceSourcePreparationOutputReference",
]

