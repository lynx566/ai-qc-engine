"""DSUR ↔ Updated IB cross document consistency QC capability configuration."""

from __future__ import annotations

from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)

DSUR_UPDATED_IB_CONSISTENCY_QC = DocumentConsistencyQcCapabilityConfig(
    capability_id="dsur_updated_ib",
    slots=(
        DocumentConsistencyQcParticipantSlot(
            slot_id="source_a",
        ),
        DocumentConsistencyQcParticipantSlot(
            slot_id="source_b",
        ),
    ),
)

__all__ = [
    "DSUR_UPDATED_IB_CONSISTENCY_QC",
]
