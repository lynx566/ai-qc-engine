"""Shared bridge runtime config for Document Consistency QC HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcBridgeConfig:
    """Runtime paths for bridge transport; does not own capability rules."""

    default_workspace_root: Path
    project_root: Path | None = None
    upload_staging_root: Path | None = None
    projection_runtime_dependencies: (
        FilterOutputProjectionRuntimeDependencies | None
    ) = None
    evidence_source_preparation_execution_dependencies: (
        EvidenceSourcePreparationExecutionDependencies | None
    ) = None


__all__ = [
    "DocumentConsistencyQcBridgeConfig",
]
