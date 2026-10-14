"""Semantic binding contract for clinical-safety aggregate-evidence ESP phases."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

HeadingScopeEligibilityEntriesBuilder = Callable[..., list[dict[str, Any]]]


@dataclass(frozen=True)
class AggregateEvidencePrepareSemanticBinding:
    """Injected prepare profile/instructions for one clinical-safety aggregate strategy."""

    assessment_profile_ref: str
    instructions: str


@dataclass(frozen=True)
class AggregateEvidenceSemanticBinding:
    """Installed semantic strategy for clinical-safety aggregate-evidence prepare + eligibility."""

    prepare: AggregateEvidencePrepareSemanticBinding
    build_heading_scope_eligibility_entries: HeadingScopeEligibilityEntriesBuilder

    def build_eligibility_entries(
        self,
        *,
        scope_assessments: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        return self.build_heading_scope_eligibility_entries(
            scope_assessments=scope_assessments,
        )
