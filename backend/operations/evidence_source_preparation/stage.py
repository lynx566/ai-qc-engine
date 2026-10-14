"""Neutral stage-runtime contracts for Evidence Source Preparation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SelectedRouteOutputReference:
    """One Route output selected for downstream ESP execution."""

    route_output_kind: str
    unit_count: int
    routed_bundle_path: Path

    def __post_init__(self) -> None:
        kind = _require_non_empty_str(
            self.route_output_kind,
            field_name="route_output_kind",
        )
        object.__setattr__(self, "route_output_kind", kind)
        unit_count = _non_negative_int(self.unit_count, field_name="unit_count")
        if unit_count <= 0:
            raise ValueError("unit_count must be greater than zero")
        object.__setattr__(self, "unit_count", unit_count)
        if not isinstance(self.routed_bundle_path, Path):
            raise TypeError("routed_bundle_path must be a pathlib.Path")


def _require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")
    return value


@dataclass(frozen=True, slots=True)
class RouteStageReference:
    """Neutral reference to one completed Route stage output."""

    output_dir: Path
    run_id: str
    doc_id: str
    semantic_module_id: str
    route_counts: Mapping[str, int]
    routed_bundle_paths: Mapping[str, Path]
    routing_manifest_path: Path


@dataclass(frozen=True, slots=True)
class ProjectionInputRefRecord:
    """One contributing Filter-output projection input recorded on Route provenance."""

    filter_job_id: str
    zone_key: str
    filter_output_projection_bundle_id: str


@dataclass(frozen=True, slots=True)
class FilterJobCoverageReference:
    """Resolved Filter coverage output for one contributing filter job."""

    filter_job_id: str
    coverage_bundle_path: Path


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationUpstreamReferences:
    """Neutral upstream artifact references required by one ESP stage run."""

    block_manifest_path: Path
    doc_meta_bundle_path: Path
    analysis_bundle_path: Path
    private_audit_bundle_path: Path | None = None


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationStageContext:
    """Neutral run/output context for one ESP stage execution."""

    output_dir: Path
    run_id: str | None = None
    git_provenance: Mapping[str, str | bool | None] | None = None


class EvidenceSourcePreparationExecutionDependencies:
    """Marker base for Application-materialized ESP execution dependencies."""


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationStageInput:
    """Neutral invocation envelope for one ESP stage runtime execution."""

    route_stage: RouteStageReference
    projection_input_refs: tuple[ProjectionInputRefRecord, ...]
    filter_job_coverage_refs: tuple[FilterJobCoverageReference, ...]
    upstream: EvidenceSourcePreparationUpstreamReferences
    context: EvidenceSourcePreparationStageContext
    execution_dependencies: EvidenceSourcePreparationExecutionDependencies
    evidence_form_id: str
    selected_route_output: SelectedRouteOutputReference

    def __post_init__(self) -> None:
        from operations.evidence_source_preparation.stage_validation import (
            validate_evidence_source_preparation_stage_input,
        )

        validate_evidence_source_preparation_stage_input(self)


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationStageResult:
    """Neutral stage result recorded by Flow without inspecting domain payloads.

    ``declared_output_path`` is the sole downstream output pointer for the
    installed ESP stage execution. It references whatever artifact path the
    installed stage executor declares as its formal downstream product. Other
  formal or implementation-internal artifacts may coexist under ``output_dir``
    but must not appear as additional fields on this result type.
    """

    output_dir: Path
    run_id: str
    doc_id: str
    semantic_module_id: str
    stage_executor_id: str
    declared_output_path: Path
    run_summary_path: Path


@runtime_checkable
class EvidenceSourcePreparationStageExecutor(Protocol):
    """Installed stage-runtime boundary for one ESP operation execution."""

    def __call__(
        self,
        *,
        stage_input: EvidenceSourcePreparationStageInput,
    ) -> EvidenceSourcePreparationStageResult: ...


__all__ = [
    "EvidenceSourcePreparationExecutionDependencies",
    "EvidenceSourcePreparationStageContext",
    "EvidenceSourcePreparationStageExecutor",
    "EvidenceSourcePreparationStageInput",
    "EvidenceSourcePreparationStageResult",
    "EvidenceSourcePreparationUpstreamReferences",
    "FilterJobCoverageReference",
    "ProjectionInputRefRecord",
    "RouteStageReference",
    "SelectedRouteOutputReference",
]
