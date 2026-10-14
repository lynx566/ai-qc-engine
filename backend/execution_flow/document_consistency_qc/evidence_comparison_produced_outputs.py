"""Rebuild ESP produced-output references from persisted FlowRun provenance."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from operations.evidence_comparison.participants import (
    ProducedEvidenceSourcePreparationOutputReference,
)

from execution_flow.document_consistency_qc.execution_provenance import (
    FlowRunExecution,
    FlowRunSlotProvenance,
)


def collect_produced_evidence_source_preparation_outputs_from_slot_provenance(
    slot_provenance: Sequence[FlowRunSlotProvenance],
) -> tuple[ProducedEvidenceSourcePreparationOutputReference, ...]:
    """Collect ESP declared outputs from persisted FlowRun slot provenance."""

    produced: list[ProducedEvidenceSourcePreparationOutputReference] = []
    for slot in slot_provenance:
        modules = slot.route_semantic_modules or ()
        for module in modules:
            if not module.evidence_source_preparation_invoked:
                continue
            declared_path_raw = module.evidence_source_preparation_declared_output_path
            if not declared_path_raw:
                raise ValueError(
                    f"slot {slot.slot_id!r} semantic_module "
                    f"{module.semantic_module_id!r} invoked ESP without "
                    "evidence_source_preparation_declared_output_path"
                )
            declared_path = Path(declared_path_raw)
            if not declared_path.is_file():
                raise ValueError(
                    f"ESP declared output must exist for slot {slot.slot_id!r}: "
                    f"{declared_path}"
                )
            produced.append(
                ProducedEvidenceSourcePreparationOutputReference(
                    slot_id=slot.slot_id,
                    semantic_module_id=module.semantic_module_id,
                    declared_output_path=declared_path,
                )
            )
    return tuple(produced)


def collect_produced_evidence_source_preparation_outputs_from_flow_execution(
    execution: FlowRunExecution,
) -> tuple[ProducedEvidenceSourcePreparationOutputReference, ...]:
    """Collect ESP declared outputs from one loaded FlowRun execution."""

    return collect_produced_evidence_source_preparation_outputs_from_slot_provenance(
        execution.slot_provenance
    )


__all__ = [
    "collect_produced_evidence_source_preparation_outputs_from_flow_execution",
    "collect_produced_evidence_source_preparation_outputs_from_slot_provenance",
]
