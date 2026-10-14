"""HTTP request schemas for finding review bridge endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

FindingReviewDecisionRequest = Literal["pending", "confirmed", "ignored"]


class FindingReviewPatchRequest(BaseModel):
    flow_run_id: str
    finding_id: str
    decision: FindingReviewDecisionRequest | None = None
    resolved: bool | None = None
    marked: bool | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _require_mutation_field(self) -> FindingReviewPatchRequest:
        if (
            self.decision is None
            and self.resolved is None
            and self.marked is None
            and "note" not in self.model_fields_set
        ):
            raise ValueError(
                "at least one of decision, resolved, marked, or note must be provided"
            )
        if self.decision is not None and self.resolved is not None:
            raise ValueError("provide decision or resolved, not both")
        return self


__all__ = ["FindingReviewDecisionRequest", "FindingReviewPatchRequest"]
