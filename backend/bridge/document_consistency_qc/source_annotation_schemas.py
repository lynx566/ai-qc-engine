"""HTTP request schemas for source annotation bridge endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SourceSentenceAnchorRequest(BaseModel):
    slot_id: str
    doc_id: str
    block_id: str
    sentence_id: str


class SourceTextRangeRequest(BaseModel):
    start_offset: int
    end_offset: int


class SourceAnnotationCreateRequest(BaseModel):
    flow_run_id: str
    anchor: SourceSentenceAnchorRequest
    range: SourceTextRangeRequest | None = None
    kind: str | None = None
    content: str | None = None
    replacement_text: str | None = None


class SourceAnnotationUpdateRequest(BaseModel):
    flow_run_id: str
    annotation_id: str
    content: str | None = None
    replacement_text: str | None = None


__all__ = [
    "SourceAnnotationCreateRequest",
    "SourceAnnotationUpdateRequest",
    "SourceSentenceAnchorRequest",
    "SourceTextRangeRequest",
]
