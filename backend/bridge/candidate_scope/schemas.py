"""Pydantic transport schemas for the candidate-scope bridge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from core.metadata.document_type_diagnostic import DocumentTypeDiagnostic


class CandidateScopeJobSelection(BaseModel):
    filter_job_id: str
    anchor_block_ids: list[str] = Field(default_factory=list)


class CandidateScopeSlotDecision(BaseModel):
    slot_id: str
    candidate_scope: list[CandidateScopeJobSelection]


class CandidateScopeNextRequest(BaseModel):
    flow_run_id: str
    slot_decisions: list[CandidateScopeSlotDecision]


class CandidateScopeNextResponse(BaseModel):
    status: Literal["ready"] = "ready"
    flow_id: str
    flow_run_id: str
    flow_status: str
    paused_at_candidate_scope: bool
    paused_slot_ids: list[str] = Field(default_factory=list)
    completed: bool


class CandidateHeadingState(BaseModel):
    doc_id: str
    filter_job_id: str
    anchor_block_id: str
    title: str
    heading_path: list[str]
    level: int
    doc_order_index: int


class CandidateScopeFilterJobState(BaseModel):
    filter_job_id: str
    automatic_anchor_block_ids: list[str]
    current_anchor_block_ids: list[str]


class CandidateScopeContentDomainGroupResponse(BaseModel):
    content_domain_id: str
    display_label: str
    filter_job_ids: list[str] = Field(default_factory=list)


class CandidateScopeSlotStateResponse(BaseModel):
    slot_id: str
    doc_id: str
    filter_jobs: list[CandidateScopeFilterJobState]
    automatic_anchor_block_ids: list[str]
    current_anchor_block_ids: list[str]
    headings: list[CandidateHeadingState]
    document_type_diagnostic: DocumentTypeDiagnostic | None = None


class CandidateScopeStateResponse(BaseModel):
    flow_id: str
    flow_run_id: str
    capability_id: str
    capability_title: str
    flow_status: str
    can_resume: bool
    content_domain_groups: list[CandidateScopeContentDomainGroupResponse]
    slots: list[CandidateScopeSlotStateResponse]
