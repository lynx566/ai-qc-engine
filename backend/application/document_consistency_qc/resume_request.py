"""Product-level resume intent for a paused Document Consistency QC flow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from execution_flow.document_consistency_qc.contracts import (
    FilterJobCandidateScopeSelection,
)


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcResumeRequest:
    """Resume one paused canonical flow after Candidate Scope review."""

    flow_run_id: str
    candidate_scope_decisions_by_slot: Mapping[
        str, tuple[FilterJobCandidateScopeSelection, ...]
    ]
    project_root: Path
    participant_privacy_paths: Mapping[str, Path | None]


__all__ = [
    "DocumentConsistencyQcResumeRequest",
]
