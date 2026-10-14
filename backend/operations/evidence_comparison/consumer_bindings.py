"""Neutral Application consumer bindings for Evidence Comparison."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantRequirement,
    require_non_empty_str,
)
from operations.evidence_comparison.stage import EvidenceComparisonStageExecutor


@dataclass(frozen=True, slots=True)
class EvidenceComparisonConsumerBinding:
    """Application-declared participant composition for one capability."""

    capability_id: str
    participant_requirements: tuple[EvidenceComparisonParticipantRequirement, ...]
    stage_executor: EvidenceComparisonStageExecutor

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capability_id",
            require_non_empty_str(self.capability_id, field_name="capability_id"),
        )
        if not self.participant_requirements:
            raise ValueError(
                "participant_requirements must contain at least one requirement"
            )
        seen_roles: set[str] = set()
        seen_selectors: set[tuple[str, str]] = set()
        for index, requirement in enumerate(self.participant_requirements):
            if not isinstance(requirement, EvidenceComparisonParticipantRequirement):
                raise TypeError(
                    f"participant_requirements[{index}] must be an "
                    "EvidenceComparisonParticipantRequirement"
                )
            selector = (requirement.slot_id, requirement.semantic_module_id)
            if requirement.role_id in seen_roles:
                raise ValueError(
                    f"duplicate participant role_id={requirement.role_id!r}"
                )
            if selector in seen_selectors:
                raise ValueError(f"duplicate participant selector={selector!r}")
            seen_roles.add(requirement.role_id)
            seen_selectors.add(selector)
        if not callable(self.stage_executor):
            raise TypeError("stage_executor must be callable")


@dataclass(frozen=True, slots=True)
class EvidenceComparisonConsumerBindings:
    """Maps a capability id to at most one installed Comparison consumer."""

    bindings: Mapping[str, EvidenceComparisonConsumerBinding]

    def __post_init__(self) -> None:
        for key, binding in self.bindings.items():
            capability_key = require_non_empty_str(key, field_name="bindings key")
            if not isinstance(binding, EvidenceComparisonConsumerBinding):
                raise TypeError(
                    f"bindings[{capability_key!r}] must be an "
                    "EvidenceComparisonConsumerBinding"
                )
            if binding.capability_id != capability_key:
                raise ValueError(
                    "binding.capability_id must match bindings key: "
                    f"{binding.capability_id!r} != {capability_key!r}"
                )

    def resolve_consumer_binding(
        self,
        capability_id: str,
    ) -> EvidenceComparisonConsumerBinding | None:
        normalized = require_non_empty_str(capability_id, field_name="capability_id")
        return self.bindings.get(normalized)


__all__ = [
    "EvidenceComparisonConsumerBinding",
    "EvidenceComparisonConsumerBindings",
]

