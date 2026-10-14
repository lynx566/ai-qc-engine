"""Neutral Route-to-ESP handoff resolution for Flow dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
)
from operations.projected_source_route.consumer_selection import (
    select_produced_route_output,
)
from operations.projected_source_route.output_contract import (
    RouteOutputDescriptor,
    build_produced_route_outputs,
)


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationRouteHandoff:
    """Resolved consumer requirements and matched Route output for one ESP run."""

    consumer_binding: EvidenceSourcePreparationConsumerBinding
    selected_route_output: RouteOutputDescriptor


def resolve_evidence_source_preparation_route_handoff(
    *,
    route_counts: Mapping[str, int],
    routed_bundle_paths: Mapping[str, Path | str],
    consumer_binding: EvidenceSourcePreparationConsumerBinding | None,
) -> EvidenceSourcePreparationRouteHandoff | None:
    """Match one installed consumer binding to a produced Route output, if present."""

    if consumer_binding is None:
        return None

    produced_route_outputs = build_produced_route_outputs(
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
    )
    selection = select_produced_route_output(
        produced_route_outputs=produced_route_outputs,
        required_route_output_kind=consumer_binding.required_route_output_kind,
    )
    if selection is None:
        return None

    return EvidenceSourcePreparationRouteHandoff(
        consumer_binding=consumer_binding,
        selected_route_output=selection.selected_route_output,
    )


__all__ = [
    "EvidenceSourcePreparationRouteHandoff",
    "resolve_evidence_source_preparation_route_handoff",
]
