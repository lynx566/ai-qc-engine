"""Neutral ESP-to-Evidence-Comparison fan-in handoff resolution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBinding,
)
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantReference,
    EvidenceComparisonParticipantRequirement,
    ProducedEvidenceSourcePreparationOutputReference,
)


class EvidenceComparisonHandoffResolutionStatus(str, Enum):
    """Structural readiness of one capability-level Comparison handoff."""

    UNBOUND = "unbound"
    INCOMPLETE = "incomplete"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class EvidenceComparisonHandoff:
    """One complete, ordered participant handoff ready for stage execution."""

    consumer_binding: EvidenceComparisonConsumerBinding
    participants: tuple[EvidenceComparisonParticipantReference, ...]


@dataclass(frozen=True, slots=True)
class EvidenceComparisonHandoffResolution:
    """Distinguishes absent installation, incomplete inputs, and readiness."""

    status: EvidenceComparisonHandoffResolutionStatus
    consumer_binding: EvidenceComparisonConsumerBinding | None
    handoff: EvidenceComparisonHandoff | None
    missing_participant_requirements: tuple[
        EvidenceComparisonParticipantRequirement, ...
    ] = ()


def resolve_evidence_comparison_handoff(
    *,
    consumer_binding: EvidenceComparisonConsumerBinding | None,
    produced_outputs: Sequence[ProducedEvidenceSourcePreparationOutputReference],
) -> EvidenceComparisonHandoffResolution:
    """Mechanically match ordered requirements to produced ESP output references."""

    produced_by_selector: dict[
        tuple[str, str], ProducedEvidenceSourcePreparationOutputReference
    ] = {}
    for index, produced in enumerate(produced_outputs):
        if not isinstance(
            produced,
            ProducedEvidenceSourcePreparationOutputReference,
        ):
            raise TypeError(
                f"produced_outputs[{index}] must be a "
                "ProducedEvidenceSourcePreparationOutputReference"
            )
        selector = (produced.slot_id, produced.semantic_module_id)
        if selector in produced_by_selector:
            raise ValueError(f"duplicate produced ESP output selector={selector!r}")
        produced_by_selector[selector] = produced

    if consumer_binding is None:
        return EvidenceComparisonHandoffResolution(
            status=EvidenceComparisonHandoffResolutionStatus.UNBOUND,
            consumer_binding=None,
            handoff=None,
        )

    if not isinstance(consumer_binding, EvidenceComparisonConsumerBinding):
        raise TypeError(
            "consumer_binding must be an EvidenceComparisonConsumerBinding or None"
        )

    missing: list[EvidenceComparisonParticipantRequirement] = []
    participants: list[EvidenceComparisonParticipantReference] = []
    for requirement in consumer_binding.participant_requirements:
        selector = (requirement.slot_id, requirement.semantic_module_id)
        produced = produced_by_selector.get(selector)
        if produced is None:
            missing.append(requirement)
            continue
        participants.append(
            EvidenceComparisonParticipantReference(
                role_id=requirement.role_id,
                slot_id=requirement.slot_id,
                semantic_module_id=requirement.semantic_module_id,
                declared_output_path=produced.declared_output_path,
            )
        )

    if missing:
        return EvidenceComparisonHandoffResolution(
            status=EvidenceComparisonHandoffResolutionStatus.INCOMPLETE,
            consumer_binding=consumer_binding,
            handoff=None,
            missing_participant_requirements=tuple(missing),
        )

    handoff = EvidenceComparisonHandoff(
        consumer_binding=consumer_binding,
        participants=tuple(participants),
    )
    return EvidenceComparisonHandoffResolution(
        status=EvidenceComparisonHandoffResolutionStatus.READY,
        consumer_binding=consumer_binding,
        handoff=handoff,
    )


__all__ = [
    "EvidenceComparisonHandoff",
    "EvidenceComparisonHandoffResolution",
    "EvidenceComparisonHandoffResolutionStatus",
    "EvidenceComparisonParticipantReference",
    "EvidenceComparisonParticipantRequirement",
    "ProducedEvidenceSourcePreparationOutputReference",
    "resolve_evidence_comparison_handoff",
]

