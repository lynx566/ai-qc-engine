"""Neutral document-consistency QC configuration contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from operations.prepare_analysis.contracts import PrepareAnalysisRequestOptions


class CandidateScopeDecisionMode(str, Enum):
    """How canonical flow proceeds after all Filter jobs complete for one slot."""

    AUTOMATIC_CONTINUE = "automatic_continue"
    PAUSE_AT_CANDIDATE_SCOPE = "pause_at_candidate_scope"


@dataclass(frozen=True)
class DocumentConsistencyQcParticipantSlot:
    """One Flow participant slot for a document-consistency QC capability."""

    slot_id: str


@dataclass(frozen=True)
class FilterJobCandidateScopeSelection:
    """Confirmed Candidate Scope heading selection for one Filter job."""

    filter_job_id: str
    anchor_block_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.filter_job_id, str) or not self.filter_job_id.strip():
            raise ValueError("filter_job_id must be a non-empty string")
        if not isinstance(self.anchor_block_ids, tuple):
            raise TypeError("anchor_block_ids must be a tuple")
        for anchor in self.anchor_block_ids:
            if not isinstance(anchor, str) or not anchor.strip():
                raise ValueError("anchor_block_ids entries must be non-empty strings")


@dataclass(frozen=True)
class DocumentConsistencyQcParticipantRunInput:
    """Formal per-participant Prepare Analysis invocation inputs."""

    prepare_analysis_request_options: PrepareAnalysisRequestOptions

    def __post_init__(self) -> None:
        if not isinstance(
            self.prepare_analysis_request_options,
            PrepareAnalysisRequestOptions,
        ):
            raise TypeError(
                "prepare_analysis_request_options must be a "
                "PrepareAnalysisRequestOptions"
            )


@dataclass(frozen=True)
class DocumentConsistencyQcCapabilityConfig:
    """Static product-entry configuration for document-consistency QC."""

    capability_id: str
    slots: tuple[DocumentConsistencyQcParticipantSlot, ...]


__all__ = [
    "CandidateScopeDecisionMode",
    "DocumentConsistencyQcCapabilityConfig",
    "DocumentConsistencyQcParticipantSlot",
    "DocumentConsistencyQcParticipantRunInput",
    "FilterJobCandidateScopeSelection",
]
