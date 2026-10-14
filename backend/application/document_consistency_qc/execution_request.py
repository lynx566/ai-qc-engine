"""Product-level normalized execution intent for Document Consistency QC."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from execution_flow.document_consistency_qc import CandidateScopeDecisionMode
from runtime.document_source_binding import DocumentIntakeSourceBinding


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcExecutionRequest:
    """Normalized processing intent for one Document Consistency QC execution."""

    capability_id: str
    project_root: Path
    participant_inputs: Mapping[str, DocumentIntakeSourceBinding]
    participant_privacy_paths: Mapping[str, Path | None]
    source_language: str
    candidate_scope_decision_mode: CandidateScopeDecisionMode = field(
        default=CandidateScopeDecisionMode.AUTOMATIC_CONTINUE,
    )

    def __post_init__(self) -> None:
        for slot_id, value in self.participant_inputs.items():
            if not isinstance(value, DocumentIntakeSourceBinding):
                raise TypeError(
                    f"participant_inputs[{slot_id!r}] must be a "
                    "DocumentIntakeSourceBinding"
                )


__all__ = [
    "DocumentConsistencyQcExecutionRequest",
]
