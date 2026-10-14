"""Shared bridge runtime config for Candidate Scope HTTP bridge."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)

OverviewProjectionRuntimeDependenciesResolver = Callable[
    [DocumentConsistencyQcApplicationComposition],
    FilterOutputProjectionRuntimeDependencies,
]


@dataclass(frozen=True, slots=True)
class BridgeRuntimeConfig:
    workspace_root: Path
    runs_root: Path
    git_root: Path
    participant_privacy_paths: Mapping[str, Path | None] = field(default_factory=dict)
    projection_runtime_dependencies: (
        FilterOutputProjectionRuntimeDependencies | None
    ) = None
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ) = None
    evidence_comparison_execution_dependencies: (
        EvidenceComparisonExecutionDependencies | None
    ) = None


@dataclass(frozen=True, slots=True)
class CandidateScopeProjectionDependencies:
    """Injectable projection runtime dependencies for candidate-scope Next."""

    materialize_overview_projection_runtime_dependencies: (
        OverviewProjectionRuntimeDependenciesResolver | None
    ) = field(default=None)


__all__ = [
    "BridgeRuntimeConfig",
    "CandidateScopeProjectionDependencies",
    "OverviewProjectionRuntimeDependenciesResolver",
]
