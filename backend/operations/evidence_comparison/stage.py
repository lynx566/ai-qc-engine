"""Neutral stage-runtime contracts for Evidence Comparison."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantReference,
    require_non_empty_str,
)


@dataclass(frozen=True, slots=True)
class EvidenceComparisonStageContext:
    """Neutral run/output context for one Comparison stage execution."""

    output_dir: Path
    run_id: str | None = None
    git_provenance: Mapping[str, str | bool | None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be a pathlib.Path")
        if self.run_id is not None:
            object.__setattr__(
                self,
                "run_id",
                require_non_empty_str(self.run_id, field_name="run_id"),
            )


class EvidenceComparisonExecutionDependencies:
    """Marker base for Application-materialized Comparison dependencies."""


@dataclass(frozen=True, slots=True)
class EvidenceComparisonStageInput:
    """Neutral invocation envelope for one Comparison stage execution."""

    participants: tuple[EvidenceComparisonParticipantReference, ...]
    context: EvidenceComparisonStageContext
    execution_dependencies: EvidenceComparisonExecutionDependencies

    def __post_init__(self) -> None:
        if not self.participants:
            raise ValueError("participants must contain at least one participant")
        seen_roles: set[str] = set()
        seen_selectors: set[tuple[str, str]] = set()
        for index, participant in enumerate(self.participants):
            if not isinstance(participant, EvidenceComparisonParticipantReference):
                raise TypeError(
                    f"participants[{index}] must be an "
                    "EvidenceComparisonParticipantReference"
                )
            selector = (participant.slot_id, participant.semantic_module_id)
            if participant.role_id in seen_roles:
                raise ValueError(f"duplicate participant role_id={participant.role_id!r}")
            if selector in seen_selectors:
                raise ValueError(f"duplicate participant selector={selector!r}")
            seen_roles.add(participant.role_id)
            seen_selectors.add(selector)
        if not isinstance(self.context, EvidenceComparisonStageContext):
            raise TypeError("context must be an EvidenceComparisonStageContext")
        if not isinstance(
            self.execution_dependencies,
            EvidenceComparisonExecutionDependencies,
        ):
            raise TypeError(
                "execution_dependencies must be an "
                "EvidenceComparisonExecutionDependencies"
            )


@dataclass(frozen=True, slots=True)
class EvidenceComparisonStageResult:
    """Neutral result for one Comparison stage execution.

    ``declared_output_path`` references the installed stage executor's formal
    downstream product when present. For Evidence Comparison this is the
    post-finalization ``final_findings.json`` product artifact.
    """

    output_dir: Path
    run_id: str
    stage_executor_id: str
    run_status: str
    run_summary_path: Path
    declared_output_path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be a pathlib.Path")
        if not isinstance(self.run_summary_path, Path):
            raise TypeError("run_summary_path must be a pathlib.Path")
        if self.declared_output_path is not None and not isinstance(
            self.declared_output_path,
            Path,
        ):
            raise TypeError("declared_output_path must be a pathlib.Path or None")
        for field_name in ("run_id", "stage_executor_id", "run_status"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_str(getattr(self, field_name), field_name=field_name),
            )


@runtime_checkable
class EvidenceComparisonStageExecutor(Protocol):
    """Installed stage-runtime boundary for one Comparison execution."""

    def __call__(
        self,
        *,
        stage_input: EvidenceComparisonStageInput,
    ) -> EvidenceComparisonStageResult: ...


__all__ = [
    "EvidenceComparisonExecutionDependencies",
    "EvidenceComparisonStageContext",
    "EvidenceComparisonStageExecutor",
    "EvidenceComparisonStageInput",
    "EvidenceComparisonStageResult",
]
