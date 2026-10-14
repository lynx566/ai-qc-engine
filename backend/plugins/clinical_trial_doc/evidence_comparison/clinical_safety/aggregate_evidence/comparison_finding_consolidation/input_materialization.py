"""Materialize generic Comparison Finding Consolidation inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_findings,
    validate_aggregate_comparison_evidence,
)

SOURCE_CONTENT_HEADING = "## Source Content"
CONCLUSIONS_HEADING = "## Conclusions"


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationFindingProjection:
    """One job-final finding projected into the consolidation alias namespace."""

    conclusion_alias: str
    finding_id: str
    frozen_job_index: int
    comparison_mode_id: str
    label: str
    conclusion: str
    source_sentence_aliases: tuple[str, ...]

    def to_alias_mapping_record(self) -> dict[str, Any]:
        return {
            "conclusion_alias": self.conclusion_alias,
            "finding_id": self.finding_id,
            "frozen_job_index": self.frozen_job_index,
            "comparison_mode_id": self.comparison_mode_id,
            "label": self.label,
            "conclusion": self.conclusion,
            "source_sentence_aliases": list(self.source_sentence_aliases),
        }


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationInput:
    """Typed provider input derived from homogeneous final job rows."""

    comparison_mode_id: str
    finding_projections: tuple[
        ComparisonFindingConsolidationFindingProjection, ...
    ]
    source_content_text: str
    conclusions_text: str
    user_input_text: str

    @property
    def finding_count(self) -> int:
        return len(self.finding_projections)

    @property
    def alias_mapping(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            projection.to_alias_mapping_record()
            for projection in self.finding_projections
        )


def _render_aggregate_source_content(
    aggregate_comparison_evidence: Mapping[str, Any],
) -> str:
    participants: list[str] = []
    for participant in aggregate_comparison_evidence["participants"]:
        scopes: list[str] = []
        for scope in participant["scopes"]:
            units: list[str] = []
            for unit in scope["units"]:
                sentences = [
                    f"- {sentence['text']} [{sentence['sentence_alias']}]"
                    for sentence in unit["sentences"]
                ]
                units.append(
                    "\n".join((f"Unit {unit['unit_alias']}", *sentences))
                )
            heading = " / ".join(scope["heading_path"])
            scopes.append(
                "\n".join(
                    (
                        f"Scope: {heading} [{scope['scope_alias']}]",
                        *units,
                    )
                )
            )
        participants.append(
            "\n\n".join((f"Participant: {participant['role_id']}", *scopes))
        )
    return "\n\n".join(participants)


def _validate_selected_rows(
    *,
    comparison_mode_id: str,
    selected_job_final_rows: Sequence[Mapping[str, Any]],
) -> None:
    if not isinstance(comparison_mode_id, str) or not comparison_mode_id.strip():
        raise ValueError("comparison_mode_id must be a non-empty string")
    if not isinstance(selected_job_final_rows, Sequence) or isinstance(
        selected_job_final_rows, (str, bytes)
    ):
        raise TypeError("selected_job_final_rows must be a sequence")
    if not selected_job_final_rows:
        return
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected_job_final_rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"selected_job_final_rows[{index}] must be an object")
        rows.append(dict(row))
    build_findings(jobs=rows)
    for index, row in enumerate(rows):
        if row["comparison_mode_id"] != comparison_mode_id:
            raise ValueError(
                f"selected_job_final_rows[{index}].comparison_mode_id must match "
                f"comparison_mode_id {comparison_mode_id!r}"
            )


def materialize_comparison_finding_consolidation_projections(
    *,
    comparison_mode_id: str,
    selected_job_final_rows: Sequence[Mapping[str, Any]],
) -> tuple[ComparisonFindingConsolidationFindingProjection, ...]:
    """Project authoritative selected rows into the ordered C-alias namespace."""

    _validate_selected_rows(
        comparison_mode_id=comparison_mode_id,
        selected_job_final_rows=selected_job_final_rows,
    )
    projections: list[ComparisonFindingConsolidationFindingProjection] = []
    for row in selected_job_final_rows:
        for finding in row["findings"]:
            sequence = len(projections) + 1
            projections.append(
                ComparisonFindingConsolidationFindingProjection(
                    conclusion_alias=f"C{sequence:03d}",
                    finding_id=finding["finding_id"],
                    frozen_job_index=row["frozen_job_index"],
                    comparison_mode_id=row["comparison_mode_id"],
                    label=finding["label"],
                    conclusion=finding["conclusion"],
                    source_sentence_aliases=tuple(
                        finding["source_sentence_aliases"]
                    ),
                )
            )
    return tuple(projections)


def _render_conclusions(
    projections: Sequence[ComparisonFindingConsolidationFindingProjection],
) -> str:
    rendered: list[str] = []
    for projection in projections:
        rendered.append(
            "\n".join(
                (
                    f"Conclusion {projection.conclusion_alias}",
                    f"- `conclusion`: {projection.conclusion}",
                    "- `source_sentence_aliases`: "
                    + ", ".join(projection.source_sentence_aliases),
                )
            )
        )
    return "\n\n".join(rendered)


def materialize_comparison_finding_consolidation_input(
    *,
    comparison_mode_id: str,
    aggregate_comparison_evidence: Mapping[str, Any],
    selected_job_final_rows: Sequence[Mapping[str, Any]],
) -> ComparisonFindingConsolidationInput:
    """Render one mode's already-selected homogeneous job-final finding rows."""

    validate_aggregate_comparison_evidence(aggregate_comparison_evidence)
    projections = materialize_comparison_finding_consolidation_projections(
        comparison_mode_id=comparison_mode_id,
        selected_job_final_rows=selected_job_final_rows,
    )
    source_content_text = _render_aggregate_source_content(
        aggregate_comparison_evidence
    )
    conclusions_text = _render_conclusions(projections)
    user_input_text = (
        f"{SOURCE_CONTENT_HEADING}\n{source_content_text}\n\n"
        f"{CONCLUSIONS_HEADING}\n{conclusions_text}"
    )
    return ComparisonFindingConsolidationInput(
        comparison_mode_id=comparison_mode_id,
        finding_projections=projections,
        source_content_text=source_content_text,
        conclusions_text=conclusions_text,
        user_input_text=user_input_text,
    )


__all__ = [
    "CONCLUSIONS_HEADING",
    "SOURCE_CONTENT_HEADING",
    "ComparisonFindingConsolidationFindingProjection",
    "ComparisonFindingConsolidationInput",
    "materialize_comparison_finding_consolidation_input",
    "materialize_comparison_finding_consolidation_projections",
]
