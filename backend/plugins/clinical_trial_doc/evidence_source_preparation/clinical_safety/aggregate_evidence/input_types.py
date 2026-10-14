"""In-memory input types for clinical-trial-doc evidence source preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm.providers.base import LLMProvider
from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationInvocation,
)
from operations.evidence_source_preparation.stage import ProjectionInputRefRecord


@dataclass(frozen=True)
class ProjectedCoverageByFilterJob:
    """Per-contributor coverage bundles for projected multi-source fan-in."""

    bundles_by_filter_job_id: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class EvidenceSourcePreparationUpstreamInput:
    block_manifest: dict[str, Any]
    doc_meta_bundle: dict[str, Any]
    analysis_bundle: dict[str, Any]
    coverage_bundle: dict[str, Any] | None = None
    private_audit_bundle: dict[str, Any] | None = None
    date_shift_offset_days: int | None = None
    date_shift_offset_source: str | None = None
    projected_coverage_by_filter_job: ProjectedCoverageByFilterJob | None = None
    projection_input_refs: tuple[ProjectionInputRefRecord, ...] = ()
    semantic_module_id: str | None = None


@dataclass(frozen=True)
class AggregateEvidenceRouteArtifactsInput:
    route_counts: dict[str, int]
    aggregate_bundle: dict[str, Any]
    routing_manifest: dict[str, Any]
    source_routed_unit_bundle_filename: str
    routing_manifest_filename: str


@dataclass(frozen=True)
class AggregateEvidenceExecutionInput(EvidenceSourcePreparationInvocation):
    """Canonical in-memory input for unified aggregate-evidence execution."""

    upstream: EvidenceSourcePreparationUpstreamInput
    route_artifacts: AggregateEvidenceRouteArtifactsInput
    evidence_form_id: str
    assessment_profile_name: str | None = None
    llm_mode: str = "mock"
    llm_profile: str | None = None
    provider: LLMProvider | None = None
    llm_execution_config: dict[str, Any] | None = None
    allow_api_parse_fallback: bool = False
