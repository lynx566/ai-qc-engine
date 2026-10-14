"""Internal CSR document consistency QC capability configuration."""

from __future__ import annotations

from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)

INTERNAL_CSR_CONSISTENCY_QC = DocumentConsistencyQcCapabilityConfig(
    capability_id="internal_csr",
    slots=(
        DocumentConsistencyQcParticipantSlot(
            slot_id="source",
        ),
    ),
)

__all__ = [
    "INTERNAL_CSR_CONSISTENCY_QC",
]
