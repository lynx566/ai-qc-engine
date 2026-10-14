"""Internal DSUR document consistency QC capability configuration."""

from __future__ import annotations

from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)

INTERNAL_DSUR_CONSISTENCY_QC = DocumentConsistencyQcCapabilityConfig(
    capability_id="internal_dsur",
    slots=(
        DocumentConsistencyQcParticipantSlot(
            slot_id="source",
        ),
    ),
)

__all__ = [
    "INTERNAL_DSUR_CONSISTENCY_QC",
]
