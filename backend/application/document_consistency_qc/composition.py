"""System-neutral composition contract for Document Consistency QC."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.metadata.schemas import MetadataProfile
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcCapabilityConfig,
)
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionFacade,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.registry import (
    resolve_filter_output_projection_job as _resolve_filter_output_projection_job,
)

FilterOutputProjectionFacadeBuilder = Callable[
    ...,
    FilterOutputProjectionFacade,
]
from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBindings,
)
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
    EvidenceSourcePreparationConsumerBindings,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from operations.projected_source_route.contracts import ProjectedSourceRouteExecutor

PrepareRequestOptionsLoader = Callable[[Path | None], PrepareAnalysisRequestOptions]
DocMetaSummaryBuilder = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcApplicationComposition:
    """Complete process-startup dependencies for Document Consistency QC."""

    capabilities: Mapping[str, DocumentConsistencyQcCapabilityConfig]
    extract_bindings: Mapping[tuple[str, str], str]
    prepare_analysis_bindings: Mapping[tuple[str, str], PrepareAnalysisConfigId]
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]]
    candidate_scope_manual_default_filter_job_bindings: Mapping[tuple[str, str], str]
    expected_document_type_bindings: Mapping[tuple[str, str], str]
    prepare_analysis_config_registry: PrepareAnalysisConfigRegistry
    load_prepare_request_options: PrepareRequestOptionsLoader
    doc_meta_profile: MetadataProfile
    doc_meta_summary_builder: DocMetaSummaryBuilder
    filter_configs: Mapping[str, Any]
    filter_job_variants: Mapping[tuple[str, str], Any]
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob]
    filter_output_projection_facade_builder: FilterOutputProjectionFacadeBuilder
    projected_source_route_executor: ProjectedSourceRouteExecutor
    route_semantic_module_sequence: tuple[str, ...]
    evidence_source_preparation_consumer_bindings: (
        EvidenceSourcePreparationConsumerBindings
    )
    evidence_comparison_consumer_bindings: EvidenceComparisonConsumerBindings
    llm_dependency_bindings: Mapping[str, str]

    def resolve_filter_output_projection_job(
        self,
        filter_job_id: str,
    ) -> ResolvedFilterOutputProjectionJob:
        """Resolve one installed Filter-output projection job by filter_job_id."""
        return _resolve_filter_output_projection_job(
            filter_job_id=filter_job_id,
            filter_output_projection_jobs=self.filter_output_projection_jobs,
        )

    def enabled_route_semantic_module_ids(self) -> frozenset[str]:
        """Return installed semantic module ids enabled for Route execution."""

        return frozenset(self.route_semantic_module_sequence)

    def is_route_semantic_module_enabled(self, semantic_module_id: str) -> bool:
        """Return whether one semantic module is installed for Route execution."""

        if not isinstance(semantic_module_id, str) or not semantic_module_id.strip():
            raise ValueError("semantic_module_id must be a non-empty string")
        return semantic_module_id.strip() in self.enabled_route_semantic_module_ids()


__all__ = [
    "DocMetaSummaryBuilder",
    "DocumentConsistencyQcApplicationComposition",
    "EvidenceSourcePreparationConsumerBinding",
    "EvidenceSourcePreparationConsumerBindings",
    "FilterOutputProjectionFacadeBuilder",
    "PrepareRequestOptionsLoader",
    "ProjectedSourceRouteExecutor",
]
