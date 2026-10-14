"""Internal IB document consistency QC capability configuration."""

from __future__ import annotations

from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)

INTERNAL_IB_CONSISTENCY_QC = DocumentConsistencyQcCapabilityConfig(
    capability_id="internal_ib",
    slots=(
        DocumentConsistencyQcParticipantSlot(
            slot_id="source",
        ),
    ),
)

__all__ = [
    "INTERNAL_IB_CONSISTENCY_QC",
]
